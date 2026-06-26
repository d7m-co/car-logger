import subprocess, json, threading, time

class Location:
  def __init__(self, config):
    self.config = config
    self.lat = config.get("location_lat", 0.0)
    self.lon = config.get("location_lon", 0.0)
    self._lock = threading.Lock()
    self._last_refresh = 0
    if config.get("location_auto"):
      self._refresh()

  def _geoclue_get(self):
    try:
      r = subprocess.run(
        ["gdbus", "call", "--system", "--dest", "org.freedesktop.GeoClue2",
         "--object-path", "/org/freedesktop/GeoClue2/Manager",
         "--method", "org.freedesktop.GeoClue2.Manager.GetClient"],
        capture_output=True, text=True, timeout=5
      )
      if r.returncode != 0:
        return None
      obj_path = r.stdout.strip().split()[-1].strip("',")
      r = subprocess.run(
        ["gdbus", "call", "--system", "--dest", "org.freedesktop.GeoClue2",
         "--object-path", obj_path,
         "--method", "org.freedesktop.GeoClue2.Client.Start"],
        capture_output=True, text=True, timeout=10
      )
      r = subprocess.run(
        ["gdbus", "call", "--system", "--dest", "org.freedesktop.GeoClue2",
         "--object-path", obj_path,
         "--method", "org.freedesktop.GeoClue2.Client.GetLocation"],
        capture_output=True, text=True, timeout=5
      )
      loc_path = r.stdout.strip().split()[-1].strip("',")
      r = subprocess.run(
        ["gdbus", "call", "--system", "--dest", "org.freedesktop.GeoClue2",
         "--object-path", loc_path,
         "--method", "org.freedesktop.GeoClue2.Location.GetProperties"],
        capture_output=True, text=True, timeout=5
      )
      out = r.stdout
      lat = float(out.split("Latitude:")[1].split("\n")[0].strip().strip("' ,"))
      lon = float(out.split("Longitude:")[1].split("\n")[0].strip().strip("' ,"))
      return lat, lon
    except Exception:
      return None

  def _ip_geolocate(self):
    try:
      r = requests.get("http://ip-api.com/json", timeout=5)
      data = r.json()
      if data.get("status") == "success":
        return data["lat"], data["lon"]
    except Exception:
      pass
    return None

  def _refresh(self):
    loc = self._geoclue_get()
    if loc is None:
      loc = self._ip_geolocate()
    if loc:
      with self._lock:
        self.lat, self.lon = loc
        if self.config.get("location_auto"):
          self.config.set_many({"location_lat": self.lat, "location_lon": self.lon})
    self._last_refresh = time.time()

  def get(self):
    if self.config.get("location_auto"):
      interval = self.config.get("location_refresh_minutes", 10) * 60
      if time.time() - self._last_refresh > interval:
        threading.Thread(target=self._refresh, daemon=True).start()
    with self._lock:
      return self.lat, self.lon
