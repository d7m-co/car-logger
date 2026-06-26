import base64, json, time, threading, queue
from io import BytesIO
from PIL import Image
import requests

def _average_hash(pil_image, size=8):
  '''64-bit perceptual hash — similar images have small Hamming distance'''
  img = pil_image.convert("L").resize((size, size), Image.LANCZOS)
  pixels = list(img.getdata())
  avg = sum(pixels) / len(pixels)
  return sum((1 if p > avg else 0) << i for i, p in enumerate(pixels))

def _hamming_distance(a, b):
  return bin(a ^ b).count("1")

class PlateReader:
  def __init__(self, config):
    self.config = config
    self.api_key = config.get("openrouter_api_key", "")
    self.model = config.get("openrouter_model", "openrouter/free")
    self._req_queue = queue.Queue()  # unlimited
    self._last_api_call = 0
    self._base_api_interval = 15.0
    self._cooldown_until = 0.0
    self._worker = None
    self._running = False
    self._lock = threading.Lock()
    self._requests = {}
    self._next_id = 1
    self._current_id = None
    self._on_update = None
    self._last_hash = None
    self._last_plate = None
    self._dedup_window = 10.0

  def set_on_update(self, callback):
    self._on_update = callback

  @property
  def queue_size(self):
    return self._req_queue.qsize()

  @property
  def current_request_id(self):
    return self._current_id

  def get_requests(self, limit=50):
    with self._lock:
      items = sorted(self._requests.values(), key=lambda r: r["queued_at"], reverse=True)
      return items[:limit]

  def start(self):
    self._running = True
    self._worker = threading.Thread(target=self._worker_loop, daemon=True)
    self._worker.start()

  def stop(self):
    self._running = False

  def _notify(self):
    if self._on_update:
      try:
        self._on_update(self.get_requests(20))
      except:
        pass

  def _dynamic_interval(self):
    '''thrust: faster when queue is deep, coast when shallow'''
    q = self._req_queue.qsize()
    base = self._base_api_interval
    if q >= 30: return max(base - 3, 8.0)
    if q >= 15: return max(base - 2, 10.0)
    if q >= 5:  return base
    return base

  def _worker_loop(self):
    while self._running:
      try:
        item = self._req_queue.get(timeout=1)
        req_id, pil_image, callback = item
        now = time.time()
        cooldown_left = self._cooldown_until - now
        interval = self._dynamic_interval()
        since_last = now - self._last_api_call
        wait = max(interval - since_last, cooldown_left, 0)
        if wait > 0:
          time.sleep(wait)
        self._current_id = req_id
        with self._lock:
          if req_id in self._requests:
            self._requests[req_id]["status"] = "processing"
            self._requests[req_id]["started_at"] = time.time()
        self._notify()

        # Frame dedup: skip if same car as previous result
        with self._lock:
          this_hash = self._requests.get(req_id, {}).get("phash")
          skip = False
          skip_reason = None
          if this_hash is not None and self._last_hash is not None and _hamming_distance(this_hash, self._last_hash) < 15:
            # Same car — skip, use previous result
            skip = True
            skip_reason = f"same car as previous (hash diff < 12)"
            result = self._last_result
            err = None
            # Find the previous request ID that had this plate
            prev_id = None
            for rid, r in self._requests.items():
              if rid != req_id and r.get("status") == "completed" and r.get("result") and r["result"].get("plate"):
                prev_id = rid
                break
            if prev_id:
              skip_reason += f", see #{prev_id}"

        if not skip:
          result, err = self._do_read_plate(pil_image)

        self._last_api_call = time.time()
        if err and ("rate" in err.lower() or "429" in err):
          self._cooldown_until = time.time() + 20
        self._current_id = None
        with self._lock:
          if req_id in self._requests:
            if err:
              self._requests[req_id]["status"] = "error"
              self._requests[req_id]["error"] = err
            elif result is None:
              self._requests[req_id]["status"] = "error"
              self._requests[req_id]["error"] = "AI returned no result"
            elif skip:
              self._requests[req_id]["status"] = "skipped"
              self._requests[req_id]["error"] = skip_reason
              self._requests[req_id]["result"] = result
            else:
              self._requests[req_id]["status"] = "completed"
              self._requests[req_id]["result"] = result
              if result:
                self._last_hash = this_hash
                self._last_result = result
              else:
                self._last_hash = None
                self._last_result = None
            self._requests[req_id]["completed_at"] = time.time()
        self._notify()
        if callback:
          callback(result)
      except queue.Empty:
        continue

  def queue_plate(self, pil_image, callback=None):
    if not self.api_key:
      return None
    now = time.time()
    phash = _average_hash(pil_image)
    with self._lock:
      req_id = self._next_id
      self._next_id += 1
      req = {
        "id": req_id,
        "status": "queued",
        "queued_at": now,
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
        "phash": phash,
      }
      self._requests[req_id] = req
    self._req_queue.put_nowait((req_id, pil_image, callback))
    self._notify()
    return req_id

  def _encode_image(self, pil_image, max_size=640):
    w, h = pil_image.size
    if max(w, h) > max_size:
      scale = max_size / max(w, h)
      pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    pil_image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

  def _do_read_plate(self, pil_image):
    if not self.api_key:
      return None, "No API key configured"

    b64 = self._encode_image(pil_image)
    payload = {
      "model": self.model,
      "messages": [
        {
          "role": "user",
          "content": [
            {"type": "text", "text": "Look at this image. First decide: is there a car visible? Return ONLY valid JSON with fields: is_car (boolean), plate (string or null), color (string), make (string), confidence (high/medium/low/none). If it's not a car, set is_car to false and plate to null. If it is a car but plate is unreadable, set is_car to true and plate to null."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
          ]
        }
      ],
      "response_format": {"type": "json_object"},
      "max_tokens": 200
    }

    headers = {
      "Authorization": f"Bearer {self.api_key}",
      "Content-Type": "application/json",
      "HTTP-Referer": "https://github.com/car-logger",
      "X-Title": "Car Security Logger"
    }

    for attempt in range(2):
      try:
        r = requests.post(
          "https://openrouter.ai/api/v1/chat/completions",
          headers=headers, json=payload, timeout=15
        )
        if r.status_code == 200:
          data = r.json()
          content = data["choices"][0]["message"]["content"]
          parsed = json.loads(content)
          return {
            "is_car": parsed.get("is_car", False),
            "plate": parsed["plate"].strip().upper() if parsed.get("plate") else None,
            "color": parsed.get("color", ""),
            "make": parsed.get("make", ""),
            "confidence": parsed.get("confidence", "none"),
            "raw": content
          }, None
        elif r.status_code == 404 and attempt == 0:
          time.sleep(2)
          continue
        else:
          err_msg = f"HTTP {r.status_code}"
          if r.status_code == 429:
            err_msg = "Rate limited"
          elif r.status_code >= 500:
            err_msg = "Server error"
          try:
            body = r.json()
            m = body.get("error", {}).get("message", "")
            if m:
              err_msg += f": {m[:100]}"
          except:
            pass
          return None, err_msg
      except requests.Timeout:
        return None, "Timed out"
      except requests.ConnectionError:
        return None, "Connection error"
      except Exception as e:
        return None, f"Error: {e}"
    return None, "Failed"
