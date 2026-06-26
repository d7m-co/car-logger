import json, os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
  "openrouter_api_key": "",
  "openrouter_model": "openrouter/free",
  "camera_id": 0,
  "resolution": [720, 480],
  "fps_motion": 10,
  "fps_idle": 2,
  "idle_timeout": 5,
  "detection_zone": [0, 0, 100, 100],
  "sensitivity": 50,
  "min_car_area": 100,
  "dedup_seconds": 60,
  "location_auto": True,
  "location_lat": 0.0,
  "location_lon": 0.0,
  "location_refresh_minutes": 10,
  "server_port": 5000,
  "save_snaps": True,
  "snap_quality": 85,
  "db_path": "data/plates.db",
  "snaps_dir": "data/snaps",
  "auto_start": False,
}

class Config:
  def __init__(self):
    self.data = DEFAULTS.copy()
    self._load()

  def _load(self):
    if os.path.exists(CONFIG_PATH):
      with open(CONFIG_PATH) as f:
        self.data.update(json.load(f))
    self._save()

  def _save(self):
    os.makedirs(os.path.dirname(CONFIG_PATH) or ".", exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
      json.dump(self.data, f, indent=2)

  def get(self, key, default=None):
    return self.data.get(key, default)

  def set(self, key, value):
    self.data[key] = value
    self._save()

  def set_many(self, pairs):
    self.data.update(pairs)
    self._save()

  @property
  def api_key_set(self):
    return bool(self.data.get("openrouter_api_key"))

  @property
  def detection_zone_percent(self):
    return self.data.get("detection_zone", [0, 0, 100, 100])

  @property
  def location(self):
    if self.data.get("location_auto"):
      return None
    return (self.data.get("location_lat"), self.data.get("location_lon"))
