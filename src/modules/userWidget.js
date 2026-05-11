import { getCurrentUser } from './settings/roleGuard.js';

const LOGIN_PAGE_URL = '/login.html';
const SESSION_KEY = 'aic_session';

function redirectToLogin() {
  const returnUrl = encodeURIComponent(window.location.href);
  window.location.href = LOGIN_PAGE_URL + '?redirect=' + returnUrl;
}

(function authGuard() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      const user = getCurrentUser();
      if (!user) {
        redirectToLogin();
      }
    });
  } else {
    const user = getCurrentUser();
    if (!user) {
      redirectToLogin();
    }
  }
})();

function updateUI() {
  const loggedOutEl = document.getElementById('userWidgetLoggedOut');
  const loggedInEl = document.getElementById('userWidgetLoggedIn');
  const nameEl = document.getElementById('userWidgetName');
  const roleEl = document.getElementById('userWidgetRole');
  const avatarEl = document.getElementById('userWidgetAvatar');

  if (!loggedOutEl || !loggedInEl) return;

  const user = getCurrentUser();

  if (user) {
    loggedOutEl.hidden = true;
    loggedInEl.hidden = false;

    const displayName = user.username || user.name || user.Username || user.Name || '用户';
    const role = user.role || user.Role || 'user';
    const roleLabel = role === 'admin' ? '管理员' : '用户';

    if (nameEl) nameEl.textContent = displayName;
    if (roleEl) {
      roleEl.textContent = roleLabel;
      roleEl.className = 'user-widget-role' + (role === 'admin' ? ' user-widget-role-admin' : '');
    }
    if (avatarEl) {
      avatarEl.textContent = displayName.charAt(0).toUpperCase();
    }
  } else {
    loggedOutEl.hidden = false;
    loggedInEl.hidden = true;
  }
}

function handleLogin() {
  redirectToLogin();
}

function handleLogout() {
  sessionStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(SESSION_KEY);
  window.location.href = LOGIN_PAGE_URL;
}

function bindEvents() {
  const loginBtn = document.getElementById('btnUserLogin');
  const logoutBtn = document.getElementById('btnUserLogout');

  if (loginBtn) {
    loginBtn.addEventListener('click', handleLogin);
  }
  if (logoutBtn) {
    logoutBtn.addEventListener('click', handleLogout);
  }
}

function initUserWidget() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      updateUI();
      bindEvents();
    });
  } else {
    updateUI();
    bindEvents();
  }
}

export { initUserWidget, updateUI, getCurrentUser };

initUserWidget();