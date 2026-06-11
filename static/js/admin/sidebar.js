// ─────────────────────────────────────────
// sidebar.js  –  ForePay Sidebar
// No event listeners. Runs once on load to
// apply active state to the current nav item
// based on window.location.pathname.
// ─────────────────────────────────────────

// ── Active nav item ───────────────────────
// Maps filename segments to the matching
// nav-item href so the correct link gets
// the .active class regardless of which
// page embeds the sidebar.
const NAV_MAP = {
  'dashboard' : 'dashboard.html',
  'workers'   : 'workers.html',
  'attendance': 'attendance.html',
  'payments'  : 'payments.html',
  'mpesa'     : 'mpesa.html',
  'reports'   : 'reports.html',
  'sites'     : 'sites.html',
  'settings'  : 'settings.html',
};

function setActiveNav() {
  const path     = window.location.pathname;           // e.g. "/app/dashboard.html"
  const filename = path.split('/').pop() || '';        // "dashboard.html"

  // Find which NAV_MAP key matches the current filename
  const matchedHref = Object.values(NAV_MAP).find(
    href => filename.endsWith(href)
  );

  if (!matchedHref) return;

  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href') || '';
    const isActive = href === matchedHref || href.endsWith(matchedHref);

    if (isActive) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

setActiveNav();

// ── Active site name ─────────────────────
// Reads an optional <meta name="forepay-site"> tag so individual
// pages can declare which site is active without JS changes.
//
// Usage in any page:
//   <meta name="forepay-site" content="Kiambu Road Plaza">
function setSiteName() {
  const meta = document.querySelector('meta[name="forepay-site"]');
  if (!meta) return;

  const siteNameEl = document.querySelector('.site-name');
  if (siteNameEl) {
    siteNameEl.textContent = meta.getAttribute('content');
  }
}

setSiteName();

// ── Foreman display name ──────────────────
// Reads an optional <meta name="forepay-user"> tag for the name,
// and <meta name="forepay-role"> for the role label.
//
// Usage:
//   <meta name="forepay-user" content="Jane Wanjiku">
//   <meta name="forepay-role" content="Site Foreman">
function setUserInfo() {
  const nameMeta = document.querySelector('meta[name="forepay-user"]');
  const roleMeta = document.querySelector('meta[name="forepay-role"]');

  if (nameMeta) {
    const nameEl = document.querySelector('.user-name');
    if (nameEl) nameEl.textContent = nameMeta.getAttribute('content');

    // Rebuild initials from first + last word
    const avatarEl = document.querySelector('.avatar');
    if (avatarEl) {
      const parts    = nameMeta.getAttribute('content').trim().split(/\s+/);
      const initials = parts.length >= 2
        ? parts[0][0] + parts[parts.length - 1][0]
        : parts[0].slice(0, 2);
      avatarEl.textContent = initials.toUpperCase();
    }
  }

  if (roleMeta) {
    const roleEl = document.querySelector('.user-role');
    if (roleEl) roleEl.textContent = roleMeta.getAttribute('content');
  }
}

setUserInfo();