const API = {
  USER: 'http://localhost:8001',
  DONATION: 'http://localhost:8002',
  ALGORITHM: 'http://localhost:8003',
  DELIVERY: 'http://localhost:8005',
  FILE: 'http://localhost:8006',
};

function apiCall(method, url, data) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (data && method !== 'GET') opts.body = JSON.stringify(data);
  return fetch(url, opts)
    .then(async (res) => {
      const json = await res.json().catch(() => null);
      if (!res.ok) throw new Error(json?.detail || json?.message || `Request failed (${res.status})`);
      return json;
    });
}

function formatDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function formatShortDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function showAlert(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = '0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem('fw_user'));
  } catch { return null; }
}

function setUser(data) {
  localStorage.setItem('fw_user', JSON.stringify(data));
}

function logout() {
  localStorage.removeItem('fw_user');
  window.location.href = 'login.html';
}

function requireRole(role) {
  const user = getUser();
  if (!user) { window.location.href = 'login.html'; return null; }
  if (role && user.role && user.role.toLowerCase() !== role.toLowerCase()) { window.location.href = 'login.html'; return null; }
  return user;
}

function getDistance(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function connectWebSocket(url, onMessage, onOpen, onClose) {
  let ws;
  let retries = 0;
  const maxRetries = 10;
  const baseDelay = 1000;

  function connect() {
    ws = new WebSocket(url);
    ws.onopen = () => {
      retries = 0;
      if (onOpen) onOpen(ws);
    };
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onMessage(data, ws);
      } catch {
        onMessage(e.data, ws);
      }
    };
    ws.onclose = () => {
      if (onClose) onClose();
      if (retries < maxRetries) {
        const delay = baseDelay * Math.min(2 ** retries, 30);
        retries++;
        setTimeout(connect, delay);
      }
    };
    ws.onerror = () => ws.close();
  }
  connect();
  return { close: () => { retries = maxRetries; if (ws) ws.close(); } };
}

function formatVectorClock(vector) {
  if (!vector || typeof vector !== 'object') return '-';
  const labels = { D: 'Donation', M: 'Matching', I: 'Inventory', V: 'Delivery' };
  return Object.entries(vector)
    .map(([k, v]) => `${labels[k] || k}:${v}`)
    .join(' ');
}

function getExpiryCountdown(expiryIso) {
  if (!expiryIso) return { text: 'No expiry', cls: 'safe' };
  const diff = new Date(expiryIso) - new Date();
  if (diff <= 0) return { text: 'Expired', cls: 'danger' };
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  if (hours > 24) return { text: `${Math.floor(hours / 24)}d ${hours % 24}h`, cls: 'safe' };
  if (hours > 6) return { text: `${hours}h ${mins}m`, cls: 'safe' };
  if (hours > 1) return { text: `${hours}h ${mins}m`, cls: 'warning' };
  return { text: `${mins}m`, cls: 'danger' };
}

function statusBadge(status) {
  const cls = (status || '').toLowerCase().replace(/\s+/g, '_');
  return `<span class="badge badge-${cls}">${status}</span>`;
}

function renderHeader(user, activeTab) {
  return `
    <header class="site-header">
      <div class="logo">&#127860; <span>FoodRedist</span></div>
      <nav>
        <span class="user-info">${user.name || user.email || 'User'} (${user.role})</span>
        <button class="btn btn-ghost btn-sm" onclick="logout()">Logout</button>
      </nav>
    </header>`;
}
