import base64, json, sys, time, threading, queue
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
  # (model_id, provider, use_response_format)
  # provider: "go" -> OpenCode Go, "or" -> OpenRouter
  # use_response_format: True for models that require {"type":"json_object"}
  ROTATION = [
    ("mimo-v2.5",                              "go", False),
    ("google/gemma-4-26b-a4b-it:free",         "or", False),
    ("nvidia/nemotron-nano-12b-v2-vl:free",    "or", True),
    ("google/gemma-4-31b-it:free",             "or", False),
  ]

  GO_ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
  OR_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

  def __init__(self, config):
    self.config = config
    self._go_key = config.get("opencode_go_api_key", "")
    self._or_key = config.get("openrouter_api_key", "")
    self._model_idx = 0
    self._req_queue = queue.Queue()  # unlimited
    self._last_enqueue = 0
    self._min_enqueue_gap = 1.5
    # per-model min spacing (seconds) to avoid rate limits
    self._model_interval = {
      "mimo-v2.5": 1.5,
      "google/gemma-4-26b-a4b-it:free": 2.0,
      "nvidia/nemotron-nano-12b-v2-vl:free": 2.0,
      "google/gemma-4-31b-it:free": 3.0,
    }
    self._last_call = {}  # model_id -> timestamp
    self._workers = []
    self._num_workers = 4
    self._running = False
    self._lock = threading.Lock()
    self._model_lock = threading.Lock()
    self._requests = {}
    self._next_id = 1
    self._current_id = None
    self._on_update = None
    self._last_hash = None
    self._last_result = None
    self._dedup_window = 10.0

  def set_keys(self, go_key=None, or_key=None):
    if go_key is not None:
      self._go_key = go_key
    if or_key is not None:
      self._or_key = or_key

  @property
  def has_any_key(self):
    return bool(self._go_key or self._or_key)

  @property
  def go_key_set(self):
    return bool(self._go_key)

  @property
  def or_key_set(self):
    return bool(self._or_key)

  def set_on_update(self, callback):
    self._on_update = callback

  @property
  def queue_size(self):
    return self._req_queue.qsize()

  @property
  def current_request_id(self):
    return self._current_id

  @property
  def worker_count(self):
    return sum(1 for t in self._workers if t.is_alive())

  @property
  def models(self):
    # Public list of active model IDs (strings) for the UI/API
    return [m[0] for m in self.ROTATION if (
      (m[1] == "go" and self._go_key) or
      (m[1] == "or" and self._or_key)
    )]

  @property
  def _model_specs(self):
    # Internal tuple list: (model_id, provider, use_response_format)
    available = []
    for model, provider, use_fmt in self.ROTATION:
      if provider == "go" and self._go_key:
        available.append((model, provider, use_fmt))
      elif provider == "or" and self._or_key:
        available.append((model, provider, use_fmt))
    return available

  def _next_model(self):
    '''Atomically advance and return the next model spec.'''
    with self._model_lock:
      specs = self._model_specs
      if not specs:
        return None
      info = specs[self._model_idx % len(specs)]
      self._model_idx = (self._model_idx + 1) % len(specs)
      return info

  def get_requests(self, limit=50):
    with self._lock:
      items = sorted(self._requests.values(), key=lambda r: r["queued_at"], reverse=True)
      return items[:limit]

  def start(self):
    self._running = True
    self._workers = []
    for i in range(self._num_workers):
      t = threading.Thread(target=lambda idx=i: self._worker_loop(idx), daemon=True, name=f"PlateReaderWorker-{i}")
      t.start()
      self._workers.append(t)

  def stop(self):
    self._running = False
    for t in self._workers:
      try:
        t.join(timeout=2)
      except:
        pass

  def _notify(self):
    if self._on_update:
      try:
        self._on_update(self.get_requests(20))
      except:
        pass

  def _worker_loop(self, worker_id):
    last_alive_log = time.time()
    while self._running:
      now = time.time()
      if now - last_alive_log >= 60:
        print(f"worker {worker_id} alive, queue size {self._req_queue.qsize()}", file=sys.stderr, flush=True)
        last_alive_log = now

      try:
        item = self._req_queue.get(timeout=1)
      except queue.Empty:
        continue

      req_id = None
      try:
        req_id, pil_image, callback = item

        specs = self._model_specs
        if not specs:
          with self._lock:
            if req_id in self._requests:
              self._requests[req_id]["status"] = "error"
              self._requests[req_id]["error"] = "No AI API key configured"
              self._requests[req_id]["completed_at"] = time.time()
          self._notify()
          if callback:
            try:
              callback(None)
            except Exception:
              pass
          continue

        self._current_id = req_id
        with self._lock:
          if req_id in self._requests:
            self._requests[req_id]["status"] = "processing"
            self._requests[req_id]["started_at"] = time.time()
            self._requests[req_id]["model"] = ""
        self._notify()

        # Frame dedup: skip if same scene as previous result
        with self._lock:
          this_hash = self._requests.get(req_id, {}).get("phash")
          skip = False
          skip_reason = None
          result = None
          err = None
          if this_hash is not None and self._last_hash is not None and _hamming_distance(this_hash, self._last_hash) < 15:
            skip = True
            skip_reason = "same scene as previous (hash diff < 15)"
            result = self._last_result
            prev_id = None
            for rid, r in self._requests.items():
              if rid != req_id and r.get("status") == "completed" and r.get("result") and r["result"].get("plate"):
                prev_id = rid
                break
            if prev_id:
              skip_reason += f", see #{prev_id}"

        model_used = None
        if not skip:
          result, err, model_used = self._do_read_plate(pil_image)
          if model_used:
            with self._lock:
              if req_id in self._requests:
                self._requests[req_id]["model"] = model_used

        self._current_id = None
        with self._lock:
          if req_id in self._requests:
            if err:
              self._requests[req_id]["status"] = "error"
              self._requests[req_id]["error"] = err
              self._requests[req_id]["completed_at"] = time.time()
            elif result is None:
              self._requests[req_id]["status"] = "error"
              self._requests[req_id]["error"] = "AI returned no result"
              self._requests[req_id]["completed_at"] = time.time()
            elif skip:
              self._requests[req_id]["status"] = "skipped"
              self._requests[req_id]["error"] = skip_reason
              self._requests[req_id]["result"] = result
              self._requests[req_id]["completed_at"] = time.time()
            else:
              self._requests[req_id]["status"] = "completed"
              self._requests[req_id]["result"] = result
              self._requests[req_id]["completed_at"] = time.time()
              if result:
                self._last_hash = this_hash
                self._last_result = result
              else:
                self._last_hash = None
                self._last_result = None
        self._notify()
        if callback:
          try:
            callback(result)
          except Exception:
            pass
      except Exception as e:
        self._current_id = None
        print(f"Worker {worker_id} unhandled exception: {e}", file=sys.stderr, flush=True)
        try:
          import traceback
          traceback.print_exc(file=sys.stderr)
        except Exception:
          pass
        if req_id is not None:
          try:
            with self._lock:
              if req_id in self._requests:
                self._requests[req_id]["status"] = "error"
                self._requests[req_id]["error"] = f"worker crash: {e}"
                self._requests[req_id]["completed_at"] = time.time()
            self._notify()
          except Exception:
            pass
          try:
            if callback:
              callback(None)
          except Exception:
            pass
        continue

  def queue_plate(self, pil_image, callback=None):
    if not self.has_any_key:
      return None
    now = time.time()
    # Don't let the queue grow unbounded: throttle enqueue
    if now - self._last_enqueue < self._min_enqueue_gap:
      return None
    self._last_enqueue = now
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
        "model": "",
      }
      self._requests[req_id] = req
    self._req_queue.put_nowait((req_id, pil_image, callback))
    self._notify()
    return req_id

  def _parse_ai_json(self, content):
    '''Parse JSON from AI response, handling markdown code fences and surrounding text'''
    if not content:
      raise ValueError("Empty AI response")
    s = content.strip()

    # Try direct JSON first
    try:
      return json.loads(s)
    except (ValueError, json.JSONDecodeError):
      pass

    # Extract from a markdown code fence if present
    fence = s.find("```")
    if fence != -1:
      nl = s.find("\n", fence)
      if nl != -1:
        inner = s[nl + 1:]
        end = inner.find("```")
        if end != -1:
          inner = inner[:end]
        try:
          return json.loads(inner.strip())
        except (ValueError, json.JSONDecodeError):
          pass

    # Fall back to the first JSON object/array substring
    start = s.find("{")
    if start == -1:
      start = s.find("[")
    end = s.rfind("}")
    if end == -1:
      end = s.rfind("]")
    if start != -1 and end != -1 and end > start:
      try:
        return json.loads(s[start:end + 1])
      except (ValueError, json.JSONDecodeError):
        pass

    raise ValueError(f"Could not parse JSON from response: {content[:100]}")

  def _encode_image(self, pil_image, max_size=1280):
    w, h = pil_image.size
    if max(w, h) > max_size:
      scale = max_size / max(w, h)
      pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    pil_image.save(buf, format="JPEG", quality=95)
    return base64.b64encode(buf.getvalue()).decode()

  def _do_read_plate(self, pil_image):
    b64 = self._encode_image(pil_image)
    messages = [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Scan this image carefully. Look for a license plate — a rectangular high-contrast sign at the vehicle's front or rear. Read each character individually, left to right. Also identify the vehicle. Return ONLY valid JSON with fields: is_car (boolean), plate (string or null, uppercase), color (string), make (string), confidence (high/medium/low/none). If a plate exists but text is unreadable, set plate=null, confidence=low. If it's not a car, set is_car=false and plate=null."},
          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]
      }
    ]

    specs = self._model_specs
    if not specs:
      return None, "No AI API key configured", None

    err = "No models available"
    model_used = None
    for _ in range(len(specs)):
      model_info = self._next_model()
      if not model_info:
        break
      model, provider, use_response_format = model_info

      # Enforce per-model rate limit (spacing measured from completed calls)
      interval = self._model_interval.get(model, 3.0)
      with self._model_lock:
        last = self._last_call.get(model, 0)
      now = time.time()
      wait = max(interval - (now - last), 0)
      if wait > 0:
        time.sleep(wait)

      if provider == "go":
        url = self.GO_ENDPOINT
        headers = {
          "Authorization": f"Bearer {self._go_key}",
          "Content-Type": "application/json",
        }
      else:
        url = self.OR_ENDPOINT
        headers = {
          "Authorization": f"Bearer {self._or_key}",
          "Content-Type": "application/json",
          "HTTP-Referer": "https://github.com/car-logger",
          "X-Title": "Car Security Logger"
        }

      payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 500
      }
      if use_response_format:
        payload["response_format"] = {"type": "json_object"}

      try:
        r = requests.post(url, headers=headers, json=payload, timeout=8)
        if r.status_code == 200:
          data = r.json()
          content = data["choices"][0]["message"]["content"]
          try:
            parsed = self._parse_ai_json(content)
          except (ValueError, json.JSONDecodeError) as e:
            err = f"Bad JSON from {model}: {content[:60] if content else 'None'}"
            with self._model_lock:
              self._last_call[model] = time.time()
            continue
          model_used = model
          with self._model_lock:
            self._last_call[model] = time.time()
          return {
            "is_car": parsed.get("is_car", False),
            "plate": parsed["plate"].strip().upper() if parsed.get("plate") else None,
            "color": parsed.get("color", ""),
            "make": parsed.get("make", ""),
            "confidence": parsed.get("confidence", "none"),
            "raw": content
          }, None, model_used
        elif r.status_code == 429:
          err = f"Rate limited on {model}"
        else:
          try:
            body = r.json()
            m = body.get("error", {}).get("message", "")
            err = f"{model}: HTTP {r.status_code}" + (f": {m[:100]}" if m else "")
          except:
            err = f"{model}: HTTP {r.status_code}"
      except requests.Timeout:
        err = f"{model} timed out"
      except requests.ConnectionError:
        err = f"{model} connection error"
      except Exception as e:
        err = f"{model} error: {e}"
      finally:
        with self._model_lock:
          self._last_call[model] = time.time()
    return None, err, None
