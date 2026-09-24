/* ============================================
   CEMS Charts helper
   Lightweight wrapper around Chart.js + a tiny
   AJAX helper used by analytics dashboards.
   ============================================ */

(function () {
  if (typeof window.Chart === 'undefined') return;

  window.CemsCharts = {
    /* Render a chart on a canvas element.
       cfg = { canvasId, type, data, options }
       Returns the created Chart instance. */
    render: function (cfg) {
      var ctx = document.getElementById(cfg.canvasId);
      if (!ctx) return null;
      var chart = new Chart(ctx.getContext('2d'), {
        type: cfg.type,
        data: cfg.data,
        options: Object.assign({
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: getComputedStyle(document.documentElement).getPropertyValue('--cems-text-secondary') } },
            tooltip: {
              backgroundColor: 'rgba(15,23,42,0.9)',
              titleColor: '#fff',
              bodyColor: '#cbd5e1',
              borderColor: 'rgba(99,102,241,0.5)',
              padding: 10,
              roundedness: 8
            }
          },
          scales: {
            x: { ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--cems-text-muted') }, grid: { color: 'rgba(0,0,0,0.04)' } },
            y: { ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--cems-text-muted') }, grid: { color: 'rgba(0,0,0,0.04)' } }
          }
        }, cfg.options || {})
      });
      return chart;
    },

    /* Fetch JSON from an endpoint and return a promise. */
    fetch: function (url) {
      return fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); })
    }
  };

  /* Skeleton loader for chart canvases while data is being fetched. */
  window.CemsCharts.skeleton = function (canvasId) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    var wrap = ctx.closest('.cems-chart-skeleton');
    if (wrap) {
      wrap.classList.add('loading');
    }
  };

  /* Auto-mark all chart skeletons as loading until rendered or fetch resolves. */
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.cems-chart-skeleton').forEach(function (wrap) {
      wrap.classList.add('loading');
    });
  });
})();
