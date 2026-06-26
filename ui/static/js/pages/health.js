(function () {
  "use strict";

  function fillHealth() {
    // Set up DOM targets but leave skeletons in place until data arrives
    document.querySelectorAll("#health-grid .skeleton").forEach(function (s) {
      var p = s.parentElement;
      if (p.id === "h-camera") {
        if (!document.getElementById("h-camera-dot")) {
          s.insertAdjacentHTML(
            "beforebegin",
            '<span class="status-dot" id="h-camera-dot"></span> <span id="h-camera-text">--</span>'
          );
        }
        return;
      }
      if (p.id === "h-api") {
        if (!document.getElementById("h-api-dot")) {
          s.insertAdjacentHTML(
            "beforebegin",
            '<span class="status-dot" id="h-api-dot"></span> <span id="h-api-text">--</span>'
          );
        }
        return;
      }
    });
  }

  async function loadHealth() {
    fillHealth();
    try {
      const r = await fetch("/api/health");
      const h = await r.json();

      var u = h.uptime;
      var dd = Math.floor(u / 86400);
      var hh = Math.floor((u % 86400) / 3600);
      var mm = Math.floor((u % 3600) / 60);
      var ss = u % 60;
      var uptimeStr = dd > 0 ? dd + "d " : "";
      uptimeStr +=
        String(hh).padStart(2, "0") +
        ":" +
        String(mm).padStart(2, "0") +
        ":" +
        String(ss).padStart(2, "0");
      document.getElementById("h-uptime").textContent = uptimeStr;

      var camDot = document.getElementById("h-camera-dot");
      var camText = document.getElementById("h-camera-text");
      if (h.camera.connected) {
        camDot.className = "status-dot green";
        camText.textContent = "Connected";
      } else {
        camDot.className = "status-dot red";
        camText.textContent = "Disconnected";
      }

      var apiDot = document.getElementById("h-api-dot");
      var apiText = document.getElementById("h-api-text");
      if (h.api.key_set) {
        apiDot.className = "status-dot green";
        var curModel = window.CarLogger.shortModelName(
          h.api.models && h.api.models[h.api.model_idx]
        );
        apiText.textContent = curModel
          ? "Auto-rotate (" + curModel + ")"
          : "Auto-rotate (" + (h.api.models || []).length + " models)";
      } else {
        apiDot.className = "status-dot yellow";
        apiText.textContent = "No key";
      }

      var db = h.database;
      var dbSize = db.size_bytes;
      var dbStr =
        dbSize > 1048576
          ? (dbSize / 1048576).toFixed(1) + " MB"
          : (dbSize / 1024).toFixed(1) + " KB";
      document.getElementById("h-db").textContent = db.rows + " rows, " + dbStr;

      var disk = h.disk;
      var freeGb = (disk.free_bytes / 1073741824).toFixed(1);
      var totalGb = (disk.total_bytes / 1073741824).toFixed(1);
      document.getElementById("h-disk").textContent =
        freeGb + " GB free / " + totalGb + " GB (" + disk.percent_used + "% used)";

      var mem = h.memory;
      var freeMem = (mem.available_bytes / 1073741824).toFixed(1);
      var totalMem = (mem.total_bytes / 1073741824).toFixed(1);
      document.getElementById("h-memory").textContent =
        mem.percent + "% used (" + freeMem + " GB free / " + totalMem + " GB)";

      document.getElementById("h-cpu").textContent = h.cpu_percent + "%";

      var loc = h.location;
      if (loc.lat && loc.lon) {
        document.getElementById("h-location").textContent =
          loc.lat.toFixed(4) + ", " + loc.lon.toFixed(4);
      } else {
        document.getElementById("h-location").textContent = "Unknown";
      }

      var stats = h.stats || {};
      document.getElementById("h-today").textContent = stats.today || 0;
      document.getElementById("h-cars").textContent = stats.cars || 0;
      document.getElementById("h-non-cars").textContent = stats.non_cars || 0;
      document.getElementById("h-errors").textContent = stats.errors || 0;
      document.getElementById("h-unique").textContent = stats.unique || 0;

      var q = h.ai_queue || 0;
      document.getElementById("h-ai-queue").textContent = q + " queued";
    } catch (e) {
      document.getElementById("health-loading").textContent =
        "Failed to load health data";
    }
  }

  loadHealth();
  setInterval(loadHealth, 10000);
  window.CarLogger.startStatusPoll(5000);
})();
