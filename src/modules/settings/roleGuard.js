export function getCurrentUser() {
  try {
    const raw = sessionStorage.getItem('aic_session');
    if (!raw) return null;
    const session = JSON.parse(raw);
    return session.user || null;
  } catch {
    return null;
  }
}

export function isAdmin() {
  const user = getCurrentUser();
  if (!user) return false;
  const role = String(user.role || user.Role || '').toLowerCase();
  return role === 'admin';
}

export function getUserRole() {
  const user = getCurrentUser();
  if (!user) return 'guest';
  return String(user.role || user.Role || 'user').toLowerCase();
}