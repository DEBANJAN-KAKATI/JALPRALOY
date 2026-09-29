// Offline-first service worker. Networks fail during floods: the last synced
// forecast and the app shell must stay available.
//   app shell  -> cache-first
//   /api/*     -> network-first, fall back to the last cached response
const SHELL = "jalproloi-shell-v2";
const DATA = "jalproloi-data-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/index.html", "/manifest.webmanifest", "/emblem.png", "/favicon.png", "/icon-192.png"])));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => ![SHELL, DATA].includes(k)).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(DATA).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request).then((r) => r || new Response('{"detail":"offline"}', { status: 503 }))),
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(
      (cached) =>
        cached ||
        fetch(event.request).then((res) => {
          if (res.ok && url.origin === self.location.origin) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(event.request, copy));
          }
          return res;
        }),
    ),
  );
});

// Web push (wire up with the backend's VAPID keys — docs/08_ALERTS_CAP.md)
self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : { title: "JalProloy", body: "New flood warning" };
  event.waitUntil(self.registration.showNotification(data.title, { body: data.body, icon: "/icon-192.png" }));
});
