/**
 * Markets 站：挂载全站产品切换条 + 品牌归属 + 同 tab 站内链
 */
(function () {
  function splitMarketsBrand() {
    var C = window.AI24X_CHROME;
    if (!C) return;
    var www = C.wwwBase().replace(/\/$/, "") + "/";
    var brands = document.querySelectorAll("header .brand, .site-header .brand, .mk-top .brand");
    for (var i = 0; i < brands.length; i++) {
      var brand = brands[i];
      if (brand.getAttribute("data-hub-split") === "1") continue;
      var parent = brand.parentNode;
      if (!parent) continue;
      var group = document.createElement("div");
      group.className = "brand-group";
      group.innerHTML =
        '<a class="brand brand-hub" href="' +
        www +
        '" data-www title="Back to AI24X Home">' +
        '<span class="brand-mark">AI</span><span>AI24X</span></a>' +
        '<span class="brand-sep" aria-hidden="true">·</span>' +
        '<a class="brand brand-local" href="/"><b>Markets</b></a>';
      parent.replaceChild(group, brand);
      brand.setAttribute("data-hub-split", "1");
    }
  }

  function injectEcoStyles() {
    if (document.getElementById("mk-chrome-style")) return;
    var st = document.createElement("style");
    st.id = "mk-chrome-style";
    st.textContent =
      ".brand-group{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap}" +
      ".brand-sep{color:var(--muted);font-weight:700;user-select:none}" +
      ".brand-hub,.brand-local{display:inline-flex;align-items:center;gap:10px;font-weight:800;font-size:16px;color:var(--text);text-decoration:none;white-space:nowrap}" +
      ".brand-hub:hover,.brand-local:hover{text-decoration:none;color:var(--text)}" +
      ".brand-local b{color:var(--accent)}" +
      ".ai24x-hub-brand{display:inline-flex;align-items:center;gap:8px;font-weight:800;font-size:.9rem;color:var(--text);text-decoration:none;margin-right:4px}" +
      ".ai24x-hub-mark{width:26px;height:26px;border-radius:7px;display:grid;place-items:center;font-size:.62rem;font-weight:900;background:var(--accent);color:#fff}" +
      ".ai24x-hub-brand.is-on .ai24x-hub-name{color:var(--accent)}" +
      ".ai24x-eco-hint{margin-left:auto;font-size:.72rem;color:var(--muted);white-space:nowrap}" +
      "@media(max-width:720px){.ai24x-eco-hint{display:none}}";
    (document.head || document.documentElement).appendChild(st);
  }

  function init() {
    var C = window.AI24X_CHROME;
    if (!C) return;
    injectEcoStyles();
    C.syncAuthFromCookie();
    splitMarketsBrand();
    var host = document.getElementById("mk-product-bar");
    if (host && typeof C.mountProductBar === "function") {
      C.mountProductBar(host, "markets");
    }
    if (typeof C.stripInAppNewTab === "function") {
      C.stripInAppNewTab(document);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
