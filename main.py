#!/usr/bin/env python3
import os, sys, json, time, threading, webbrowser, signal
from pathlib import Path

os.chdir(Path(__file__).parent)

import cv2, psutil
from PIL import Image

from config import Config
from engine.detector import Detector
from engine.plate_reader import PlateReader
from engine.logger import Logger
from engine.location import Location
from server.camera_stream import CameraStream

RUNNING = True
START_TIME = time.time()
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

def create_app(config, detector, logger, location_obj, camera, plate_reader):
  from flask import Flask, send_from_directory, request, jsonify, Response
  from flask_socketio import SocketIO

  app = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")
  app.config["SECRET_KEY"] = os.urandom(16).hex()
  socketio = SocketIO(app, cors_allowed_origins="http://localhost:5000", async_mode="threading")

  @app.after_request
  def add_security_headers(resp):
    resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://cdn.socket.io; connect-src 'self' ws: http://localhost:5000;"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp

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

  @app.route("/queue")
  def queue_page():
    return send_from_directory("ui/templates", "queue.html")

  @app.route("/api/queue")
  def get_queue():
    if not plate_reader:
      return jsonify([])
    return jsonify(plate_reader.get_requests(50))

  @app.route("/snaps/<path:filename>")
  def serve_snap(filename):
    sanitized = os.path.basename(filename)
    return send_from_directory(config.get("snaps_dir", "data/snaps"), sanitized)

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
    safe = {k: v for k, v in config.data.items() if k != "openrouter_api_key"}
    safe["openrouter_api_key"] = bool(config.get("openrouter_api_key"))
    return jsonify(safe)

  CONFIG_ALLOWED_KEYS = {"openrouter_api_key", "openrouter_model", "camera_id", "resolution", "fps_motion", "fps_idle", "idle_timeout", "sensitivity", "min_car_area", "dedup_seconds", "location_auto", "location_lat", "location_lon", "location_refresh_minutes", "server_port", "save_snaps", "snap_quality", "snaps_dir", "auto_start", "detection_zone"}

  @app.route("/api/config", methods=["POST"])
  def set_config():
    origin = request.headers.get("Origin", "")
    if origin and origin not in ("http://localhost:5000", f"http://127.0.0.1:{config.get('server_port', 5000)}"):
      return jsonify({"status": "error", "message": "Invalid origin"}), 403
    data = request.get_json()
    if not data:
      return jsonify({"status": "error", "message": "No settings data received. Try again."}), 400
    filtered = {k: v for k, v in data.items() if k in CONFIG_ALLOWED_KEYS}
    if not filtered:
      return jsonify({"status": "error", "message": "No valid settings keys."}), 400
    config.set_many(filtered)
    if "openrouter_api_key" in filtered and plate_reader:
      plate_reader.api_key = filtered["openrouter_api_key"]
    return jsonify({"status": "ok"})

  @app.route("/api/history")
  def get_history():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    search = request.args.get("search")
    ai_label = request.args.get("ai_label")
    rows = logger.get_history(limit=limit, offset=offset, search=search, ai_label=ai_label)
    return jsonify(rows)

  @app.route("/api/plates")
  def get_known_plates():
    return jsonify(logger.get_known_plates())

  @app.route("/api/stats")
  def get_stats():
    return jsonify(logger.get_stats())

  @app.route("/api/history", methods=["DELETE"])
  def delete_history():
    if request.args.get("all"):
      count = logger.delete_all()
      return jsonify({"deleted": count})
    ids = request.get_json()
    if not ids or not isinstance(ids, list):
      return jsonify({"error": "Send a JSON array of IDs to delete"}), 400
    count = logger.delete_by_ids(ids)
    return jsonify({"deleted": count})

  @app.route("/api/status")
  def get_status():
    global LOCATION_CACHE
    return jsonify({
      "camera": camera.is_opened,
      "api_key": bool(config.get("openrouter_api_key")),
      "model": config.get("openrouter_model"),
      "location": {"lat": LOCATION_CACHE[0], "lon": LOCATION_CACHE[1]},
      "stats": logger.get_stats(),
      "ai_queue": plate_reader.queue_size if plate_reader else 0,
      "ai_current": plate_reader.current_request_id if plate_reader else None,
    })

  @app.route("/health")
  def health_page():
    return send_from_directory("ui/templates", "health.html")

  @app.route("/api/health")
  def get_health():
    global START_TIME, LOCATION_CACHE
    uptime_seconds = int(time.time() - START_TIME)
    db_path = config.get("db_path", "data/plates.db")
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    snaps_dir = config.get("snaps_dir", "data/snaps")
    disk = psutil.disk_usage(snaps_dir if os.path.exists(snaps_dir) else ".")
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.3)
    row_count = 0
    try:
      row_count = logger.get_stats()["total"]
    except: pass
    return jsonify({
      "uptime": uptime_seconds,
      "camera": {"connected": camera.is_opened},
      "api": {
        "key_set": bool(config.get("openrouter_api_key")),
        "model": config.get("openrouter_model"),
      },
      "database": {"size_bytes": db_size, "rows": row_count},
      "disk": {"free_bytes": disk.free, "total_bytes": disk.total, "percent_used": disk.percent},
      "memory": {"percent": mem.percent, "available_bytes": mem.available, "total_bytes": mem.total},
      "cpu_percent": cpu,
      "location": {"lat": LOCATION_CACHE[0], "lon": LOCATION_CACHE[1]},
      "stats": logger.get_stats(),
      "ai_queue": plate_reader.queue_size if plate_reader else 0,
      "ai_current": plate_reader.current_request_id if plate_reader else None,
    })


  @socketio.on("connect")
  def handle_connect():
    pass

  return app, socketio

