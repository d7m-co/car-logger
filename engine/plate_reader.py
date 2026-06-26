import base64, json, time, threading, queue
from io import BytesIO
from PIL import Image
import requests

class PlateReader:
  def __init__(self, config):
    self.config = config
    self.api_key = config.get("openrouter_api_key", "")
    self.model = config.get("openrouter_model", "openrouter/free")
    self._last_call = 0
    self._min_interval = 2.0
    self._req_queue = queue.Queue(maxsize=20)
    self._worker = None
    self._running = False
    self._lock = threading.Lock()
    self._requests = {}
    self._next_id = 1
    self._current_id = None
    self._on_update = None

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

  def _worker_loop(self):
    while self._running:
      try:
        item = self._req_queue.get(timeout=1)
        req_id, pil_image, callback = item
        self._current_id = req_id
        with self._lock:
          if req_id in self._requests:
            self._requests[req_id]["status"] = "processing"
            self._requests[req_id]["started_at"] = time.time()
        self._notify()
        result = self._do_read_plate(pil_image)
        self._current_id = None
        with self._lock:
          if req_id in self._requests:
            if result is None:
              self._requests[req_id]["status"] = "error"
              self._requests[req_id]["error"] = "API request failed"
            else:
              self._requests[req_id]["status"] = "completed"
              self._requests[req_id]["result"] = result
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
    if now - self._last_call < self._min_interval:
      return None
    self._last_call = now
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
      }
      self._requests[req_id] = req
    try:
      self._req_queue.put_nowait((req_id, pil_image, callback))
      self._notify()
      return req_id
    except queue.Full:
      with self._lock:
        self._requests.pop(req_id, None)
      return None

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
      return None

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

    try:
      r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
          "Authorization": f"Bearer {self.api_key}",
          "Content-Type": "application/json",
          "HTTP-Referer": "https://github.com/car-logger",
          "X-Title": "Car Security Logger"
        },
        json=payload,
        timeout=30
      )
      if r.status_code != 200:
        return None
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
      }
    except Exception:
      pass
    return None
