/* AI24X Markets (markets.ai24x.com) static offline cache
 *
 * Goals:
 * - Make app.html / index.html / screener.html resilient under weak network.
 * - Keep API calls always network-first (never cache /api/*).
 * - HTML navigations network-first (deploy updates appear immediately);
 *   static assets stale-while-revalidate; offline falls back to cache.
 */
(() => {
  "use strict";

  const CACHE_VERSION = "ai24x-markets-static-v1";
  const CACHE_NAME = CACHE_VERSION;

  function urlFromScope(p) {
    return new URL(p, self.registration.scope).toString();
  }

  function isApiRequest(req) {
    try {
      const u = new URL(typeof req === "string" ? req : req.url);
      return (
        u.pathname.startsWith("/api/") ||
        u.pathname === "/docs" ||
        u.pathname.startsWith("/docs")
      );
    } catch {
      return false;
    }
  }

  self.addEventListener("install", (event) => {
    event.waitUntil(
      (async () => {
        const cache = await caches.open(CACHE_NAME);
        const preCache = [
          urlFromScope("app.html"),
          urlFromScope("index.html"),
          urlFromScope("screener.html"),
          urlFromScope("pricing.html"),
          urlFromScope("manifest.webmanifest"),
          urlFromScope("icons/icon-192.png"),
          urlFromScope("icons/icon-512.png"),
          urlFromScope("vendor/lightweight-charts.standalone.production.js"),
        ];
        await cache.addAll(preCache);
        await self.skipWaiting();
      })().catch(() => {
        // If any optional asset fails, still install (offline shell stays usable).
        return self.skipWaiting();
      })
    );
  });

  self.addEventListener("message", (event) => {
    try {
      const data = event && event.data ? event.data : null;
      if (data && data.type === "SKIP_WAITING") {
        self.skipWaiting();
      }
    } catch {}
  });

  self.addEventListener("activate", (event) => {
    event.waitUntil(
      (async () => {
        const keys = await caches.keys();
        await Promise.all(
          keys.map((k) => (k === CACHE_NAME ? Promise.resolve() : caches.delete(k)))
        );
        await self.clients.claim();
      })()
    );
  });

  self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") return;

    // API/docs: always network, never cached.
    if (isApiRequest(req)) {
      event.respondWith(fetch(req));
      return;
    }

    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE_NAME);
        const url = new URL(req.url);
        const isLocal = url.origin === self.location.origin;

        // HTML navigations: network-first so updates apply on first visit.
        const accept = req.headers.get("accept") || "";
        const isHtml = req.mode === "navigate" || accept.includes("text/html");
        if (isHtml) {
          try {
            const resp = await fetch(req, { cache: "no-store" });
            if (resp.ok && isLocal) cache.put(req, resp.clone()).catch(() => {});
            return resp;
          } catch {
            const cachedHtml = await cache.match(req, { ignoreSearch: true });
            if (cachedHtml) return cachedHtml;
            const fallback = await cache.match(urlFromScope("app.html"));
            if (fallback) return fallback;
            throw new Response("offline", { status: 503 });
          }
        }

        // Static assets: stale-while-revalidate.
        const cached = await cache.match(req);
        if (cached) {
          fetch(req)
            .then((resp) => {
              if (resp && resp.ok && isLocal) cache.put(req, resp.clone()).catch(() => {});
            })
            .catch(() => {});
          return cached;
        }

        try {
          const resp = await fetch(req);
          if (resp.ok && isLocal) cache.put(req, resp.clone()).catch(() => {});
          return resp;
        } catch {
          const fallback = await cache.match(urlFromScope("app.html"));
          if (fallback) return fallback;
          throw new Response("offline", { status: 503 });
        }
      })()
    );
  });
})();
