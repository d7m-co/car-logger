document.addEventListener("DOMContentLoaded", function() {
  const socket = io();
  const feed = document.getElementById("live-feed");
  const list = document.getElementById("detections-list");
  const totalCount = document.getElementById("total-count");
  const statToday = document.getElementById("stat-today");
  const statTotal = document.getElementById("stat-total");
  const statUnique = document.getElementById("stat-unique");
  const badgeCars = document.getElementById("badge-cars");
  const badgeStatus = document.getElementById("badge-status");
  const indCamera = document.getElementById("indicator-camera");
  const indAI = document.getElementById("indicator-ai");
  const indLoc = document.getElementById("indicator-loc");

  let detectionCount = 0;

  socket.on("new_detection", function(data) {
    detectionCount++;
    totalCount.textContent = detectionCount;

    const item = document.createElement("div");
    item.className = "detection-item";
    item.innerHTML =
      '<div class="plate">' + data.plate + '</div>' +
      '<div class="info">' +
        '<div class="vehicle">' + (data.vehicle_info || "") + '</div>' +
        '<div class="time">' + (data.timestamp || "").split(".")[0].replace("T", " ") + '</div>' +
      '</div>';

    list.insertBefore(item, list.firstChild);
    list.querySelector(".empty-state")?.remove();

    while (list.children.length > 100) {
      list.removeChild(list.lastChild);
    }
  });

  async function pollStatus() {
    try {
      const r = await fetch("/api/status");
      const s = await r.json();

      if (s.camera) {
        indCamera.innerHTML = "📷 <span>Camera ✅</span>";
        indCamera.className = "indicator active";
      } else {
        indCamera.innerHTML = "📷 <span>Camera ❌</span>";
        indCamera.className = "indicator error";
      }

      if (s.api_key) {
        indAI.innerHTML = "🤖 <span>AI: " + (s.model || "").split("/").pop() + "</span>";
        indAI.className = "indicator active";
      } else {
        indAI.innerHTML = "🤖 <span>No API key</span>";
        indAI.className = "indicator error";
      }

      if (s.location) {
        const loc = s.location;
        const lat = loc.lat || loc.manual_lat;
        const lon = loc.lon || loc.manual_lon;
        indLoc.innerHTML = "📍 <span>" + (lat ? lat.toFixed(4) + ", " + lon.toFixed(4) : "Unknown") + "</span>";
        indLoc.className = "indicator active";
      }

      const stats = s.stats || {};
      statToday.textContent = stats.today || 0;
      statTotal.textContent = stats.total || 0;
      statUnique.textContent = stats.unique || 0;
      badgeCars.innerHTML = "🚘 " + (stats.today || 0);

    } catch (e) {
      indCamera.className = "indicator error";
    }
  }

  setInterval(pollStatus, 5000);
  pollStatus();
});
