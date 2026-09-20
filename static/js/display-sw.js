const CACHE = 'flatscreen-display-shell-v4';
const SHELL = '/display/offline/';
const ASSETS = [SHELL, '/appearance.css', '/appearance-display.css', '/static/css/app.css', '/static/css/design.css', '/static/js/app.js', '/static/mark.svg'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('flatscreen-display-shell-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== 'GET') return;
  if (event.request.mode === 'navigate' && url.pathname === '/display/') {
    event.respondWith(fetch(event.request).then(r => r.status >= 500 ? caches.match(SHELL) : r).catch(() => caches.match(SHELL)));
  } else if (ASSETS.includes(url.pathname)) {
    event.respondWith(fetch(event.request).then(response => {
      if (response.ok) { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); }
      return response;
    }).catch(() => caches.match(event.request)));
  }
});
