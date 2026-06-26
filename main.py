#!/usr/bin/env python3
import os, sys, json, time, threading, webbrowser, signal
from pathlib import Path

os.chdir(Path(__file__).parent)

import cv2
from PIL import Image

from config import Config
from engine.detector import Detector
from engine.plate_reader import PlateReader
from engine.logger import Logger
from engine.location import Location
from server.camera_stream import CameraStream

RUNNING = True
latest_frame = None
frame_lock = threading.Lock()
LOCATION_CACHE = (0.0, 0.0)

def signal_handler(sig, frame):
  global RUNNING
  RUNNING = False
  print("\n  ⏹ Shutting down...")

def annotate_frame(frame_in):
  global latest_frame
  with frame_lock:
    latest_frame = frame_in

def get_annotated_frame():
  with frame_lock:
    return latest_frame.copy() if latest_frame is not None else None

def print_banner(config, port):
  print("")
  print("  ╔═══════════════════════════════════════════╗")
  print("  ║     🚗 Car Security Logger               ║")
  print("  ║───────────────────────────────────────────║")
  if config.api_key_set:
    m = config.get("openrouter_model", "").split("/")[-1]
    print(f"  ║  🤖 AI: {m:<28} ║")
  else:
    print(f"  ║  🤖 AI: Key not set                     ║")
  print(f"  ║───────────────────────────────────────────║")
  print(f"  ║  🔗 Dashboard: http://localhost:{port}              ║")
  print(f"  ║  📱 Phone: http://<your-ip>:{port}              ║")
  print(f"  ║  ⏹  Press Ctrl+C to stop                 ║")
  print("  ╚═══════════════════════════════════════════╝")
  print("")

def create_app(config, detector, logger, location_obj, camera):
  from flask import Flask, send_from_directory, request, jsonify, Response
  from flask_socketio import SocketIO

  app = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")
  app.config["SECRET_KEY"] = os.urandom(16).hex()
  socketio = SocketIO(app, cors_allowed_origins="*")

  camera_started = False

  @app.route("/")
  def index():
    return send_from_directory("ui/templates", "index.html")

  @app.route("/settings")
  def settings_page():
    return send_from_directory("ui/templates", "settings.html")

  @app.route("/history")
  def history_page():
    return send_from_directory("ui/templates", "history.html")

  @app.route("/snaps/<path:filename>")
  def serve_snap(filename):
    return send_from_directory(config.get("snaps_dir", "data/snaps"), filename)

  @app.route("/video_feed")
  def video_feed():
    nonlocal camera_started
    if not camera_started:
      camera.start()
      time.sleep(1)
      camera_started = True

    def gen():
      while RUNNING:
        annotated = get_annotated_frame()
        if annotated is None:
          time.sleep(0.05)
          continue
        ret, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
          continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

  @app.route("/api/config", methods=["GET"])
  def get_config():
    return jsonify(config.data)

  @app.route("/api/config", methods=["POST"])
  def set_config():
    data = request.get_json()
    if data:
      config.set_many(data)
      return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 400

  @app.route("/api/history")
  def get_history():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    search = request.args.get("search")
    rows = logger.get_history(limit=limit, offset=offset, search=search)
    return jsonify(rows)

  @app.route("/api/stats")
  def get_stats():
    return jsonify(logger.get_stats())

  @app.route("/api/status")
  def get_status():
    global LOCATION_CACHE
    return jsonify({
      "camera": camera.is_opened,
      "api_key": bool(config.get("openrouter_api_key")),
      "model": config.get("openrouter_model"),
      "location": {"lat": LOCATION_CACHE[0], "lon": LOCATION_CACHE[1]},
      "stats": logger.get_stats(),
    })

  @socketio.on("connect")
  def handle_connect():
    pass

  return app, socketio

