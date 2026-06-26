(function () {
  "use strict";

  window.CarLogger = window.CarLogger || {};

  var timer = null;

  function updateTopbarIndicators(s) {
    var q = s.ai_queue || 0;
    var el = document.getElementById("h-indicator-queue");
    var aiEl = document.getElementById("h-indicator-ai");

    if (el) {
      if (q > 0) {
        el.style.display = "inline-flex";
        el.innerHTML =
          '<span aria-hidden="true">📨</span> <span>' + q + " queued</span>";
        el.className = "indicator active";
      } else {
        el.style.display = "none";
      }
    }

    if (aiEl) {
      var ok = s.api_key;
      var curModel = window.CarLogger.shortModelName(
        s.models && s.models[s.model_idx]
      );
      var label = curModel
        ? "AI: " + curModel
        : ok
        ? "AI ready"
        : "AI key missing";
      aiEl.innerHTML = "🤖 <span>" + label + "</span>";
      aiEl.className = "indicator" + (ok ? " active" : " error");
    }
  }

  function tick() {
    fetch("/api/status")
      .then(function (r) {
        return r.json();
      })
      .then(updateTopbarIndicators)
      .catch(function () {});
  }

  window.CarLogger.startStatusPoll = function startStatusPoll(intervalMs) {
    if (timer) return;
    intervalMs = intervalMs || 5000;
    tick();
    timer = setInterval(tick, intervalMs);
  };

  window.CarLogger.stopStatusPoll = function stopStatusPoll() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  };
})();
