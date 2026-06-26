import cv2
import threading
import time

class CameraStream:
  def __init__(self, config):
    self.config = config
    self.camera_id = config.get("camera_id", 0)
    self.resolution = tuple(config.get("resolution", [720, 480]))
    self.cap = None
    self.lock = threading.Lock()
    self._latest_frame = None
    self._running = False
    self._thread = None
    self._failures = 0

  def start(self):
    if self._running:
      return
    self._open_camera()
    self._running = True
    self._thread = threading.Thread(target=self._capture_loop, daemon=True)
    self._thread.start()

  def _open_camera(self):
    if self.cap:
      self.cap.release()
    self.cap = cv2.VideoCapture(self.camera_id)
    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

  def stop(self):
    self._running = False
    if self._thread:
      self._thread.join(timeout=2)
    if self.cap:
      self.cap.release()
      self.cap = None

  def _capture_loop(self):
    while self._running:
      if not self.cap or not self.cap.isOpened():
        self._open_camera()
        time.sleep(1)
        continue
      ret, frame = self.cap.read()
      if ret:
        self._failures = 0
        with self.lock:
          self._latest_frame = frame
      else:
        self._failures += 1
        if self._failures > 10:
          self._open_camera()
          self._failures = 0
        time.sleep(0.5)

  def read(self):
    with self.lock:
      return self._latest_frame.copy() if self._latest_frame is not None else None

  @property
  def is_opened(self):
    return self.cap is not None and self.cap.isOpened()
