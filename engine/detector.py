import cv2
import numpy as np
import time
from collections import OrderedDict

class Detector:
  def __init__(self, config):
    self.config = config
    self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
      history=500, varThreshold=36, detectShadows=True
    )
    self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    self._prev_gray = None
    self._motion_frames = 0
    self._idle_frames = 0
    self._last_motion_time = time.time()
    self._tracks = OrderedDict()
    self._next_track_id = 0
    self._frame_count = 0
    self._capture_ready = True
    self._capture_cooldown = 0

  def process(self, frame):
    self._frame_count += 1
    h, w = frame.shape[:2]
    zone = self.config.detection_zone_percent
    zx1 = int(w * zone[0] / 100)
    zy1 = int(h * zone[1] / 100)
    zx2 = int(w * zone[2] / 100)
    zy2 = int(h * zone[3] / 100)

    gray = cv2.cvtColor(frame, cv2.GaussianBlur(frame, (5, 5)), cv2.COLOR_BGR2GRAY)
    fg_mask = self.bg_subtractor.apply(gray)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)
    _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = self.config.get("min_car_area", 500)

    cars = []
    for cnt in contours:
      area = cv2.contourArea(cnt)
      if area < min_area:
        continue
      x, y, bw, bh = cv2.boundingRect(cnt)
      aspect = bw / max(bh, 1)
      if aspect < 0.3 or aspect > 5.0:
        continue
      cx, cy = x + bw // 2, y + bh // 2
      cars.append({
        "bbox": (x, y, bw, bh),
        "center": (cx, cy),
        "area": area
      })

    cars_in_zone = [c for c in cars if zx1 < c["center"][0] < zx2 and zy1 < c["center"][1] < zy2]
    motion = len(cars_in_zone) > 0

    now = time.time()
    if motion:
      self._last_motion_time = now
      self._motion_frames += 1
    else:
      self._motion_frames = 0

    idle = (now - self._last_motion_time) > self.config.get("idle_timeout", 5)

    trigger_capture = False
    captured_car = None
    if motion and self._capture_ready:
      best = max(cars_in_zone, key=lambda c: c["area"])
      trigger_capture = True
      captured_car = best
      self._capture_ready = False
      self._capture_cooldown = now

    if not self._capture_ready and (now - self._capture_cooldown) > 3:
      self._capture_ready = True

    result_frame = frame.copy()
    cv2.rectangle(result_frame, (zx1, zy1), (zx2, zy2), (0, 255, 255), 2)
    cv2.putText(result_frame, "ZONE", (zx1, zy1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    for c in cars:
      x, y, bw, bh = c["bbox"]
      color = (0, 255, 0) if c == captured_car else (0, 200, 0)
      cv2.rectangle(result_frame, (x, y), (x + bw, y + bh), color, 2)

    status = "🟢 ACTIVE" if motion else ("💤 IDLE" if idle else "🟡 WATCHING")
    cv2.putText(result_frame, status, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if motion else (100, 100, 100), 2)
    cv2.putText(result_frame, f"Cars: {len(cars_in_zone)}", (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    return {
      "frame": result_frame,
      "motion": motion,
      "idle": idle,
      "trigger_capture": trigger_capture,
      "captured_car": captured_car,
      "cars_in_zone": len(cars_in_zone),
      "raw_frame": frame,
    }