def engine_loop(config, camera, detector, plate_reader, logger, location_obj, broadcast_func):
  global RUNNING, LOCATION_CACHE
  camera.start()
  time.sleep(1.5)

  if not camera.is_opened:
    print("  ❌ Camera not found. Check connection.")
    if broadcast_func:
      broadcast_func({"type": "error", "msg": "Camera not found"})
    return

  print("  📷 Camera started")
  print("  🟢 Waiting for cars...")
  print("")

  lat, lon = 0.0, 0.0
  if location_obj:
    lat, lon = location_obj.get()
    LOCATION_CACHE = (lat, lon)

  while RUNNING:
    frame = camera.read()
    if frame is None:
      time.sleep(0.1)
      continue

    result = detector.process(frame)
    annotate_frame(result["frame"])

    if result.get("idle"):
      time.sleep(0.3)

    if result["trigger_capture"] and result.get("captured_car"):
      car = result["captured_car"]
      x, y, w, h = car["bbox"]
      raw = result["raw_frame"]
      crop = raw[max(0,y-20):min(raw.shape[0],y+h+20), max(0,x-20):min(raw.shape[1],x+w+20)]
      if crop.size == 0:
        crop = raw

      plate_info = None
      if plate_reader:
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(crop_rgb)
        plate_info = plate_reader.read_plate(pil_image)

      if location_obj:
        lat, lon = location_obj.get()
        LOCATION_CACHE = (lat, lon)

      ms = int(time.time() * 1000) % 1000
      ts = time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

      plate_number = "UNKNOWN"
      vehicle_info = ""
      if plate_info and plate_info.get("plate"):
        plate_number = plate_info["plate"]
        parts = []
        if plate_info.get("color"): parts.append(plate_info["color"])
        if plate_info.get("make"): parts.append(plate_info["make"])
        vehicle_info = " ".join(parts)

      if plate_number != "UNKNOWN" and logger.is_duplicate(plate_number):
        print(f"  [{time.strftime('%H:%M:%S')}] ⏭ {plate_number:10s} | DUPLICATE")
        continue

      image_path = None
      if config.get("save_snaps"):
        snaps_dir = config.get("snaps_dir", "data/snaps")
        os.makedirs(snaps_dir, exist_ok=True)
        fname = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}-{plate_number.replace(' ','_')}.jpg"
        image_path = os.path.join(snaps_dir, fname)
        cv2.imwrite(image_path, result["raw_frame"],
                    [cv2.IMWRITE_JPEG_QUALITY, config.get("snap_quality", 85)])

      logger.log(
        plate=plate_number, lat=lat, lon=lon,
        image_path=image_path, vehicle_info=vehicle_info,
        raw_ai=json.dumps(plate_info) if plate_info else None
      )

      print(f"  [{time.strftime('%H:%M:%S')}] 📸 {plate_number:10s} | {vehicle_info or 'N/A':20s}")

      if broadcast_func:
        broadcast_func({
          "type": "detection",
          "plate": plate_number,
          "timestamp": ts,
          "vehicle_info": vehicle_info,
          "image_path": image_path,
          "lat": lat, "lon": lon,
        })

  camera.stop()
  logger.close()

def main():
  global RUNNING
  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  config = Config()

  if not config.api_key_set:
    print("  ⚠ No OpenRouter API key configured.")
    print("  ⚠ Open the dashboard → Settings → paste your key.")
    print("")

  detector = Detector(config)
  plate_reader = PlateReader(config) if config.api_key_set else None
  logger = Logger(config)
  location_obj = Location(config) if config.get("location_auto") else None
  camera = CameraStream(config)

  port = config.get("server_port", 5000)
  print_banner(config, port)

  detection_history = []

  def broadcast_func(data):
    detection_history.append(data)
    if len(detection_history) > 500:
      detection_history.pop(0)

  app, socketio = create_app(config, detector, logger, location_obj, camera)

  engine_thread = threading.Thread(
    target=engine_loop,
    args=(config, camera, detector, plate_reader, logger, location_obj, broadcast_func),
    daemon=True
  )
  engine_thread.start()

  webbrowser.open(f"http://localhost:{port}")

  try:
    socketio.run(app, host="0.0.0.0", port=port, debug=False, log_output=False, allow_unsafe_werkzeug=True)
  except KeyboardInterrupt:
    RUNNING = False

  print("  ✅ Car Logger stopped.")

if __name__ == "__main__":
  main()
