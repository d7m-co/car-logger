from flask_socketio import emit
from flask import request

def register_socketio(socketio, logger):
  @socketio.on("connect")
  def handle_connect():
    pass

  @socketio.on("disconnect")
  def handle_disconnect():
    pass

  def broadcast_detection(data):
    socketio.emit("new_detection", data)
