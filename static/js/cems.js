/* ============================================
   CEMS Global JavaScript
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {
  // Mobile sidebar toggle
  const sidebarToggle = document.getElementById('cems-sidebar-toggle');
  const sidebar = document.getElementById('cems-sidebar');
  const sidebarOverlay = document.getElementById('cems-sidebar-overlay');
  
  if (sidebarToggle && sidebar && sidebarOverlay) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      sidebarOverlay.classList.toggle('active');
    });
    
    sidebarOverlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      sidebarOverlay.classList.remove('active');
    });
  }
  
  // Auto-dismiss flash messages
  const flashMessages = document.querySelectorAll('.cems-alert');
  flashMessages.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transform = 'translateX(100%)';
      alert.style.transition = 'all 0.3s ease';
      setTimeout(() => alert.remove(), 300);
    }, 5000);
  });
  
  // Close sidebar on window resize (desktop)
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1024 && sidebar && sidebarOverlay) {
      sidebar.classList.remove('open');
      sidebarOverlay.classList.remove('active');
    }
  });
  
  // Confirm delete actions
  const deleteForms = document.querySelectorAll('[data-confirm]');
  deleteForms.forEach(form => {
    form.addEventListener('submit', (e) => {
      const message = form.getAttribute('data-confirm') || 'Are you sure you want to proceed?';
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });
  
  // Search box focus effect
  const searchBox = document.querySelector('.cems-search-box input');
  if (searchBox) {
    searchBox.addEventListener('focus', () => {
      searchBox.parentElement.classList.add('focused');
    });
    searchBox.addEventListener('blur', () => {
      searchBox.parentElement.classList.remove('focused');
    });
  }
  
  // Table row click for action links
  const tableRows = document.querySelectorAll('.cems-table tbody tr');
  tableRows.forEach(row => {
    const actionLink = row.querySelector('.cems-table-actions a:first-child');
    if (actionLink) {
      row.style.cursor = 'pointer';
      row.addEventListener('click', (e) => {
        if (!e.target.closest('button') && !e.target.closest('form')) {
          window.location.href = actionLink.href;
        }
      });
    }
  });
  
  // Lightbox for gallery
  const galleryItems = document.querySelectorAll('.cems-gallery-item');
  const lightbox = document.getElementById('cems-lightbox');
  const lightboxImg = document.getElementById('cems-lightbox-img');
  const lightboxClose = document.getElementById('cems-lightbox-close');
  
  galleryItems.forEach(item => {
    item.addEventListener('click', () => {
      const img = item.querySelector('img');
      if (img && lightbox && lightboxImg) {
        lightboxImg.src = img.src;
        lightbox.classList.add('active');
      }
    });
  });
  
  if (lightboxClose && lightbox) {
    lightboxClose.addEventListener('click', () => {
      lightbox.classList.remove('active');
    });
    
    lightbox.addEventListener('click', (e) => {
      if (e.target === lightbox) {
        lightbox.classList.remove('active');
      }
    });
  }
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Escape to close modals/lightbox
    if (e.key === 'Escape') {
      if (lightbox) lightbox.classList.remove('active');
      const modal = document.querySelector('.cems-modal-backdrop.active');
      if (modal) modal.classList.remove('active');
    }
    
    // Ctrl+K or / to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('.cems-search-box input');
      if (searchInput) searchInput.focus();
    }
  });
  
  // Global image fallback: replace broken images with placeholder SVG
  const placeholderUrl = '/static/images/placeholder.svg';
  document.addEventListener('error', function(e) {
    if (e.target.tagName === 'IMG' && e.target.src && !e.target.dataset.fallbackApplied) {
      e.target.dataset.fallbackApplied = 'true';
      e.target.src = placeholderUrl;
    }
  }, true);
  
  // Fallback for images that haven't fired error yet (lazy-loaded or cached 404)
  const allImgs = document.querySelectorAll('img[src]:not([onerror])');
  allImgs.forEach(img => {
    img.onerror = function() {
      this.onerror = null;
      this.src = placeholderUrl;
    };
  });
});
