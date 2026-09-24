/* ============================================
   KIOSK CHECK-IN — Professional Check-in App
   ============================================ */

(function () {
  'use strict';

  // ---- Elements ----
  const root = document.getElementById('kiosk-root');
  const eventScreen = document.getElementById('kiosk-event-select');
  const scannerScreen = document.getElementById('kiosk-scanner');
  const eventListEl = document.getElementById('kiosk-event-list');
  const backBtn = document.getElementById('kiosk-back-btn');
  const fullscreenBtn = document.getElementById('kiosk-fullscreen-btn');
  const exitBtn = document.getElementById('kiosk-exit-btn');
  const scannerTitle = document.getElementById('kiosk-scanner-event-title');
  const videoEl = document.getElementById('kiosk-video');
  const canvasEl = document.getElementById('kiosk-canvas');
  const cameraFrame = document.getElementById('kiosk-camera-frame');
  const cameraPlaceholder = document.getElementById('kiosk-camera-placeholder');
  const resultCard = document.getElementById('kiosk-result');
  const resultIcon = document.getElementById('kiosk-result-icon');
  const resultStatus = document.getElementById('kiosk-result-status');
  const resultStudent = document.getElementById('kiosk-result-student');
  const resultTicket = document.getElementById('kiosk-result-ticket');
  const resultTime = document.getElementById('kiosk-result-time');
  const liveCount = document.getElementById('kiosk-live-count');
  const manualBtn = document.getElementById('kiosk-manual-btn');
  const resetBtn = document.getElementById('kiosk-reset-btn');
  const manualOverlay = document.getElementById('kiosk-manual');
  const manualInput = document.getElementById('kiosk-manual-input');
  const manualSubmit = document.getElementById('kiosk-manual-submit');
  const manualCancel = document.getElementById('kiosk-manual-cancel');

  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  // ---- State ----
  let currentEventId = null;
  let scanning = false;
  let html5QrCode = null;
  let scanCooldown = false;
  let statsPollInterval = null;
  let eventList = [];

  // ---- API Helpers ----

  async function apiFetch(url, options) {
    const opts = Object.assign({
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      },
    }, options || {});
    const resp = await fetch(url, opts);
    const data = await resp.json().catch(() => ({}));
    return { ok: resp.ok, status: resp.status, data: data };
  }

  async function loadEvents() {
    const { ok, data } = await apiFetch('/api/kiosk/events', { method: 'GET' });
    if (!ok || !data.success) {
      eventListEl.innerHTML = '<div class="kiosk-event-list__empty">Failed to load events.</div>';
      return;
    }
    eventList = data.events || [];
    if (eventList.length === 0) {
      eventListEl.innerHTML = '<div class="kiosk-event-list__empty">No authorized events found.</div>';
      return;
    }
    eventListEl.innerHTML = eventList.map(function (e) {
      const pct = e.registered > 0 ? Math.round((e.attended / e.registered) * 100) : 0;
      const dateStr = e.date ? new Date(e.date).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
      }) : '—';
      return '<div class="kiosk-event-card" data-event-id="' + e.id + '">' +
        '<div class="kiosk-event-card__title">' + escapeHtml(e.title) + '</div>' +
        '<div class="kiosk-event-card__meta">' +
        '<span>📅 ' + dateStr + ' · ' + escapeHtml(e.time) + '</span>' +
        '<span>📍 ' + escapeHtml(e.venue || '—') + '</span>' +
        '</div>' +
        '<div class="kiosk-event-card__count">' + e.attended + ' / ' + e.registered + '</div>' +
        '<div class="kiosk-event-card__progress">' +
        '<div class="kiosk-event-card__progress-bar" style="width:' + pct + '%"></div>' +
        '</div>' +
        '</div>';
    }).join('');
    // Attach click handlers
    document.querySelectorAll('.kiosk-event-card').forEach(function (card) {
      card.addEventListener('click', function () {
        const id = parseInt(this.getAttribute('data-event-id'), 10);
        startKioskForEvent(id);
      });
    });
  }

  // ---- Kiosk Flow ----

  function startKioskForEvent(eventId) {
    const event = eventList.find(function (e) { return e.id === eventId; });
    if (!event) return;
    currentEventId = eventId;
    scannerTitle.textContent = event.title;
    eventScreen.classList.remove('kiosk-screen--active');
    scannerScreen.classList.add('kiosk-screen--active');
    resultCard.classList.remove('kiosk-result--show', 'kiosk-result--success',
      'kiosk-result--duplicate', 'kiosk-result--invalid');
    resetBtn.style.display = 'none';
    scanCooldown = false;
    startStatsPolling();
    startScanner();
    // Auto-enter fullscreen if possible
    requestFullscreen();
  }

  function goBack() {
    stopStatsPolling();
    stopScanner();
    scannerScreen.classList.remove('kiosk-screen--active');
    eventScreen.classList.add('kiosk-screen--active');
    currentEventId = null;
  }

  function exitKiosk() {
    stopStatsPolling();
    stopScanner();
    if (document.exitFullscreen && document.fullscreenElement) {
      document.exitFullscreen();
    }
    window.location.href = '/kiosk';
  }

  // ---- Stats Polling ----

  function startStatsPolling() {
    refreshStats();
    statsPollInterval = setInterval(refreshStats, 5000);
  }

  function stopStatsPolling() {
    if (statsPollInterval) {
      clearInterval(statsPollInterval);
      statsPollInterval = null;
    }
  }

  async function refreshStats() {
    if (!currentEventId) return;
    const { data } = await apiFetch('/api/kiosk/stats/' + currentEventId, { method: 'GET' });
    if (data && data.success) {
      liveCount.textContent = data.attended + ' / ' + data.registered;
    }
  }

  // ---- QR Scanner ----

  function startScanner() {
    scanning = true;
    scanCooldown = false;
    resetBtn.style.display = 'none';

    if (!window.Html5Qrcode) {
      showCameraError('QR library not loaded. Please refresh the page.');
      return;
    }

    html5QrCode = new Html5Qrcode('kiosk-video');
    const config = { fps: 10, qrbox: { width: 250, height: 250 } };

    html5QrCode.start(
      { facingMode: 'environment' },
      config,
      function (decodedText) {
        handleScanResult(decodedText, 'qr_scan');
      },
      function (errorMessage) {
        // Silently ignore scan errors (frame decode failures are normal)
        if (errorMessage && errorMessage.includes('NotFoundException')) {
          // Camera not found, show placeholder
          showCameraError('No camera found. Use manual entry instead.');
        }
      }
    ).catch(function (err) {
      showCameraError('Camera access unavailable. Use manual entry instead.');
      console.error('Kiosk camera error:', err);
    });
  }

  function stopScanner() {
    scanning = false;
    if (html5QrCode) {
      html5QrCode.clear().catch(function () {});
      html5QrCode = null;
    }
  }

  function showCameraError(message) {
    cameraPlaceholder.style.display = 'flex';
    cameraPlaceholder.querySelector('.kiosk-camera-placeholder__text').textContent = message;
  }

  function hideCameraError() {
    cameraPlaceholder.style.display = 'none';
  }

  async function handleScanResult(decodedText, method) {
    if (scanCooldown) return;
    scanCooldown = true;

    // Pause scanning while we process
    if (html5QrCode) {
      html5QrCode.pause().catch(function () {});
    }

    const payload = {
      identifier: decodedText,
      event_id: currentEventId,
      method: method,
    };

    const { ok, status, data } = await apiFetch('/api/kiosk/checkin', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    showResult(data, ok);

    // Auto-reset for next scan after delay
    setTimeout(function () {
      scanCooldown = false;
      resultCard.classList.remove('kiosk-result--show', 'kiosk-result--success',
        'kiosk-result--duplicate', 'kiosk-result--invalid');
      resetBtn.style.display = 'inline-flex';
      if (html5QrCode) {
        html5QrCode.resume().catch(function () {});
      }
    }, 2500);
  }

  // ---- Result Display ----

  function showResult(data, apiOk) {
    const status = data.status || 'invalid';
    const statusClass = 'kiosk-result--' + status;

    // Reset
    resultCard.className = 'kiosk-result';
    resultIcon.className = 'kiosk-result__icon';
    resultStatus.textContent = '';
    resultStudent.textContent = '—';
    resultTicket.textContent = '—';
    resultTime.textContent = '—';

    if (status === 'success') {
      resultIcon.textContent = '✓';
      resultStatus.textContent = '✓ Attendance Marked';
    } else if (status === 'duplicate') {
      resultIcon.textContent = '⚠';
      resultStatus.textContent = '⚠ Already Checked In';
    } else {
      resultIcon.textContent = '✕';
      resultStatus.textContent = '✕ Invalid Ticket';
    }

    resultStudent.textContent = data.participant || '—';
    resultTicket.textContent = data.ticket_code || data.message || '—';
    resultTime.textContent = data.checkin_time || new Date().toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: true
    });

    // Show the result card
    resultCard.classList.add('kiosk-result--show', statusClass);
    resetBtn.style.display = 'none';

    // Refresh live count on successful check-in
    if (status === 'success' || status === 'duplicate') {
      refreshStats();
    }
  }

  function resetResult() {
    resultCard.classList.remove('kiosk-result--show', 'kiosk-result--success',
      'kiosk-result--duplicate', 'kiosk-result--invalid');
    resetBtn.style.display = 'none';
    scanCooldown = false;
    if (html5QrCode) {
      html5QrCode.resume().catch(function () {});
    }
  }

  // ---- Manual Entry ----

  function showManualEntry() {
    manualOverlay.classList.add('kiosk-manual--show');
    manualInput.value = '';
    manualInput.focus();
  }

  function hideManualEntry() {
    manualOverlay.classList.remove('kiosk-manual--show');
    manualInput.value = '';
  }

  async function submitManual() {
    const code = manualInput.value.trim().toUpperCase();
    if (!code) return;
    manualSubmit.disabled = true;
    manualSubmit.textContent = 'Checking…';
    await handleScanResult(code, 'manual');
    // Hide manual overlay after processing
    setTimeout(hideManualEntry, 500);
  }

  // ---- Fullscreen ----

  function requestFullscreen() {
    const el = document.documentElement;
    if (el.requestFullscreen) {
      el.requestFullscreen().catch(function () {});
    } else if (el.webkitRequestFullscreen) {
      el.webkitRequestFullscreen().catch(function () {});
    } else if (el.msRequestFullscreen) {
      el.msRequestFullscreen().catch(function () {});
    }
  }

  // ---- Utility ----

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ---- Event Listeners ----

  backBtn.addEventListener('click', function () {
    if (scanCooldown) return;
    goBack();
  });

  exitBtn.addEventListener('click', function () {
    if (!confirm('Exit kiosk mode?')) return;
    exitKiosk();
  });

  fullscreenBtn.addEventListener('click', function () {
    requestFullscreen();
  });

  manualBtn.addEventListener('click', function () {
    if (currentEventId) showManualEntry();
  });

  manualCancel.addEventListener('click', hideManualEntry);

  manualSubmit.addEventListener('click', submitManual);

  manualInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      submitManual();
    }
  });

  manualInput.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      hideManualEntry();
    }
  });

  resetBtn.addEventListener('click', function () {
    resetResult();
  });

  // Also reset on backdrop click for manual overlay
  manualOverlay.addEventListener('click', function (e) {
    if (e.target === manualOverlay) hideManualEntry();
  });

  // ---- Init ----
  loadEvents();
})();
