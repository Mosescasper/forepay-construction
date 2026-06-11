/* ============================================================
   FOREPAY — index.js
   Landing page interactions: mock dashboard, pay button,
   workflow steps highlight, feature card hover effects
   ============================================================ */

(function () {
  'use strict';

  /* ── Mock dashboard pay button ────────────────────────────── */
  const mockPayBtn = document.querySelector('.mock-pay-btn');

  if (mockPayBtn) {
    mockPayBtn.addEventListener('click', () => {
      const original = mockPayBtn.textContent;
      mockPayBtn.textContent = '✓ Payments Sent!';
      mockPayBtn.style.background = '#0F6E56';
      setTimeout(() => {
        mockPayBtn.textContent = original;
        mockPayBtn.style.background = '';
      }, 2000);
    });
  }

  /* ── Mock KPI counter animation on hero visible ───────────── */
  function animateCounter(el, target, suffix = '') {
    const duration = 1600;
    const start    = performance.now();

    const step = (now) => {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease     = 1 - Math.pow(1 - progress, 3); // ease-out-cubic
      const current  = Math.round(target * ease);
      el.textContent = current.toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  const heroStatsObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.querySelectorAll('.stat-num[data-count]').forEach(el => {
          const val    = parseFloat(el.dataset.count);
          const suffix = el.dataset.suffix || '';
          animateCounter(el, val, suffix);
        });
        heroStatsObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  const heroStats = document.querySelector('.hero-stats');
  if (heroStats) heroStatsObserver.observe(heroStats);

  /* ── Workflow step highlight on scroll ────────────────────── */
  const flowSteps = document.querySelectorAll('.flow-step');

  const flowObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.borderColor = '#1D9E75';
        entry.target.style.transition  = 'border-color 0.4s ease';
      } else {
        entry.target.style.borderColor = '';
      }
    });
  }, { threshold: 0.6 });

  flowSteps.forEach(step => flowObserver.observe(step));

  /* ── Feature card tilt on mouse move ──────────────────────── */
  const featCards = document.querySelectorAll('.feat-card');

  featCards.forEach(card => {
    card.addEventListener('mousemove', e => {
      const rect   = card.getBoundingClientRect();
      const x      = e.clientX - rect.left;
      const y      = e.clientY - rect.top;
      const centerX = rect.width  / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -4;
      const rotateY = ((x - centerX) / centerX) *  4;
      card.style.transform    = `perspective(600px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.02)`;
      card.style.transition   = 'transform 0.1s ease';
    });

    card.addEventListener('mouseleave', () => {
      card.style.transform  = '';
      card.style.transition = 'transform 0.4s ease, border-color 0.2s';
    });
  });

  /* ── Mock table row highlight ─────────────────────────────── */
  const mockRows = document.querySelectorAll('.mock-row:not(.head)');

  mockRows.forEach(row => {
    row.addEventListener('mouseenter', () => {
      row.style.background  = 'rgba(29,158,117,0.08)';
      row.style.cursor      = 'pointer';
    });
    row.addEventListener('mouseleave', () => {
      row.style.background  = '';
    });
  });

  /* ── CTA button pulse on hover ────────────────────────────── */
  const ctaBtns = document.querySelectorAll('.cta-section .btn-primary');

  ctaBtns.forEach(btn => {
    btn.addEventListener('mouseenter', () => {
      btn.style.transform  = 'scale(1.04)';
      btn.style.transition = 'transform 0.2s ease';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.transform  = '';
    });
  });

})();