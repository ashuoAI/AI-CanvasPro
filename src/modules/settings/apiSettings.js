import { isAdmin } from './roleGuard.js';

const RESTRICTED_PANES = ['pane-api-input', 'pane-file-save'];

function disablePaneControls(paneId) {
  const pane = document.getElementById(paneId);
  if (!pane) return;

  const inputs = pane.querySelectorAll('input, textarea, select');
  const buttons = pane.querySelectorAll('button');

  inputs.forEach(el => {
    el.disabled = true;
    el.classList.add('settings-input-locked');
  });

  buttons.forEach(el => {
    el.disabled = true;
    el.classList.add('settings-btn-locked');
  });
}

function addPermissionBanner(paneId) {
  const pane = document.getElementById(paneId);
  if (!pane) return;

  const body = pane.querySelector('.settings-pane-body');
  if (!body) return;

  const banner = document.createElement('div');
  banner.className = 'settings-permission-banner';
  banner.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> 仅管理员可编辑此设置`;
  body.insertBefore(banner, body.firstChild);
}

function addNavLockIcon(paneId) {
  const navItem = document.querySelector(`.settings-nav-item[data-pane="${paneId.replace('pane-', '')}"]`);
  if (!navItem) return;

  const lockIcon = document.createElement('span');
  lockIcon.className = 'settings-nav-lock';
  lockIcon.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;
  navItem.appendChild(lockIcon);
  navItem.classList.add('settings-nav-item-restricted');
}

export function initApiSettings() {
  if (isAdmin()) return;

  RESTRICTED_PANES.forEach(paneId => {
    disablePaneControls(paneId);
    addPermissionBanner(paneId);
    addNavLockIcon(paneId);
  });
}