// ─────────────────────────────────────────
// dashboard.js  –  ForePay Dashboard
// No event listeners. DOM must be ready
// before this script runs (place at end of
// <body> or use defer attribute).
// ─────────────────────────────────────────

// ── Date display ──────────────────────────
const dateEl = document.getElementById('topbar-date');
if (dateEl) {
  const now = new Date();
  dateEl.textContent = now.toLocaleDateString('en-KE', {
    weekday : 'long',
    day     : 'numeric',
    month   : 'long',
    year    : 'numeric',
  });
}

// ── Weekly attendance bar chart ───────────
const ATTENDANCE = {
  days    : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
  present : [22, 20, 23, 21, 0],
  half    : [ 1,  2,  1,  2, 0],
  absent  : [ 1,  2,  0,  3, 0],
  total   : 24,          // total workers on site
  today   : 3,           // 0-based index of current day (Thu = 3)
};

function buildBarChart(chartEl, data) {
  const { days, present, half, absent, total, today } = data;

  days.forEach((day, i) => {
    const col = document.createElement('div');
    col.className = 'bar-col';

    const makeBar = (val, color) => {
      const bar   = document.createElement('div');
      bar.className = 'bar';
      const heightPx = Math.round((val / total) * 90);
      const opacity  = i === today ? '1' : '0.6';
      bar.style.cssText =
        `height:${heightPx}px;background:${color};opacity:${opacity}`;
      return bar;
    };

    if (i < today + 1) {
      // Days with recorded data
      col.appendChild(makeBar(present[i], 'var(--accent)'));
      col.appendChild(makeBar(half[i],    'var(--amber)'));
      col.appendChild(makeBar(absent[i],  'var(--red)'));
    } else {
      // Future days – placeholder column
      const placeholder = document.createElement('div');
      placeholder.style.cssText =
        'flex:1;border:1px dashed var(--border);border-radius:4px;opacity:.4;width:100%';
      col.appendChild(placeholder);
    }

    const label = document.createElement('div');
    label.className = 'bar-label';
    label.textContent = day + (i === today ? ' ●' : '');
    if (i === today) label.style.color = 'var(--accent)';
    col.appendChild(label);

    chartEl.appendChild(col);
  });
}

const chartEl = document.getElementById('bar-chart');
if (chartEl) {
  buildBarChart(chartEl, ATTENDANCE);
}