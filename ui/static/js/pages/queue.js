(function () {
  "use strict";

  var term = document.getElementById("term");
  function id_(s) {
    return document.getElementById(s);
  }
  var lastDone = 0,
    lastTime = Date.now();



  function render(reqs) {
    var html =
      '<div class="line hdr"><span class="p">$</span> tail -f /var/log/ai-queue — ' +
      reqs.length +
      " entries</div>";
    var q = 0,
      p = 0,
      d = 0,
      e = 0,
      s = 0,
      ret = 0;
    for (var i = 0; i < reqs.length; i++) {
      var r = reqs[i];
      if (r.status === "queued") q++;
      else if (r.status === "processing") p++;
      else if (r.status === "completed") d++;
      else if (r.status === "error") e++;
      else if (r.status === "skipped") s++;
      else if (r.status === "retrying") ret++;

      var detail = "";
      if (r.status === "completed" && r.result) {
        if (r.result.is_car) {
          detail = "🚗 " + window.CarLogger.escHtml(r.result.plate || "UNKNOWN");
          if (r.result.color) detail += " " + window.CarLogger.escHtml(r.result.color);
          if (r.result.make) detail += " " + window.CarLogger.escHtml(r.result.make);
          detail += " [" + window.CarLogger.escHtml(r.result.confidence || "none") + "]";
        } else {
          detail = "🚫 NON-CAR";
        }
      } else if (r.status === "skipped" && r.result) {
        detail = "⏭ SKIP " + window.CarLogger.escHtml(r.error || "");
      } else if (r.status === "retrying") {
        detail = "🔄 RETRY #" + (parseInt(r.retries) || 1) + " " + window.CarLogger.escHtml(r.error || "");
      } else if (r.status === "error") {
        detail = window.CarLogger.escHtml(r.error || "API request failed");
      }

      var elapsed = "";
      if (r.started_at) {
        var end = r.completed_at || Date.now() / 1000;
        elapsed = (end - r.started_at).toFixed(1) + "s";
      }

      html += '<div class="line">';
    html += '  <span class="ts">' + window.CarLogger.fmtTime(r.queued_at) + "</span>";
    html += '  <span class="id">#' + r.id + "</span>";
    html += '  <span class="' + r.status + '">' + r.status + "</span>";
    if (detail) html += "  <span>" + detail + "</span>";
    if (elapsed) html += '  <span class="ts">(' + elapsed + ")</span>";
    html += "</div>";
  }
  if (reqs.length === 0) {
    html += '<div class="idle-msg">⏳ queue idle — no AI requests yet</div>';
  }
  term.innerHTML = html;
  term.scrollTop = term.scrollHeight;
  id_("qs-queued").textContent = q;
  id_("qs-processing").textContent = p;
  id_("qs-done").textContent = d;
  id_("qs-errs").textContent = e;
  id_("qs-retrying").textContent = ret;
  id_("qs-skipped").textContent = s;
    id_("q-last-refresh").textContent =
      "last refresh: " + window.CarLogger.fmtTime(Date.now() / 1000);
    // throughput speed
    var now = Date.now();
    var doneDelta = d + e + s - lastDone;
    var timeDelta = (now - lastTime) / 1000;
    if (doneDelta > 0 && timeDelta > 0) {
      var perMin = Math.round((doneDelta / timeDelta) * 60);
      id_("qs-speed").textContent = perMin + "/min";
    }
    lastDone = d + e + s;
    lastTime = now;
  }

  function poll() {
    fetch("/api/queue")
      .then(function (r) {
        return r.json();
      })
      .then(render)
      .catch(function () {});
    setTimeout(poll, 2000);
  }
  poll();
  window.CarLogger.startStatusPoll(5000);
})();
