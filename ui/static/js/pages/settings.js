(function () {
  "use strict";

  var getEl = window.CarLogger.getEl;
  var _configLoaded = false;

  async function loadConfig() {
    try {
      const r = await fetch("/api/config");
      if (!r.ok) throw new Error("HTTP " + r.status);
      const cfg = await r.json();
      getEl("go-api-key").value = cfg.opencode_go_api_key || "";
      getEl("or-api-key").value = cfg.openrouter_api_key || "";
      getEl("sensitivity").value = cfg.sensitivity;
      getEl("sens-label").textContent = cfg.sensitivity;
      getEl("min-car-area").value = cfg.min_car_area;
      getEl("dedup-seconds").value = cfg.dedup_seconds;
      getEl("resolution").value = cfg.resolution.join(",");
      getEl("location-auto").checked = cfg.location_auto;
      getEl("loc-lat").value = cfg.location_lat;
      getEl("loc-lon").value = cfg.location_lon;
      getEl("server-port").value = cfg.server_port;
      toggleManualLoc();
      _configLoaded = true;
      document.querySelectorAll(".settings-page [disabled]").forEach(function (el) {
        el.disabled = false;
      });
      getEl("btn-save").disabled = false;
    } catch (e) {
      showMsg("Failed to load settings: " + e.message, "error");
    }
  }

  function toggleManualLoc() {
    getEl("manual-loc").style.display = getEl("location-auto").checked
      ? "none"
      : "block";
  }

  getEl("location-auto").addEventListener("change", toggleManualLoc);

  getEl("sensitivity").addEventListener("input", function () {
    getEl("sens-label").textContent = this.value;
  });

  function readVal(id, fallback) {
    var v = parseFloat(getEl(id).value);
    return isNaN(v) ? fallback : v;
  }

  var saving = false;

  getEl("btn-save").addEventListener("click", async function () {
    if (saving) return;
    saving = true;
    var btn = getEl("btn-save");
    btn.textContent = "Saving...";
    btn.disabled = true;

    var body = {
      opencode_go_api_key: getEl("go-api-key").value,
      openrouter_api_key: getEl("or-api-key").value,
      sensitivity: parseInt(getEl("sensitivity").value),
      min_car_area: readVal("min-car-area", 500),
      dedup_seconds: readVal("dedup-seconds", 60),
      resolution: getEl("resolution").value.split(",").map(Number),
      location_auto: getEl("location-auto").checked,
      location_lat: readVal("loc-lat", 0),
      location_lon: readVal("loc-lon", 0),
      server_port: readVal("server-port", 5000),
    };

    try {
      var r = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        showMsg("Saved successfully", "ok");
      } else {
        var emsg = "Save failed";
        try {
          var ej = await r.json();
          if (ej.message) emsg = ej.message;
        } catch (e) {}
        showMsg(emsg, "error");
      }
    } catch (e) {
      showMsg("Save failed: " + e.message, "error");
    }

    saving = false;
    btn.textContent = "Save";
    btn.disabled = false;
  });

  function showMsg(text, type) {
    var msg = getEl("save-msg");
    msg.textContent = text;
    msg.className = "save-msg " + (type === "ok" ? "ok" : "err");
    setTimeout(function () {
      msg.textContent = "";
      msg.className = "save-msg";
    }, 5000);
  }

loadConfig();
window.CarLogger.startStatusPoll(5000);
})();
