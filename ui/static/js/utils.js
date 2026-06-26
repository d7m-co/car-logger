(function () {
  "use strict";

  window.CarLogger = window.CarLogger || {};

  window.CarLogger.getEl = function getEl(id) {
    return document.getElementById(id);
  };

  window.CarLogger.escHtml = function escHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  window.CarLogger.aiLabelHtml = function aiLabelHtml(label) {
    if (label === "car") return '<span class="badge badge-car">🚗 Car</span>';
    if (label === "non_car")
      return '<span class="badge badge-non-car">🚫 Not a car</span>';
    if (label === "error")
      return '<span class="badge badge-error">⚠ AI error</span>';
    return '<span class="badge badge-unknown">--</span>';
  };

  window.CarLogger.fmtTime = function fmtTime(t) {
    function pad2(n) {
      return (n < 10 ? "0" : "") + n;
    }
    var d = new Date(t * 1000);
    return (
      pad2(d.getHours()) +
      ":" +
      pad2(d.getMinutes()) +
      ":" +
      pad2(d.getSeconds())
    );
  };

  window.CarLogger.shortModelName = function shortModelName(full) {
    return String(full || "").split("/").pop();
  };

  window.CarLogger.formatDateTime = function formatDateTime(ts) {
    if (!ts) return "--";
    return String(ts).split(".")[0].replace("T", " ");
  };
})();
