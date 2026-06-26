(function () {
  "use strict";

  var PAGE_SIZE = 100;
  var currentOffset = 0;
  var currentSearch = "";
  var currentFilter = "";
  var loading = false;
  var hasMore = true;
  var allRows = [];

  var getEl = window.CarLogger.getEl;
  var escHtml = window.CarLogger.escHtml;
  var aiLabelHtml = window.CarLogger.aiLabelHtml;

  function showSkeleton() {
    var tbody = getEl("history-body");
    tbody.innerHTML = "";
    for (var i = 0; i < 6; i++) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td><div class="skeleton" style="width:16px;height:16px;margin:auto"></div></td>' +
        '<td><div class="skeleton" style="height:16px;width:60px"></div></td>' +
        '<td><div class="skeleton" style="height:16px;width:80px"></div></td>' +
        '<td><div class="skeleton" style="height:16px;width:140px"></div></td>' +
        '<td><div class="skeleton" style="height:16px;width:60px"></div></td>' +
        '<td><div class="skeleton" style="height:16px;width:100px"></div></td>' +
        '<td><div class="skeleton" style="height:16px;width:40px"></div></td>';
      tbody.appendChild(tr);
    }
  }

  function clearFilters() {
    currentSearch = "";
    currentFilter = "";
    getEl("search-input").value = "";
    filterBtns.forEach(function (b) {
      b.classList.remove("active");
    });
    filterBtns[0].classList.add("active");
    loadHistory("", false);
  }

  function updateClearFiltersBtn() {
    var btn = getEl("btn-clear-filters");
    if (!btn) return;
    btn.style.display = currentSearch || currentFilter ? "inline-block" : "none";
  }

  async function loadHistory(search, append) {
    if (loading) return;
    loading = true;

    if (!append) {
      currentOffset = 0;
      hasMore = true;
      allRows = [];
      showSkeleton();
    }

    var url = "/api/history?limit=" + PAGE_SIZE + "&offset=" + currentOffset;
    if (search) url += "&search=" + encodeURIComponent(search);
    if (currentFilter) url += "&ai_label=" + encodeURIComponent(currentFilter);

    try {
      var r = await fetch(url);
      if (!r.ok) throw new Error("Server returned " + r.status);
      var rows = await r.json();
      var tbody = getEl("history-body");

      if (!append) tbody.innerHTML = "";

      if (rows.length === 0 && !append) {
        var msg =
          currentSearch || currentFilter
            ? 'No detections match your filter. <button class="btn btn-tiny clear-filters" style="color:var(--accent2);background:transparent;border:none;padding:0">Clear filters</button>'
            : "No detections yet. Park near a camera to start logging.";
        tbody.innerHTML = '<tr><td colspan="7" class="empty">' + msg + "</td></tr>";
        getEl("btn-load-more").style.display = "none";
        hasMore = false;
      } else {
        for (const row of rows) {
          allRows.push(row);
          var tr = document.createElement("tr");
          var imgFile = row.image_path ? row.image_path.split("/").pop() : null;
          tr.dataset.id = row.id;
          tr.innerHTML =
            '<td><input type="checkbox" class="row-check" data-id="' +
            escHtml(row.id) +
            '" aria-label="Select row ' +
            escHtml(row.id) +
            '"></td>' +
            "<td>" +
            aiLabelHtml(row.ai_label) +
            "</td>" +
            '<td class="plate-cell">' +
            escHtml(row.plate || "--") +
            "</td>" +
            '<td class="ts-cell">' +
            escHtml(window.CarLogger.formatDateTime(row.timestamp || row.created_at)) +
            "</td>" +
            "<td>" +
            escHtml(row.vehicle_info || "--") +
            "</td>" +
            "<td>" +
            (row.latitude
              ? escHtml(
                  row.latitude.toFixed(4) + ", " + row.longitude.toFixed(4)
                )
              : "--") +
            "</td>" +
            "<td>" +
            (imgFile
              ? '<a href="/snaps/' + escHtml(imgFile) + '" target="_blank">View</a>'
              : "--") +
            "</td>";
          tbody.appendChild(tr);
        }
        currentOffset += rows.length;
        hasMore = rows.length >= PAGE_SIZE;
        getEl("btn-load-more").style.display = hasMore ? "inline-block" : "none";
      }
    } catch (e) {
      getEl("history-body").innerHTML =
        '<tr><td colspan="7" class="empty">Could not load history. The server may be restarting — try refreshing in a moment.</td></tr>';
    }

    try {
      var sr = await fetch("/api/stats");
      if (sr.ok) {
        var st = await sr.json();
        getEl("history-count").textContent = "(" + (st.total || 0) + " total)";
      }
    } catch (e) {}

    getEl("history-loading").style.display = "none";
    loading = false;
    updateClearFiltersBtn();
  }

  // Filter buttons
  var filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      filterBtns.forEach(function (b) {
        b.classList.remove("active");
      });
      this.classList.add("active");
      currentFilter = this.dataset.filter;
      loadHistory(getEl("search-input").value, false);
    });
  });

  getEl("btn-search").addEventListener("click", function () {
    currentSearch = getEl("search-input").value;
    loadHistory(currentSearch, false);
  });
  getEl("search-input").addEventListener("keyup", function (e) {
    if (e.key === "Enter") {
      currentSearch = e.target.value;
      loadHistory(currentSearch, false);
    }
  });
  getEl("btn-refresh").addEventListener("click", function () {
    loadHistory(getEl("search-input").value, false);
  });
  getEl("btn-load-more").addEventListener("click", function () {
    loadHistory(currentSearch, true);
  });
  getEl("btn-clear-filters").addEventListener("click", clearFilters);

  getEl("btn-export").addEventListener("click", function () {
    if (allRows.length === 0) return;
    var headers = [
      "id",
      "ai_label",
      "plate",
      "timestamp",
      "vehicle_info",
      "latitude",
      "longitude",
      "image_path",
    ];
    var csv = headers.join(",") + "\n";
    for (var r of allRows) {
      csv +=
        headers
          .map(function (h) {
            var v =
              r[h] !== null && r[h] !== undefined
                ? String(r[h]).replace(/"/g, '""')
                : "";
            return '"' + v + '"';
          })
          .join(",") + "\n";
    }
    var blob = new Blob([csv], { type: "text/csv" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download =
      "car-logger-detections-" + new Date().toISOString().slice(0, 10) + ".csv";
    a.click();
    URL.revokeObjectURL(a.href);
  });

  // Select all toggle
  getEl("select-all").addEventListener("change", function () {
    var checks = document.querySelectorAll(".row-check");
    for (var c of checks) c.checked = this.checked;
    updateDeleteBtn();
  });

  // Update delete button visibility
  document.addEventListener("change", function (e) {
    if (e.target.classList.contains("row-check")) updateDeleteBtn();
  });

  function updateDeleteBtn() {
    var checked = document.querySelectorAll(".row-check:checked").length;
    getEl("btn-delete-selected").style.display =
      checked > 0 ? "inline-block" : "none";
  }

  getEl("btn-delete-selected").addEventListener("click", async function () {
    var ids = [];
    var checks = document.querySelectorAll(".row-check:checked");
    for (var c of checks) ids.push(c.dataset.id);
    if (ids.length === 0) return;
    if (
      !confirm(
        "Delete " + ids.length + " detection(s)? This cannot be undone."
      )
    )
      return;

    getEl("btn-delete-selected").textContent = "Deleting...";
    getEl("btn-delete-selected").disabled = true;

    try {
      var r = await fetch("/api/history", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ids),
      });
      if (r.ok) {
        loadHistory(currentSearch, false);
      } else {
        var err = await r.json();
        alert("Delete failed: " + (err.error || r.status));
      }
    } catch (e) {
      alert("Delete failed: " + e.message);
    }

    getEl("btn-delete-selected").textContent = "Delete selected";
    getEl("btn-delete-selected").disabled = false;
  });

  getEl("btn-wipe").addEventListener("click", async function () {
    if (
      !confirm(
        "WIPE ALL DETECTION HISTORY?\n\nThis will permanently delete every detection in the database. This cannot be undone.\n\nAre you sure?"
      )
    )
      return;

    getEl("btn-wipe").textContent = "Wiping...";
    getEl("btn-wipe").disabled = true;

    try {
      var r = await fetch("/api/history?all=1", { method: "DELETE" });
      if (r.ok) {
        await r.json();
        loadHistory("", false);
      } else {
        alert("Wipe failed: " + r.status);
      }
    } catch (e) {
      alert("Wipe failed: " + e.message);
    }

    getEl("btn-wipe").textContent = "Wipe all";
    getEl("btn-wipe").disabled = false;
  });

  // Clear filters buttons (top bar + empty-state inline link)
  document.addEventListener("click", function (e) {
    if (e.target.closest(".clear-filters")) {
      clearFilters();
    }
  });

  loadHistory("", false);

  // Populate plate autocomplete once on page load
  fetch("/api/plates")
    .then(function (r) {
      return r.json();
    })
    .then(function (plates) {
      var dl = getEl("plate-list");
      dl.innerHTML = "";
      for (var p of plates) {
        var opt = document.createElement("option");
        opt.value = p;
        dl.appendChild(opt);
      }
    })
    .catch(function () {});

  window.CarLogger.startStatusPoll(5000);
})();
