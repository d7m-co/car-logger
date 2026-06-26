var audioCtx = null;

function getAudioCtx() {
  if (!audioCtx) {
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

function playChime() {
  var ctx = getAudioCtx();
  if (!ctx) return;
  try {
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    osc.type = "sine";
    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.35);
  } catch(e) {}
}

function retryFeed() {
  var img = document.getElementById("live-feed");
  var err = document.querySelector(".feed-error");
  if (img) {
    img.src = "/video_feed?" + Date.now();
    img.style.display = "block";
    if (err) err.style.display = "none";
  }
}

function showHelp() {
  var existing = document.getElementById("shortcuts-help");
  if (existing) { existing.remove(); return; }
  var div = document.createElement("div");
  div.id = "shortcuts-help";
  div.className = "shortcuts-overlay";
  div.innerHTML =
    '<div class="shortcuts-panel"><div class="shortcuts-header"><span class="shortcuts-title">Help &amp; Shortcuts</span><button class="shortcuts-close" id="shortcuts-close">&times;</button></div>' +
    '<div style="margin-bottom:16px"><strong style="font-size:14px">Keyboard shortcuts</strong></div>' +
    '<div class="shortcuts-grid" style="margin-bottom:20px">' +
    '<div class="shortcut"><kbd>s</kbd> Settings</div>' +
    '<div class="shortcut"><kbd>h</kbd> History</div>' +
    '<div class="shortcut"><kbd>l</kbd> Health</div>' +
    '<div class="shortcut"><kbd>r</kbd> Reload feed</div>' +
    '<div class="shortcut"><kbd>j</kbd> Next detection</div>' +
    '<div class="shortcut"><kbd>k</kbd> Prev detection</div>' +
    '<div class="shortcut"><kbd>?</kbd> This help</div>' +
    '<div class="shortcut"><kbd>Esc</kbd> Close modal</div>' +
    '</div>' +
    '<div style="margin-bottom:12px"><strong style="font-size:14px">Getting started</strong></div>' +
    '<div style="font-size:13px;color:var(--text2);line-height:1.6">' +
    '<p style="margin-bottom:8px"><strong>1. Add your API key</strong> &mdash; Go to Settings and paste your OpenRouter key to enable license plate reading.</p>' +
    '<p style="margin-bottom:8px"><strong>2. Position the camera</strong> &mdash; Aim it at the street or driveway where cars pass.</p>' +
    '<p style="margin-bottom:8px"><strong>3. Tune detection</strong> &mdash; Adjust Sensitivity and Min Car Size in Settings if you get too many or too few detections.</p>' +
    '<p style="margin-bottom:8px"><strong>4. Review history</strong> &mdash; All plates are logged with timestamps and location. Export to CSV from the History page.</p>' +
    '</div>' +
    '<div style="border-top:1px solid var(--border);padding-top:12px;margin-top:4px;font-size:12px;color:var(--text2)">' +
    'System status indicators: 📷 Camera, 🤖 AI, 📍 Location, 🔌 WebSocket. Hover or tap any indicator for details.' +
    '</div></div>';
  document.body.appendChild(div);
  document.getElementById("shortcuts-close").addEventListener("click", function() { div.remove(); });
  div.addEventListener("click", function(e) { if (e.target === div) div.remove(); });
}

document.addEventListener("DOMContentLoaded", function() {
  const list = document.getElementById("detections-list");
  const totalCount = document.getElementById("total-count");
  const statToday = document.getElementById("stat-today");
  const statTotal = document.getElementById("stat-total");
  const statUnique = document.getElementById("stat-unique");
  const badgeCars = document.getElementById("badge-cars");
  const indCamera = document.getElementById("indicator-camera");
  const indAI = document.getElementById("indicator-ai");
  const indQueue = document.getElementById("indicator-queue");
  const indLoc = document.getElementById("indicator-loc");
  const indWs = document.getElementById("indicator-ws");
  const feedImg = document.getElementById("live-feed");
  const feedContainer = document.getElementById("feed-container");
  const modal = document.getElementById("detail-modal");
  const modalClose = document.getElementById("modal-close");

  var detectionCount = 0;
  var wsConnected = false;

  // Video feed error handling
  var feedError = document.createElement("div");
  feedError.className = "feed-error";
  feedError.innerHTML = 'Camera feed unavailable. Check the camera connection and try again.&nbsp; <button class="btn btn-tiny" onclick="retryFeed()">Retry</button>';
  feedError.style.display = "none";

  feedImg.addEventListener("error", function() {
    feedImg.style.display = "none";
    feedError.style.display = "flex";
  });
  feedImg.addEventListener("load", function() {
    feedImg.style.display = "block";
    feedError.style.display = "none";
  });
  feedContainer.appendChild(feedError);

  // Keyboard shortcuts
  document.addEventListener("keydown", function(e) {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
    if (e.key === "?") { e.preventDefault(); showHelp(); }
    if (e.key === "s" || e.key === "S") { window.location.href = "/settings"; }
    if (e.key === "h" || e.key === "H") { window.location.href = "/history"; }
    if (e.key === "l" || e.key === "L") { window.location.href = "/health"; }
    if (e.key === "r" || e.key === "R") { retryFeed(); }
    if (e.key === "j" || e.key === "J") { var s = document.querySelector(".detection-item.selected"); if (s) s.classList.remove("selected"); var n = s ? s.nextElementSibling : document.querySelector(".detection-item"); if (n) { n.classList.add("selected"); n.scrollIntoView({block:"nearest"}); n.click(); } }
    if (e.key === "k" || e.key === "K") { var t = document.querySelector(".detection-item.selected"); if (t) t.classList.remove("selected"); var p = t ? t.previousElementSibling : null; if (p) { p.classList.add("selected"); p.scrollIntoView({block:"nearest"}); p.click(); } }
  });

  var socket = tryConnectSocket();

  function tryConnectSocket() {
    if (typeof io === "undefined") return null;
    var s = io();
    s.on("connect", function() {
      wsConnected = true;
      updateWsIndicator("connected");
    });
    s.on("disconnect", function() {
      wsConnected = false;
      updateWsIndicator("disconnected");
    });
    s.on("reconnect_attempt", function() {
      updateWsIndicator("reconnecting");
    });
    s.on("new_detection", function(data) {
      addDetection(data);
      playChime();
    });
    return s;
  }

  function updateWsIndicator(state) {
    if (!indWs) return;
    if (state === "connected") {
      indWs.innerHTML = "🔌 <span>Live</span>";
      indWs.className = "indicator active";
    } else if (state === "reconnecting") {
      indWs.innerHTML = "🔌 <span>Reconnecting...</span>";
      indWs.className = "indicator error";
    } else {
      indWs.innerHTML = "🔌 <span>Disconnected</span>";
      indWs.className = "indicator error";
    }
  }

  function aiLabelHtml(label) {
    if (label === "car") return '<span class="badge badge-car">🚗 Car</span>';
    if (label === "non_car") return '<span class="badge badge-non-car">🚫 Not a car</span>';
    if (label === "error") return '<span class="badge badge-error">⚠ AI error</span>';
    return '<span class="badge badge-unknown">--</span>';
  }

  function addDetection(data) {
    detectionCount++;
    totalCount.textContent = detectionCount;

    var item = document.createElement("div");
    item.className = "detection-item";
    item.dataset.plate = data.plate || "";
    item.dataset.time = data.timestamp || "";
    item.dataset.vehicle = data.vehicle_info || "";
    item.dataset.image = data.image_path || "";
    item.dataset.lat = data.lat || 0;
    item.dataset.lon = data.lon || 0;
    item.dataset.id = data.id || "";
    item.dataset.aiLabel = data.ai_label || "";
    item.dataset.confidence = data.confidence || "";
    item.dataset.color = data.color || "";
    item.dataset.make = data.make || "";
    item.dataset.rawAi = data.raw_ai || "";
    item.innerHTML =
      '<div class="plate">' + (data.plate || aiLabelHtml(data.ai_label)) + '</div>' +
      '<div class="info">' +
        '<div class="vehicle">' + (data.vehicle_info || aiLabelHtml(data.ai_label)) + '</div>' +
        '<div class="time">' + ((data.timestamp || "").split(".")[0].replace("T", " ") || "") + '</div>' +
      '</div>';

    item.addEventListener("click", function() {
      openModal(this.dataset);
    });

    list.insertBefore(item, list.firstChild);
    var empty = list.querySelector(".empty-state");
    if (empty) empty.remove();

    while (list.children.length > 100) {
      list.removeChild(list.lastChild);
    }
  }

  function openModal(d) {
    document.getElementById("modal-plate").textContent = d.plate || "UNKNOWN";
    document.getElementById("modal-ai-label").innerHTML = aiLabelHtml(d.aiLabel) || "--";
    document.getElementById("modal-confidence").textContent = d.confidence || "--";
    document.getElementById("modal-vehicle").textContent = (d.color && d.color + " " + d.make) || d.vehicle || "--";
    var ts = (d.time || "").split(".")[0].replace("T", " ");
    document.getElementById("modal-time").textContent = ts || "--";
    if (d.lat && d.lon) {
      document.getElementById("modal-location").textContent = parseFloat(d.lat).toFixed(4) + ", " + parseFloat(d.lon).toFixed(4);
    } else {
      document.getElementById("modal-location").textContent = "Unknown";
    }
    document.getElementById("modal-id").textContent = d.id || "--";
    var rawEl = document.getElementById("modal-raw");
    var rawRow = document.getElementById("modal-raw-row");
    if (d.rawai) {
      rawEl.textContent = d.rawai;
      rawRow.style.display = "flex";
    } else {
      rawRow.style.display = "none";
    }

    var img = document.getElementById("modal-image");
    var fallback = document.getElementById("modal-image-fallback");
    if (d.image) {
      img.src = "/snaps/" + d.image;
      img.style.display = "block";
      fallback.style.display = "none";
    } else {
      img.style.display = "none";
      fallback.style.display = "flex";
    }

    modal.showModal();
    document.body.classList.add("modal-open");
  }

  function closeModal() {
    modal.close();
    document.body.classList.remove("modal-open");
  }

  modalClose.addEventListener("click", closeModal);
  modal.addEventListener("click", function(e) {
    if (e.target === modal) closeModal();
  });
  modal.addEventListener("close", function() {
    document.body.classList.remove("modal-open");
  });
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && modal.open) closeModal();
  });

  var statusFailed = false;

  async function pollStatus() {
    try {
      var r = await fetch("/api/status");
      if (!r.ok) throw new Error("Status endpoint returned " + r.status);
      var s = await r.json();
      statusFailed = false;

      if (s.camera) {
        indCamera.innerHTML = "📷 <span>Camera</span>";
        indCamera.className = "indicator active";
      } else {
        indCamera.innerHTML = "📷 <span>Camera offline</span>";
        indCamera.className = "indicator error";
      }

      var modelName = (s.model || "").split("/").pop() || "ready";
      if (s.api_key) {
        indAI.innerHTML = "🤖 <span>AI: " + modelName + "</span>";
        indAI.className = "indicator active";
      } else {
        indAI.innerHTML = "🤖 <span>AI key missing</span>";
        indAI.className = "indicator error";
      }

      var q = s.ai_queue || 0;
      if (q > 0) {
        indQueue.style.display = "inline-flex";
        indQueue.innerHTML = "📨 <span>" + q + " queued</span>";
        indQueue.className = "indicator active";
      } else {
        indQueue.style.display = "none";
      }

      var loc = s.location || {};
      var lat = loc.lat || 0;
      var lon = loc.lon || 0;
      if (lat && lon) {
        indLoc.innerHTML = "📍 <span>" + lat.toFixed(4) + ", " + lon.toFixed(4) + "</span>";
        indLoc.className = "indicator active";
      } else {
        indLoc.innerHTML = "📍 <span>Loc: --</span>";
        indLoc.className = "indicator";
      }

      var stats = s.stats || {};
      statToday.textContent = stats.today || 0;
      statTotal.textContent = stats.total || 0;
      statUnique.textContent = stats.unique || 0;
      badgeCars.innerHTML = "🚘 " + (stats.today || 0);

    } catch (e) {
      indCamera.innerHTML = "📷 <span>Server unreachable</span>";
      indCamera.className = "indicator error";
      indAI.innerHTML = "🤖 <span>Server unreachable</span>";
      indAI.className = "indicator error";
      indLoc.innerHTML = "📍 <span>Server unreachable</span>";
      indLoc.className = "indicator error";
      if (indQueue) indQueue.style.display = "none";
      statusFailed = true;
    }
  }

  pollStatus();
  setInterval(pollStatus, 5000);
});
