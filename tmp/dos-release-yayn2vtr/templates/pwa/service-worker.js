// No Cache Storage, offline records, or background submission queue.
const OFFLINE_HTML = "{{ offline_html|escapejs }}";

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  // Let the browser handle mutations, HTMX, assets and other origins normally.
  if (request.method !== 'GET' || request.mode !== 'navigate' ||
      new URL(request.url).origin !== self.location.origin) return;

  event.respondWith(fetch(request, { cache: 'no-store' }).catch(() =>
    new Response(OFFLINE_HTML, {
      status: 503,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
        'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
      },
    })
  ));
});
