/* AI24X a.ai24x.com static offline cache
 *
 * Goals:
 * - Make `index.html` / `demo.html` resilient under weak network.
 * - Keep API calls always network-first (never cache `/api/*`).
 * - Cache vendor chart library if available.
 */
(() => {
  "use strict";

  const CACHE_VERSION = "ai24x-a1-static-v44";
  const CACHE_NAME = CACHE_VERSION;

  /** @param {string} p */
  function urlFromScope(p) {
    return new URL(p, self.registration.scope).toString();
  }

  /** @param {RequestInfo} req */
  function isApiRequest(req) {
    try {
      const u = new URL(typeof req === "string" ? req : req.url);
      return u.pathname.startsWith("/api/") || u.pathname === "/docs" || u.pathname.startsWith("/docs");
    } catch {
      return false;
    }
  }

  self.addEventListener("install", (event) => {
    event.waitUntil(
      (async () => {
        const cache = await caches.open(CACHE_NAME);
        const preCache = [
          // same-dir pages
          urlFromScope("index.html"),
          urlFromScope("account.html"),
          urlFromScope("demo.html"),
          urlFromScope("help.html"),
          urlFromScope("partner.html"),
          urlFromScope("feedback.html"),
          // p/a base styles + shared chrome
          urlFromScope("css/base.css"),
          urlFromScope("css/tool.css"),
          urlFromScope("js/shell.js"),
          // vendor via typical alias (recommended by docs)
          new URL("/vendor/lightweight-charts.standalone.production.js", self.location.origin).toString(),
        ];
        await cache.addAll(preCache);
        await self.skipWaiting();
      })().catch(() => {
        // If vendor isn't exposed (no /vendor alias), addAll may fail; still install.
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
        await Promise.all(keys.map((k) => (k === CACHE_NAME ? Promise.resolve() : caches.delete(k))));
        await self.clients.claim();
      })()
    );
  });

  self.addEventListener("fetch", (event) => {
    const req = event.request;

    // Only cache GET requests
    if (req.method !== "GET") return;

    // Never cache API/docs: always go to network
    if (isApiRequest(req)) {
      event.respondWith(fetch(req));
      return;
    }

    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE_NAME);
        const url = new URL(req.url);
        const isLocal = url.origin === self.location.origin;

        // Critical chrome assets should be network-first so nav updates take effect immediately
        // (avoid "need F5 twice" after deployments).
        try {
          const p = url.pathname || "";
          if (
            isLocal &&
            (p.endsWith("/js/shell.js") ||
              p.endsWith("/css/base.css") ||
              p.endsWith("/css/tool.css") ||
              p.endsWith("/partner.html") ||
              p.endsWith("/index.html") ||
              p.endsWith("/account.html") ||
              p.endsWith("/demo.html") ||
              p.endsWith("/help.html") ||
              p.endsWith("/feedback.html"))
          ) {
            try {
              const resp = await fetch(req, { cache: "no-store" });
              if (resp && resp.ok) cache.put(req, resp.clone()).catch(() => {});
              return resp;
            } catch {
              const cachedCritical = await cache.match(req, { ignoreSearch: true });
              if (cachedCritical) return cachedCritical;
            }
          }
        } catch {}

        // Navigations/HTML: network-first to avoid stale UI; fallback to cache when offline.
        const accept = req.headers.get("accept") || "";
        const isHtml = req.mode === "navigate" || accept.includes("text/html");
        if (isHtml) {
          try {
            const resp = await fetch(req, { cache: "no-store" });
            if (resp.ok && url.origin === self.location.origin) {
              cache.put(req, resp.clone()).catch(() => {});
            }
            return resp;
          } catch {
            const cachedHtml = await cache.match(req, { ignoreSearch: true });
            if (cachedHtml) return cachedHtml;
            const fallback = await cache.match(urlFromScope("index.html"));
            if (fallback) return fallback;
            throw new Response("offline", { status: 503 });
          }
        }

        // Static assets: stale-while-revalidate (avoid "must hard refresh" issues)
        // Do NOT ignore search for assets: allow cache-busting when needed.
        const cached = await cache.match(req);

        if (cached) {
          // Update in background
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
          const fallback = await cache.match(urlFromScope("index.html"));
          if (fallback) return fallback;
          throw new Response("offline", { status: 503 });
        }
      })()
    );
  });
})();

