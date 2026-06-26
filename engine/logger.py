import sqlite3, os, threading, time
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
        plate TEXT,
        timestamp TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        image_path TEXT,
        vehicle_info TEXT,
        raw_ai_response TEXT,
        ai_label TEXT DEFAULT 'unknown',
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
    try:
      self.conn.execute("ALTER TABLE plates ADD COLUMN ai_label TEXT DEFAULT 'unknown'")
    except:
      pass
    try:
      self.conn.execute("ALTER TABLE plates RENAME TO plates_old")
      self.conn.execute("CREATE TABLE plates (id INTEGER PRIMARY KEY AUTOINCREMENT, plate TEXT, timestamp TEXT NOT NULL, latitude REAL, longitude REAL, image_path TEXT, vehicle_info TEXT, raw_ai_response TEXT, ai_label TEXT DEFAULT 'unknown', created_at TEXT DEFAULT (datetime('now')))")
      self.conn.execute("INSERT INTO plates (id, plate, timestamp, latitude, longitude, image_path, vehicle_info, raw_ai_response, ai_label, created_at) SELECT id, plate, timestamp, latitude, longitude, image_path, vehicle_info, raw_ai_response, COALESCE(ai_label, 'unknown'), created_at FROM plates_old")
      self.conn.execute("DROP TABLE plates_old")
      self.conn.commit()
    except:
      self.conn.rollback()
    self.conn.commit()

  def is_duplicate(self, plate, window_seconds=None):
    if window_seconds is None:
      window_seconds = self.config.get("dedup_seconds", 60)
    with self.lock:
      cur = self.conn.execute(
        "SELECT COUNT(*) FROM plates WHERE plate = ? AND created_at > datetime('now', ?)",
        (plate, f"-{window_seconds} seconds")
      )
      return cur.fetchone()[0] > 0

  def log(self, plate=None, lat=None, lon=None, image_path=None, vehicle_info=None, raw_ai=None, ai_label="unknown"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}Z"
    with self.lock:
      cur = self.conn.execute(
        "INSERT INTO plates (plate, timestamp, latitude, longitude, image_path, vehicle_info, raw_ai_response, ai_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (plate, ts, lat, lon, image_path, vehicle_info, raw_ai, ai_label)
      )
      self.conn.commit()
      row_id = cur.lastrowid
    return ts, row_id

  def get_history(self, limit=100, offset=0, search=None, ai_label=None):
    with self.lock:
      clauses = []
      params = []
      if search:
        clauses.append("plate LIKE ?")
        params.append(f"%{search}%")
      if ai_label:
        clauses.append("ai_label = ?")
        params.append(ai_label)
      where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
      cur = self.conn.execute(
        f"SELECT * FROM plates{where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
      )
      rows = cur.fetchall()
      cols = [d[0] for d in cur.description]
      return [dict(zip(cols, r)) for r in rows]

  def get_known_plates(self, limit=50):
    with self.lock:
      cur = self.conn.execute(
        "SELECT DISTINCT plate FROM plates WHERE plate IS NOT NULL AND plate != 'UNKNOWN' ORDER BY id DESC LIMIT ?", (limit,)
      )
      return [r[0] for r in cur.fetchall()]

  def get_stats(self):
    with self.lock:
      today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
      total = self.conn.execute("SELECT COUNT(*) FROM plates").fetchone()[0]
      today_count = self.conn.execute(
        "SELECT COUNT(*) FROM plates WHERE date(created_at) = ?", (today,)
      ).fetchone()[0]
      unique = self.conn.execute(
        "SELECT COUNT(DISTINCT plate) FROM plates WHERE plate IS NOT NULL"
      ).fetchone()[0]
      car_count = self.conn.execute(
        "SELECT COUNT(*) FROM plates WHERE ai_label = 'car'"
      ).fetchone()[0]
      non_car_count = self.conn.execute(
        "SELECT COUNT(*) FROM plates WHERE ai_label = 'non_car'"
      ).fetchone()[0]
      error_count = self.conn.execute(
        "SELECT COUNT(*) FROM plates WHERE ai_label = 'error'"
      ).fetchone()[0]
      return {"total": total, "today": today_count, "unique": unique, "cars": car_count, "non_cars": non_car_count, "errors": error_count}

  def delete_by_ids(self, ids):
    if not ids:
      return 0
    placeholders = ",".join("?" for _ in ids)
    with self.lock:
      cur = self.conn.execute(
        f"DELETE FROM plates WHERE id IN ({placeholders})", ids
      )
      self.conn.commit()
      return cur.rowcount

  def delete_all(self):
    with self.lock:
      cur = self.conn.execute("DELETE FROM plates")
      self.conn.commit()
      return cur.rowcount

  def close(self):
    self.conn.close()
