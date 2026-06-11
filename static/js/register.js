document.addEventListener('DOMContentLoaded', () => {

  // --- Password toggle ---
  const toggleBtn = document.getElementById('togglePassword');
  const passwordInput = document.getElementById('password');
  const eyeOpen = document.getElementById('eyeOpen');
  const eyeClosed = document.getElementById('eyeClosed');

  if (toggleBtn && passwordInput) {
    toggleBtn.addEventListener('click', () => {
      const isHidden = passwordInput.type === 'password';
      passwordInput.type = isHidden ? 'text' : 'password';
      eyeOpen.style.display = isHidden ? 'none' : 'block';
      eyeClosed.style.display = isHidden ? 'block' : 'none';
    });
  }

  // --- Form submission with validation ---
  const form = document.getElementById('registerForm');
  const btn = document.getElementById('registerBtn');

  if (form && btn) {
    form.addEventListener('submit', (e) => {
      const username = document.getElementById('username').value.trim();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value.trim();
      const confirmPassword = document.getElementById('confirm_password').value.trim();

      // Validation
      if (!username || !email || !password || !confirmPassword) {
        e.preventDefault();
        showInlineError('Please fill in all fields.');
        return;
      }

      if (!isValidEmail(email)) {
        e.preventDefault();
        showInlineError('Please enter a valid email address.');
        return;
      }

      if (password.length < 6) {
        e.preventDefault();
        showInlineError('Password must be at least 6 characters.');
        return;
      }

      if (password !== confirmPassword) {
        e.preventDefault();
        showInlineError('Passwords do not match.');
        return;
      }

      btn.classList.add('loading');
    });
  }

  // --- Email validation helper ---
  function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
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
    const inputs = ['username', 'email', 'password', 'confirm_password'];
    inputs.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.style.animation = 'none';
      el.style.borderColor = 'var(--accent)';
      setTimeout(() => el.style.borderColor = '', 1500);
    });
  }

  // --- Real-time password match check ---
  const password = document.getElementById('password');
  const confirmPassword = document.getElementById('confirm_password');

  if (password && confirmPassword) {
    confirmPassword.addEventListener('input', () => {
      if (confirmPassword.value && password.value !== confirmPassword.value) {
        confirmPassword.style.borderColor = 'var(--accent)';
      } else {
        confirmPassword.style.borderColor = '';
      }
    });
  }

});
