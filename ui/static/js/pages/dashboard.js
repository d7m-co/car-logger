(function () {
  "use strict";

  // Guard so app.js never crashes if the CDN script is blocked.
  window.io = window.io || null;

  function getEl(id) {
    return document.getElementById(id);
  }

  function updateCapNotice() {
    var notice = getEl("cap-notice");
    var total = getEl("total-count");
    if (!notice || !total) return;
    var n = parseInt(total.textContent, 10) || 0;
    notice.textContent = n >= 100 ? "showing latest 100" : "";
  }

  function setupCapNotice() {
    var total = getEl("total-count");
    if (!total) return;
    updateCapNotice();
    var mo = new MutationObserver(updateCapNotice);
    mo.observe(total, { childList: true, subtree: true, characterData: true });
  }

  function setupRetryButton() {
    var feedContainer = getEl("feed-container");
    if (!feedContainer) return;
    feedContainer.addEventListener("click", function (e) {
      var btn = e.target.closest(".feed-error .btn");
      if (btn && typeof retryFeed === "function") {
        retryFeed();
      }
    });
  }

  function setupFocusTrap() {
    var modal = getEl("detail-modal");
    if (!modal) return;

    var focusablesSelector =
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

    function getFocusables() {
      return Array.from(modal.querySelectorAll(focusablesSelector)).filter(
        function (n) {
          return n.offsetParent !== null && !n.disabled;
        }
      );
    }

    modal.addEventListener("keydown", function (e) {
      if (e.key !== "Tab") return;
      var nodes = getFocusables();
      if (nodes.length === 0) return;
      var first = nodes[0];
      var last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });

    modal.addEventListener("focusin", function (e) {
      if (modal.open && !modal.contains(e.target)) {
        var nodes = getFocusables();
        if (nodes.length) nodes[0].focus();
      }
    });

    var previousFocus = null;
    var openObserver = new MutationObserver(function () {
      if (modal.open) {
        previousFocus = document.activeElement;
        var nodes = getFocusables();
        if (nodes.length) nodes[0].focus();
      } else if (previousFocus) {
        previousFocus.focus();
        previousFocus = null;
      }
    });
    openObserver.observe(modal, { attributes: true, attributeFilter: ["open"] });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupRetryButton();
    setupCapNotice();
    setupFocusTrap();
  });
})();
