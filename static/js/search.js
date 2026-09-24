/**
 * CEMS Global Search — Frontend Logic
 * Handles autocomplete, search execution, filters, pagination.
 */
(function () {
  "use strict";

  const config = window.searchConfig || {};
  let debounceTimer = null;
  let currentResults = null;
  let currentPage = 1;

  /* ────────────────────────────────────────────
     UTILITIES
  ──────────────────────────────────────────── */
  function esc(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function debounce(fn, delay) {
    return function (...args) {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  /* ────────────────────────────────────────────
     AUTOCOMPLETE
  ──────────────────────────────────────────── */
  const searchInput = document.getElementById("search-input");
  const autocompleteDropdown = document.getElementById("autocomplete-dropdown");
  const autocompleteResults = document.getElementById("autocomplete-results");
  const searchClear = document.getElementById("search-clear");

  const fetchAutocomplete = debounce(async function (query) {
    if (!query || query.length < 2) {
      autocompleteDropdown.style.display = "none";
      return;
    }
    try {
      const url = config.autocompleteUrl + "?q=" + encodeURIComponent(query);
      const resp = await fetch(url);
      const data = await resp.json();
      if (!data.success || !data.suggestions.length) {
        autocompleteDropdown.style.display = "none";
        return;
      }
      renderAutocomplete(data.suggestions);
    } catch (e) {
      /* Silently fail — autocomplete is non-critical */
    }
  }, 250);

  function renderAutocomplete(suggestions) {
    const typeIcons = {
      event: "📅", venue: "🏫", notice: "📢",
      certificate: "🏆", resource: "📦", user: "👤",
    };
    const typeLabels = {
      event: "Event", venue: "Venue", notice: "Notice",
      certificate: "Certificate", resource: "Resource", user: "User",
    };

    // Group by type
    const grouped = {};
    for (const s of suggestions) {
      if (!grouped[s.type]) grouped[s.type] = [];
      grouped[s.type].push(s);
    }

    let html = "";
    for (const type of Object.keys(grouped).sort((a, b) => {
      const order = { event: 0, venue: 1, notice: 2, resource: 3, certificate: 4 };
      return (order[type] ?? 99) - (order[b] ?? 99);
    })) {
      html += `<div class="autocomplete-group-label">${typeLabels[type] || type}</div>`;
      for (const item of grouped[type]) {
        html += `
          <a href="${esc(item.url)}" class="autocomplete-item" data-type="${item.type}" data-id="${item.id}">
            <span class="autocomplete-icon">${typeIcons[item.type] || "🔍"}</span>
            <div class="autocomplete-body">
              <div class="autocomplete-title">${esc(item.title)}</div>
              <div class="autocomplete-subtitle">${esc(item.subtitle)}</div>
            </div>
          </a>
        `;
      }
    }

    autocompleteResults.innerHTML = html;
    autocompleteDropdown.style.display = "block";
  }

  searchInput.addEventListener("input", function () {
    const val = this.value.trim();
    searchClear.style.display = val ? "block" : "none";
    fetchAutocomplete(val);
  });

  searchInput.addEventListener("focus", function () {
    if (this.value.trim().length >= 2) {
      fetchAutocomplete(this.value.trim());
    }
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".search-input-wrap")) {
      autocompleteDropdown.style.display = "none";
    }
  });

  searchClear.addEventListener("click", function () {
    searchInput.value = "";
    searchClear.style.display = "none";
    autocompleteDropdown.style.display = "none";
    searchInput.focus();
  });

  /* ────────────────────────────────────────────
     SEARCH EXECUTION
  ──────────────────────────────────────────── */
  async function executeSearch(page, type, q, filters) {
    const params = new URLSearchParams();
    params.set("page", page);
    params.set("per_page", document.getElementById("per-page-select").value);
    if (type && type !== "all") params.set("type", type);
    if (q) params.set("q", q);

    // Type-specific filters
    if (type === "event" || type === "all") {
      if (filters.event_category) params.set("event_category", filters.event_category);
      if (filters.event_date) params.set("event_date", filters.event_date);
      if (filters.event_venue) params.set("event_venue", filters.event_venue);
      if (filters.event_status) params.set("event_status", filters.event_status);
    }
    if (type === "venue" || type === "all") {
      if (filters.venue_building) params.set("venue_building", filters.venue_building);
      if (filters.venue_capacity) params.set("venue_capacity", filters.venue_capacity);
      if (filters.venue_type) params.set("venue_type", filters.venue_type);
    }
    if (type === "notice" || type === "all") {
      if (filters.notice_category) params.set("notice_category", filters.notice_category);
    }
    if (type === "certificate" || type === "all") {
      if (filters.cert_id) params.set("cert_id", filters.cert_id);
    }
    if (type === "resource" || type === "all") {
      if (filters.resource_category) params.set("resource_category", filters.resource_category);
      if (filters.resource_status) params.set("resource_status", filters.resource_status);
    }

    try {
      const url = config.searchUrl + "?" + params.toString();
      const resp = await fetch(url);
      const data = await resp.json();
      if (data.success) {
        currentResults = data;
        currentPage = page;
        renderResults(data);
        updateURL(params);
      }
    } catch (e) {
      showError("Search failed. Please try again.");
    }
  }

  function renderResults(data) {
    const { results, totals, empty_messages, has_filters } = data;
    const typeLabels = {
      events: "Events", venues: "Venues", notices: "Notices",
      certificates: "Certificates", resources: "Resources",
    };
    const totalResults = data.total_results;

    document.getElementById("search-prompt").style.display = "none";
    document.getElementById("search-results").style.display = "block";

    document.getElementById("results-title").textContent = "Search Results";
    document.getElementById("results-count").textContent =
      totalResults === 1 ? "1 result" : `${totalResults} results`;

    // Active filters bar
    const activeFiltersBar = document.getElementById("active-filters-bar");
    const q = document.getElementById("search-input").value.trim();
    const type = document.getElementById("search-type").value;
    let filterChips = "";
    if (q) filterChips += `<span class="filter-chip">Search: "${esc(q)}"</span>`;
    if (type && type !== "all") filterChips += `<span class="filter-chip">Type: ${esc(type)}</span>`;
    if (has_filters) {
      for (const [k, v] of Object.entries(results)) {
        // No extra chips for now, just show "has filters"
      }
    }
    activeFiltersBar.style.display = filterChips ? "flex" : "none";
    activeFiltersBar.innerHTML = filterChips +
      `<button class="clear-search-btn" type="button" onclick="window.searchApp.clearSearch()">Clear Search</button>`;

    // Build results content
    let html = "";
    let hasAnyResults = false;
    let emptyDesc = "";

    for (const [key, items] of Object.entries(results)) {
      if (items.length > 0) {
        hasAnyResults = true;
        html += `<div class="results-type-section">`;
        html += `<h3 class="results-type-title">${typeLabels[key] || key} <span class="results-type-count">${items.length}</span></h3>`;
        html += `<div class="results-grid">`;
        for (const item of items) {
          html += renderResultCard(key, item);
        }
        html += `</div></div>`;
      } else if (data.total_results === 0) {
        emptyDesc = empty_messages[key] || empty_messages["events"];
      }
    }

    if (!hasAnyResults) {
      document.getElementById("empty-state").style.display = "block";
      document.getElementById("empty-description").textContent = emptyDesc || "No results found. Try adjusting your search terms or filters.";
      document.getElementById("results-content").innerHTML = "";
    } else {
      document.getElementById("empty-state").style.display = "none";
      document.getElementById("results-content").innerHTML = html;
    }

    // Pagination
    const pagination = document.getElementById("pagination");
    if (data.total_results > 0) {
      const totalPages = Math.ceil(data.total_results / data.per_page);
      if (totalPages > 1) {
        let phtml = `<span class="page-info">Page ${data.page} of ${totalPages}</span>`;
        if (data.page > 1) {
          phtml += `<button class="page-btn page-prev" data-page="${data.page - 1}" type="button">← Previous</button>`;
        }
        if (data.page < totalPages) {
          phtml += `<button class="page-btn page-next" data-page="${data.page + 1}" type="button">Next →</button>`;
        }
        pagination.innerHTML = phtml;
        pagination.style.display = "flex";
      } else {
        pagination.style.display = "none";
      }
    } else {
      pagination.style.display = "none";
    }

    // Update filter panel visibility
    if (data.total_results > 0 || has_filters) {
      document.getElementById("search-filters").style.display = "block";
    }
  }

  function renderResultCard(type, item) {
    const typeIcons = {
      events: "📅", venues: "🏫", notices: "📢",
      certificates: "🏆", resources: "📦",
    };
    const icon = typeIcons[type] || "🔍";
    let meta = "";

    if (type === "events") {
      const dateStr = item.date ? `<span>◷ ${esc(item.date)}</span>` : "";
      meta = `<div class="result-meta">${dateStr}<span>⌖ ${esc(item.venue || "—")}</span><span>${esc(item.category || "")}</span></div>`;
    } else if (type === "venues") {
      meta = `<div class="result-meta"><span>${esc(item.building || "—")}</span><span>${esc(item.venue_type || "—")}</span><span>Cap: ${item.capacity}</span></div>`;
    } else if (type === "notices") {
      meta = `<div class="result-meta"><span>${esc(item.category || "")}</span><span>${esc(item.published_at || "—")}</span></div>`;
    } else if (type === "certificates") {
      meta = `<div class="result-meta"><span>${esc(item.certificate_code || "")}</span><span>${item.verified ? "✅ Verified" : "⏳ Pending"}</span></div>`;
    } else if (type === "resources") {
      meta = `<div class="result-meta"><span>${esc(item.category || "")}</span><span>${esc(item.location || "—")}</span><span>${item.available_quantity}/${item.quantity} avail.</span></div>`;
    }

    const desc = item.description ? `<p class="result-description">${esc(item.description)}</p>` : "";
    const status = item.status ? `<span class="result-status-badge ${getStatusClass(item.status)}">${esc(item.status)}</span>` : "";

    return `
      <a href="${esc(item.url)}" class="result-card">
        <div class="result-card-header">
          <span class="result-icon">${icon}</span>
          <h4 class="result-title">${esc(item.title || item.name || "Untitled")}</h4>
          ${status}
        </div>
        ${meta}
        ${desc}
      </a>
    `;
  }

  function getStatusClass(status) {
    const s = (status || "").toLowerCase();
    if (s === "approved" || s === "active" || s === "available" || s === "verified" || s === "published") return "status-good";
    if (s === "pending" || s === "waiting" || s === "reserved") return "status-warn";
    if (s === "rejected" || s === "unavailable" || s === "cancelled") return "status-bad";
    return "status-neutral";
  }

  /* ────────────────────────────────────────────
     DYNAMIC FILTERS
  ──────────────────────────────────────────── */
  function updateFilters(type) {
    const grid = document.getElementById("filters-grid");
    grid.innerHTML = "";

    if (type === "all" || type === "event") {
      grid.innerHTML += `
        <div class="filter-group">
          <label>Category</label>
          <select class="filter-input" data-filter="event_category">
            <option value="">All Categories</option>
            <option value="Academic">Academic</option>
            <option value="Technical">Technical</option>
            <option value="Cultural">Cultural</option>
            <option value="Sports">Sports</option>
            <option value="Workshop">Workshop</option>
            <option value="Entrepreneurship">Entrepreneurship</option>
            <option value="Social">Social</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Date</label>
          <input type="date" class="filter-input" data-filter="event_date">
        </div>
        <div class="filter-group">
          <label>Venue</label>
          <input type="text" class="filter-input" data-filter="event_venue" placeholder="Venue name...">
        </div>
        <div class="filter-group">
          <label>Status</label>
          <select class="filter-input" data-filter="event_status">
            <option value="">All</option>
            <option value="approved">Approved</option>
            <option value="published">Published</option>
            <option value="pending">Pending</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      `;
    }

    if (type === "all" || type === "venue") {
      grid.innerHTML += `
        <div class="filter-group">
          <label>Building</label>
          <input type="text" class="filter-input" data-filter="venue_building" placeholder="Building name...">
        </div>
        <div class="filter-group">
          <label>Min Capacity</label>
          <input type="number" class="filter-input" data-filter="venue_capacity" min="0" placeholder="e.g. 100">
        </div>
        <div class="filter-group">
          <label>Type</label>
          <select class="filter-input" data-filter="venue_type">
            <option value="">All Types</option>
            <option value="Auditorium">Auditorium</option>
            <option value="Seminar Hall">Seminar Hall</option>
            <option value="Classroom">Classroom</option>
            <option value="Lab">Lab</option>
            <option value="Ground">Ground</option>
            <option value="Conference Room">Conference Room</option>
            <option value="Open Area">Open Area</option>
            <option value="Other">Other</option>
          </select>
        </div>
      `;
    }

    if (type === "all" || type === "notice") {
      grid.innerHTML += `
        <div class="filter-group">
          <label>Category</label>
          <select class="filter-input" data-filter="notice_category">
            <option value="">All Categories</option>
            <option value="Academic">Academic</option>
            <option value="Examination">Examination</option>
            <option value="Placement">Placement</option>
            <option value="Technical">Technical</option>
            <option value="Social">Social</option>
            <option value="Cultural">Cultural</option>
          </select>
        </div>
      `;
    }

    if (type === "all" || type === "certificate") {
      grid.innerHTML += `
        <div class="filter-group">
          <label>Certificate ID</label>
          <input type="text" class="filter-input" data-filter="cert_id" placeholder="Certificate code...">
        </div>
      `;
    }

    if (type === "all" || type === "resource") {
      grid.innerHTML += `
        <div class="filter-group">
          <label>Category</label>
          <select class="filter-input" data-filter="resource_category">
            <option value="">All Categories</option>
            <option value="Audio-Visual">Audio-Visual</option>
            <option value="Furniture">Furniture</option>
            <option value="Equipment">Equipment</option>
            <option value="Stationery">Stationery</option>
            <option value="Sports">Sports</option>
            <option value="Lab">Lab</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Status</label>
          <select class="filter-input" data-filter="resource_status">
            <option value="">All</option>
            <option value="available">Available</option>
            <option value="reserved">Reserved</option>
            <option value="unavailable">Unavailable</option>
          </select>
        </div>
      `;
    }

    if (type !== "all") {
      grid.innerHTML += `
        <div class="filter-group filter-spacer">
          <button id="apply-filters-btn" class="btn btn-primary" type="button">Apply Filters</button>
        </div>
      `;
    }

    // Attach event listeners
    document.querySelectorAll(".filter-input").forEach(function (el) {
      el.addEventListener("change", applyFilters);
      el.addEventListener("input", function () {
        // For text inputs, apply on Enter key
        el.addEventListener("keydown", function (e) {
          if (e.key === "Enter") applyFilters();
        });
      });
    });

    const applyBtn = document.getElementById("apply-filters-btn");
    if (applyBtn) {
      applyBtn.addEventListener("click", applyFilters);
    }
  }

  function applyFilters() {
    const type = document.getElementById("search-type").value;
    const q = document.getElementById("search-input").value.trim();
    const filters = {};
    document.querySelectorAll(".filter-input").forEach(function (el) {
      const key = el.getAttribute("data-filter");
      if (key && el.value) {
        filters[key] = el.value;
      }
    });
    currentPage = 1;
    executeSearch(1, type, q, filters);
  }

  /* ────────────────────────────────────────────
     URL MANAGEMENT
  ──────────────────────────────────────────── */
  function updateURL(params) {
    const url = "/search?" + params.toString();
    window.history.replaceState({}, "", url);
  }

  function loadFromURL() {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q") || "";
    const type = params.get("type") || "all";

    if (q) {
      document.getElementById("search-input").value = q;
      document.getElementById("search-clear").style.display = "block";
    }
    if (type && type !== "all") {
      document.getElementById("search-type").value = type;
    }

    if (q || type !== "all") {
      updateFilters(type);
      const filters = {};
      for (const [key, value] of params.entries()) {
        if (key.startsWith("event_") || key.startsWith("venue_") || key.startsWith("notice_") || key.startsWith("cert_id") || key.startsWith("resource_")) {
          filters[key] = value;
        }
      }
      // Map URL param names to filter names (they're the same already)
      currentPage = parseInt(params.get("page")) || 1;
      executeSearch(currentPage, type, q, filters);
    }
  }

  /* ────────────────────────────────────────────
     PUBLIC API (exposed on window.searchApp)
  ──────────────────────────────────────────── */
  function searchByType(type) {
    document.getElementById("search-type").value = type;
    updateFilters(type);
    document.getElementById("search-input").focus();
    executeSearch(1, type, "", {});
  }

  function clearSearch() {
    document.getElementById("search-input").value = "";
    document.getElementById("search-clear").style.display = "none";
    document.getElementById("search-type").value = "all";
    document.getElementById("search-filters").style.display = "none";
    document.getElementById("search-results").style.display = "none";
    document.getElementById("empty-state").style.display = "none";
    document.getElementById("active-filters-bar").style.display = "none";
    document.getElementById("pagination").style.display = "none";
    document.getElementById("search-prompt").style.display = "block";
    updateURL(new URLSearchParams());
    window.location.reload();
  }

  function showError(message) {
    document.getElementById("empty-state").style.display = "block";
    document.getElementById("empty-title").textContent = "Error";
    document.getElementById("empty-description").textContent = message;
    document.getElementById("results-content").innerHTML = "";
  }

  // Pagination clicks (delegated)
  document.addEventListener("click", function (e) {
    const pageBtn = e.target.closest(".page-btn");
    if (pageBtn) {
      const page = parseInt(pageBtn.getAttribute("data-page"));
      const type = document.getElementById("search-type").value;
      const q = document.getElementById("search-input").value.trim();
      const filters = {};
      document.querySelectorAll(".filter-input").forEach(function (el) {
        const key = el.getAttribute("data-filter");
        if (key && el.value) filters[key] = el.value;
      });
      executeSearch(page, type, q, filters);
    }
  });

  // Per-page change
  document.getElementById("per-page-select").addEventListener("change", function () {
    const type = document.getElementById("search-type").value;
    const q = document.getElementById("search-input").value.trim();
    const filters = {};
    document.querySelectorAll(".filter-input").forEach(function (el) {
      const key = el.getAttribute("data-filter");
      if (key && el.value) filters[key] = el.value;
    });
    executeSearch(1, type, q, filters);
  });

  // Search button
  document.getElementById("search-btn").addEventListener("click", function () {
    const type = document.getElementById("search-type").value;
    const q = document.getElementById("search-input").value.trim();
    const filters = {};
    document.querySelectorAll(".filter-input").forEach(function (el) {
      const key = el.getAttribute("data-filter");
      if (key && el.value) filters[key] = el.value;
    });
    currentPage = 1;
    executeSearch(1, type, q, filters);
  });

  // Enter key on search input
  searchInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      autocompleteDropdown.style.display = "none";
      const type = document.getElementById("search-type").value;
      const q = this.value.trim();
      const filters = {};
      document.querySelectorAll(".filter-input").forEach(function (el) {
        const key = el.getAttribute("data-filter");
        if (key && el.value) filters[key] = el.value;
      });
      currentPage = 1;
      executeSearch(1, type, q, filters);
    }
  });

  // Clear filters
  document.getElementById("clear-filters").addEventListener("click", function () {
    document.querySelectorAll(".filter-input").forEach(function (el) {
      el.value = "";
    });
    const type = document.getElementById("search-type").value;
    const q = document.getElementById("search-input").value.trim();
    currentPage = 1;
    executeSearch(1, type, q, {});
  });

  // Type change
  document.getElementById("search-type").addEventListener("change", function () {
    const type = this.value;
    updateFilters(type);
    if (type !== "all") {
      executeSearch(1, type, "", {});
    } else {
      const q = document.getElementById("search-input").value.trim();
      if (q) {
        executeSearch(1, "all", q, {});
      } else {
        document.getElementById("search-filters").style.display = "none";
        document.getElementById("search-results").style.display = "none";
        document.getElementById("empty-state").style.display = "none";
        document.getElementById("search-prompt").style.display = "block";
        updateURL(new URLSearchParams());
      }
    }
  });

  // Initialize
  updateFilters(config.currentType !== "all" ? config.currentType : "all");
  loadFromURL();

  // Expose public API
  window.searchApp = {
    searchByType,
    clearSearch,
    executeSearch,
  };
})();
