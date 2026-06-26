import threading
from flask import Blueprint, Response, jsonify, request
from .camera_stream import CameraStream

routes = Blueprint("routes", __name__)

_camera = None
_detector = None
_logger = None
_config = None
_location = None
_annotate_func = None

def init(camera, detector, logger, config, location):
  global _camera, _detector, _logger, _config, _location
  _camera = camera
  _detector = detector
  _logger = logger
  _config = config
  _location = location

def set_annotate_func(func):
  global _annotate_func
  _annotate_func = func

@routes.route("/video_feed")
def video_feed():
  if not _camera or not _camera.is_opened:
    return "Camera not available", 503
  return Response(
    _camera.gen_frames(_annotate_func),
    mimetype="multipart/x-mixed-replace; boundary=frame"
  )

@routes.route("/api/config", methods=["GET"])
def get_config():
  return jsonify(_config.data)

@routes.route("/api/config", methods=["POST"])
def set_config():
  data = request.get_json()
  if data:
    _config.set_many(data)
    return jsonify({"status": "ok"})
  return jsonify({"status": "error"}), 400

@routes.route("/api/history")
def get_history():
  limit = request.args.get("limit", 100, type=int)
  offset = request.args.get("offset", 0, type=int)
  search = request.args.get("search")
  rows = _logger.get_history(limit=limit, offset=offset, search=search)
  return jsonify(rows)

@routes.route("/api/stats")
def get_stats():
  return jsonify(_logger.get_stats())

@routes.route("/api/location")
def get_location():
  if _location:
    lat, lon = _location.get()
    return jsonify({"lat": lat, "lon": lon})
  return jsonify({"lat": 0, "lon": 0})

@routes.route("/api/status")
def get_status():
  lat, lon = (0, 0)
  if _location:
    lat, lon = _location.get()
  return jsonify({
    "camera": _camera.is_opened if _camera else False,
    "api_key": bool(_config.get("openrouter_api_key")),
    "location": {"lat": lat, "lon": lon} if _config.get("location_auto") else {"manual": True, "lat": _config.get("location_lat"), "lon": _config.get("location_lon")},
    "model": _config.get("openrouter_model"),
    "stats": _logger.get_stats() if _logger else {},
  })
