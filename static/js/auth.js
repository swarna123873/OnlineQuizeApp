/**
 * Authentication handling: Role toggling, password complexity checks, and validation.
 */
document.addEventListener('DOMContentLoaded', () => {
  const roleCards = document.querySelectorAll('.role-card');
  const roleInput = document.getElementById('selected-role');
  const authForm = document.getElementById('auth-form');
  const submitBtn = document.getElementById('submit-btn');
  const errorMessageContainer = document.getElementById('error-message-container');
  const passwordInput = document.getElementById('password');

  // Role card selection logic
  if (roleCards.length > 0) {
    roleCards.forEach(card => {
      card.addEventListener('click', () => {
        roleCards.forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        const role = card.getAttribute('data-role');
        if (roleInput) {
          roleInput.value = role;
        }
        const radio = card.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
        }
      });
    });
  }

  // Live password complexity check (Registration page)
  if (passwordInput && document.getElementById('rule-length')) {
    const ruleLength = document.getElementById('rule-length');
    const ruleLetter = document.getElementById('rule-letter');
    const ruleNumber = document.getElementById('rule-number');
    const ruleSpecial = document.getElementById('rule-special');

    passwordInput.addEventListener('input', () => {
      const val = passwordInput.value;

      updateRule(ruleLength, val.length >= 6, '• At least 6 characters');
      updateRule(ruleLetter, /[a-zA-Z]/.test(val), '• At least one letter (a-z, A-Z)');
      updateRule(ruleNumber, /[0-9]/.test(val), '• At least one number (0-9)');
      updateRule(ruleSpecial, /[!@#$%^&*(),.?":{}|<>\-_]/.test(val), '• At least one special character (!@#$%^&*)');
    });

    function updateRule(element, isValid, text) {
      if (!element) return;
      if (isValid) {
        element.style.color = '#10b981';
        element.innerHTML = `<span>✓ ${text.replace('• ', '')}</span>`;
      } else {
        element.style.color = 'var(--text-muted)';
        element.innerHTML = `<span>• ${text.replace('• ', '').replace('✓ ', '')}</span>`;
      }
    }
  }

  // Display error message dynamically
  function showError(msg) {
    if (!errorMessageContainer) return;
    errorMessageContainer.innerHTML = `
      <div class="alert alert-error">
        <span>${msg}</span>
      </div>
    `;
    errorMessageContainer.scrollIntoView({ behavior: 'smooth' });
  }

  function clearError() {
    if (errorMessageContainer) {
      errorMessageContainer.innerHTML = '';
    }
  }

  // Handle Form Submission Validation
  if (authForm) {
    authForm.addEventListener('submit', (e) => {
      // Validate role if on login/register with role selector
      const roleCardsExist = document.querySelectorAll('.role-card').length > 0;
      if (roleCardsExist) {
        const activeCard = document.querySelector('.role-card.active');
        const selectedRole = activeCard ? activeCard.getAttribute('data-role') : (roleInput ? roleInput.value : '');

        if (!selectedRole) {
          e.preventDefault();
          showError('Please select your account role (Educator/School or Student).');
          return;
        }
      }

      const emailInput = document.getElementById('email');
      if (!emailInput || !emailInput.value.trim()) {
        e.preventDefault();
        showError('Please enter your email address.');
        emailInput?.focus();
        return;
      }

      if (passwordInput && !passwordInput.value) {
        e.preventDefault();
        showError('Please enter your password.');
        passwordInput?.focus();
        return;
      }

      // Check password complexity rule on registration form
      if (document.getElementById('rule-length') && passwordInput) {
        const val = passwordInput.value;
        const validLength = val.length >= 6;
        const hasLetter = /[a-zA-Z]/.test(val);
        const hasNumber = /[0-9]/.test(val);
        const hasSpecial = /[!@#$%^&*(),.?":{}|<>\-_]/.test(val);

        if (!validLength || !hasLetter || !hasNumber || !hasSpecial) {
          e.preventDefault();
          showError('Password must be at least 6 characters and include letters, numbers, and special characters.');
          passwordInput.focus();
          return;
        }
      }

      clearError();
    });
  }
});
