// Scouting FC: guarda en el móvil los archivos ya abiertos (se ve sin conexión y carga más rápido).
// Siempre intenta la red primero para que los datos semanales nuevos se vean en cuanto están publicados.
const CACHE = "scoutingfc-v1";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const c = r.clone(); caches.open(CACHE).then(k => k.put(e.request, c)); }
    return r;
  }).catch(() => caches.match(e.request)));
});
