import sqlite3, os, time, threading
from datetime import datetime, timezone

class Logger:
  def __init__(self, config):
    self.config = config
    db_path = config.get("db_path", "data/plates.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    self.conn = sqlite3.connect(db_path, check_same_thread=False)
    self.lock = threading.Lock()
    self._create_tables()

  def _create_tables(self):
    self.conn.execute("""
      CREATE TABLE IF NOT EXISTS plates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        image_path TEXT,
        vehicle_info TEXT,
        raw_ai_response TEXT,
        created_at TEXT DEFAULT (datetime('now'))
      )
    """)
    self.conn.execute("""
      CREATE TABLE IF NOT EXISTS config_log (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
      )
    """)
    self.conn.commit()

  def is_duplicate(self, plate, window_seconds=None):
    if window_seconds is None:
      window_seconds = self.config.get("dedup_seconds", 60)
    cutoff = datetime.now(timezone.utc).isoformat()
    with self.lock:
      cur = self.conn.execute(
        "SELECT COUNT(*) FROM plates WHERE plate = ? AND timestamp > datetime('now', ?)",
        (plate, f"-{window_seconds} seconds")
      )
      return cur.fetchone()[0] > 0

  def log(self, plate, lat=None, lon=None, image_path=None, vehicle_info=None, raw_ai=None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    with self.lock:
      self.conn.execute(
        "INSERT INTO plates (plate, timestamp, latitude, longitude, image_path, vehicle_info, raw_ai_response) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (plate, ts, lat, lon, image_path, vehicle_info, raw_ai)
      )
      self.conn.commit()
    return ts

  def get_history(self, limit=100, offset=0, search=None):
    with self.lock:
      if search:
        cur = self.conn.execute(
          "SELECT * FROM plates WHERE plate LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
          (f"%{search}%", limit, offset)
        )
      else:
        cur = self.conn.execute(
          "SELECT * FROM plates ORDER BY id DESC LIMIT ? OFFSET ?",
          (limit, offset)
        )
      rows = cur.fetchall()
      cols = [d[0] for d in cur.description]
      return [dict(zip(cols, r)) for r in rows]

  def get_stats(self):
    with self.lock:
      today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
      total = self.conn.execute("SELECT COUNT(*) FROM plates").fetchone()[0]
      today_count = self.conn.execute(
        "SELECT COUNT(*) FROM plates WHERE date(created_at) = ?", (today,)
      ).fetchone()[0]
      unique = self.conn.execute(
        "SELECT COUNT(DISTINCT plate) FROM plates"
      ).fetchone()[0]
      return {"total": total, "today": today_count, "unique": unique}

  def close(self):
    self.conn.close()
