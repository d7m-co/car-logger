document.addEventListener("DOMContentLoaded", function() {
  const socket = tryConnectSocket();
  const list = document.getElementById("detections-list");
  const totalCount = document.getElementById("total-count");
  const statToday = document.getElementById("stat-today");
  const statTotal = document.getElementById("stat-total");
  const statUnique = document.getElementById("stat-unique");
  const badgeCars = document.getElementById("badge-cars");
  const indCamera = document.getElementById("indicator-camera");
  const indAI = document.getElementById("indicator-ai");
  const indLoc = document.getElementById("indicator-loc");

  let detectionCount = 0;

  function tryConnectSocket() {
    if (typeof io !== "undefined") {
      var s = io();
      s.on("new_detection", function(data) {
        addDetection(data);
      });
      return s;
    }
    return null;
  }

  function addDetection(data) {
    detectionCount++;
    totalCount.textContent = detectionCount;

    var item = document.createElement("div");
    item.className = "detection-item";
    item.innerHTML =
      '<div class="plate">' + (data.plate || "UNKNOWN") + '</div>' +
      '<div class="info">' +
        '<div class="vehicle">' + (data.vehicle_info || "") + '</div>' +
        '<div class="time">' + ((data.timestamp || "").split(".")[0].replace("T", " ") || "") + '</div>' +
      '</div>';

    list.insertBefore(item, list.firstChild);
    var empty = list.querySelector(".empty-state");
    if (empty) empty.remove();

    while (list.children.length > 100) {
      list.removeChild(list.lastChild);
    }
  }

  async function pollStatus() {
    try {
      var r = await fetch("/api/status");
      var s = await r.json();

      if (s.camera) {
        indCamera.innerHTML = "📷 <span>Camera ✅</span>";
        indCamera.className = "indicator active";
      } else {
        indCamera.innerHTML = "📷 <span>Camera ❌</span>";
        indCamera.className = "indicator error";
      }

      if (s.api_key) {
        indAI.innerHTML = "🤖 <span>AI: " + ((s.model || "").split("/").pop() || "ready") + "</span>";
        indAI.className = "indicator active";
      } else {
        indAI.innerHTML = "🤖 <span>No API key</span>";
        indAI.className = "indicator error";
      }

      if (s.location) {
        var loc = s.location;
        var lat = loc.lat || 0;
        var lon = loc.lon || 0;
        if (lat && lon) {
          indLoc.innerHTML = "📍 <span>" + lat.toFixed(4) + ", " + lon.toFixed(4) + "</span>";
        } else {
          indLoc.innerHTML = "📍 <span>Unknown</span>";
        }
        indLoc.className = "indicator active";
      }

      var stats = s.stats || {};
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
