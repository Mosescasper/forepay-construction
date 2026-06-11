document.addEventListener('DOMContentLoaded', () => {

  // --- Password toggle ---
  const toggleBtn = document.getElementById('togglePassword');
  const passwordInput = document.getElementById('login-password');

  if (toggleBtn && passwordInput) {
    const eyeOpen = toggleBtn.querySelector('.eye-open');
    const eyeClosed = toggleBtn.querySelector('.eye-closed');

    toggleBtn.addEventListener('click', () => {
      const isHidden = passwordInput.type === 'password';
      passwordInput.type = isHidden ? 'text' : 'password';
      if (eyeOpen && eyeClosed) {
        eyeOpen.style.display = isHidden ? 'none' : 'block';
        eyeClosed.style.display = isHidden ? 'block' : 'none';
      }
    });
  }

  // --- Form submission with loading state ---
  const form = document.getElementById('loginForm');
  const btn = document.getElementById('loginBtn');

  if (form && btn) {
    form.addEventListener('submit', (e) => {
      const usernameInput = document.getElementById('login-username');
      const passwordInput = document.getElementById('login-password');
      const username = usernameInput ? usernameInput.value.trim() : '';
      const password = passwordInput ? passwordInput.value.trim() : '';

      if (!username || !password) {
        e.preventDefault();
        showInlineError('Please fill in all fields.');
        return;
      }

      btn.classList.add('loading');
    });
  }

  // --- Auto-dismiss flash messages ---
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach((flash, i) => {
    setTimeout(() => {
      flash.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      flash.style.opacity = '0';
      flash.style.transform = 'translateX(8px)';
      setTimeout(() => flash.remove(), 400);
    }, 3500 + i * 300);
  });

  // --- Inline error helper ---
  function showInlineError(message) {
    const existing = document.querySelector('.flash.inline-error');
    if (existing) existing.remove();

    const flashBox = document.querySelector('.flash-messages');
    if (!flashBox) return;

    const div = document.createElement('div');
    div.className = 'flash error inline-error';
    div.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
           fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      ${message}
    `;
    flashBox.prepend(div);

    setTimeout(() => {
      div.style.transition = 'opacity 0.4s ease';
      div.style.opacity = '0';
      setTimeout(() => div.remove(), 400);
    }, 3000);
  }

  // --- Input shake on error flash ---
  const errorFlash = document.querySelector('.flash.error');
  if (errorFlash) {
    [document.getElementById('login-username'), document.getElementById('login-password')]
      .forEach(el => {
        if (!el) return;
        el.style.animation = 'none';
        el.style.borderColor = 'var(--error)';
        setTimeout(() => el.style.borderColor = '', 1500);
      });
  }

});