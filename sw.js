// Minimal service worker: it makes the blogger app installable. Pages always come from the network, never from a cache,
// so the editor and the site are never out of date.
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function (e) { e.respondWith(fetch(e.request)); });
