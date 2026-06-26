import base64, json, time
from io import BytesIO
from PIL import Image
import requests

class PlateReader:
  def __init__(self, config):
    self.config = config
    self.api_key = config.get("openrouter_api_key", "")
    self.model = config.get("openrouter_model", "meta-llama/llama-3.2-11b-vision-instruct:free")
    self._last_call = 0
    self._min_interval = 2.0

  def _encode_image(self, pil_image, max_size=640):
    w, h = pil_image.size
    if max(w, h) > max_size:
      scale = max_size / max(w, h)
      pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    pil_image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

  def read_plate(self, pil_image):
    elapsed = time.time() - self._last_call
    if elapsed < self._min_interval:
      return None

    if not self.api_key:
      return None

    b64 = self._encode_image(pil_image)
    payload = {
      "model": self.model,
      "messages": [
        {
          "role": "user",
          "content": [
            {"type": "text", "text": "Extract the license plate number from this car image. Return ONLY valid JSON with fields: plate (string), color (string), make (string), confidence (high/medium/low). If no plate visible, return {\"plate\": null, \"confidence\": \"none\"}."},
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
      self._last_call = time.time()
      if r.status_code != 200:
        return None
      data = r.json()
      content = data["choices"][0]["message"]["content"]
      parsed = json.loads(content)
      if parsed.get("plate"):
        return {
          "plate": parsed["plate"].strip().upper(),
          "color": parsed.get("color", ""),
          "make": parsed.get("make", ""),
          "confidence": parsed.get("confidence", "low"),
          "raw": content
        }
    except Exception:
      pass
    return None
