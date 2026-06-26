import cv2
import threading

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

  def start(self):
    if self._running:
      return
    self.cap = cv2.VideoCapture(self.camera_id)
    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
    self._running = True
    self._thread = threading.Thread(target=self._capture_loop, daemon=True)
    self._thread.start()

  def stop(self):
    self._running = False
    if self._thread:
      self._thread.join(timeout=2)
    if self.cap:
      self.cap.release()
      self.cap = None

  def _capture_loop(self):
    while self._running and self.cap:
      ret, frame = self.cap.read()
      if ret:
        with self.lock:
          self._latest_frame = frame

  def read(self):
    with self.lock:
      return self._latest_frame.copy() if self._latest_frame is not None else None

  @property
  def is_opened(self):
    return self.cap is not None and self.cap.isOpened()

  def gen_frames(self, annotated_frame_provider=None):
    while self._running:
      frame = self.read()
      if frame is None:
        continue
      if annotated_frame_provider:
        frame = annotated_frame_provider(frame)
      ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
      if not ret:
        continue
      yield (b"--frame\r\n"
             b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