def log_ai_result(config, logger, location_obj, broadcast_func, ai_result, capture_info):
  global LOCATION_CACHE
  lat, lon = LOCATION_CACHE
  if location_obj:
    lat, lon = location_obj.get()
    LOCATION_CACHE = (lat, lon)

  ms = int(time.time() * 1000) % 1000
  ts = time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

  if ai_result is None:
    ai_label = "error"
    _, row_id = logger.log(
      plate=None, lat=lat, lon=lon,
      image_path=None, vehicle_info="AI error",
      raw_ai=None, ai_label=ai_label
    )
    print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ AI ERROR")
    if broadcast_func:
      broadcast_func({
        "type": "detection",
        "ai_label": ai_label,
        "id": row_id,
        "plate": None,
        "timestamp": ts,
        "vehicle_info": "AI error",
        "image_path": None,
        "lat": lat, "lon": lon,
        "confidence": "none",
        "color": "",
        "make": "",
        "raw_ai": "",
      })
    return

  is_car = ai_result.get("is_car", False)
  ai_label = "car" if is_car else "non_car"
  plate_number = ai_result.get("plate") or ("UNKNOWN" if is_car else None)
  parts = []
  if ai_result.get("color"): parts.append(ai_result["color"])
  if ai_result.get("make"): parts.append(ai_result["make"])
  vehicle_info = " ".join(parts)

  if is_car and plate_number and plate_number != "UNKNOWN" and logger.is_duplicate(plate_number):
    print(f"  [{time.strftime('%H:%M:%S')}] ⏭ {plate_number:10s} | DUPLICATE")
    return

  image_path = None
  if is_car and config.get("save_snaps"):
    snaps_dir = config.get("snaps_dir", "data/snaps")
    os.makedirs(snaps_dir, exist_ok=True)
    fname = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}-{(plate_number or 'unknown').replace(' ','_')}.jpg"
    cv2.imwrite(os.path.join(snaps_dir, fname), capture_info["raw_frame"],
                [cv2.IMWRITE_JPEG_QUALITY, config.get("snap_quality", 85)])
    image_path = fname

  _, row_id = logger.log(
    plate=plate_number, lat=lat, lon=lon,
    image_path=image_path, vehicle_info=vehicle_info,
    raw_ai=json.dumps(ai_result), ai_label=ai_label
  )

  if is_car:
    label = f"{plate_number:10s}" if plate_number and plate_number != "UNKNOWN" else "UNKNOWN   "
    print(f"  [{time.strftime('%H:%M:%S')}] 🚗 {label} | {vehicle_info or 'N/A':20s}")
  else:
    print(f"  [{time.strftime('%H:%M:%S')}] 🚫 NON-CAR ({ai_result.get('raw', '')[:40]})")

  if broadcast_func:
    broadcast_func({
      "type": "detection",
      "ai_label": ai_label,
      "id": row_id,
      "plate": plate_number,
      "timestamp": ts,
      "vehicle_info": vehicle_info,
      "image_path": image_path,
      "lat": lat, "lon": lon,
      "confidence": ai_result.get("confidence", "none"),
      "color": ai_result.get("color", ""),
      "make": ai_result.get("make", ""),
      "raw_ai": ai_result.get("raw", ""),
    })


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

      # Save snap immediately
      if config.get("save_snaps"):
        snaps_dir = config.get("snaps_dir", "data/snaps")
        os.makedirs(snaps_dir, exist_ok=True)
        fname = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}-capture.jpg"
        cv2.imwrite(os.path.join(snaps_dir, fname), raw,
                    [cv2.IMWRITE_JPEG_QUALITY, config.get("snap_quality", 85)])
      else:
        fname = None

      if not plate_reader or not plate_reader.api_key:
        continue

      capture_info = {"raw_frame": raw.copy(), "snap_filename": fname}
      crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
      pil_image = Image.fromarray(crop_rgb)
      plate_reader.queue_plate(pil_image, callback=lambda ai_result, ci=capture_info: log_ai_result(config, logger, location_obj, broadcast_func, ai_result, ci))

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
  plate_reader = PlateReader(config)
  logger = Logger(config)
  location_obj = Location(config) if config.get("location_auto") else None
  camera = CameraStream(config)
  if plate_reader.api_key:
    plate_reader.start()

  port = config.get("server_port", 5000)
  print_banner(config, port)

  app, socketio = create_app(config, detector, logger, location_obj, camera, plate_reader)

  detection_history = []

  def broadcast_func(data):
    detection_history.append(data)
    if len(detection_history) > 500:
      detection_history.pop(0)
    try:
      socketio.emit("new_detection", data)
    except:
      pass

  if plate_reader:
    def on_queue_update(reqs):
      try:
        socketio.emit("queue_update", reqs)
      except:
        pass
    plate_reader.set_on_update(on_queue_update)

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
