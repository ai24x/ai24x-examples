/**
 * Markets 站：品牌归属（回 Hub）+ 站内链；不再挂全站产品切换条
 */
(function () {
  function splitMarketsBrand() {
    var C = window.AI24X_CHROME;
    if (!C) return;
    var www = C.wwwBase().replace(/\/$/, "") + "/";
    // 已静态写好 brand-group：只改写 Hub 本机地址，避免再替换造成顶栏跳动
    var hubs = document.querySelectorAll(".brand-group .brand-hub[data-www], .brand-group a.brand-hub");
    for (var h = 0; h < hubs.length; h++) {
      hubs[h].setAttribute("href", www);
    }
    var brands = document.querySelectorAll("header .brand, .site-header .brand, .mk-top .brand");
    for (var i = 0; i < brands.length; i++) {
      var brand = brands[i];
      if (brand.closest(".brand-group")) continue;
      if (brand.getAttribute("data-hub-split") === "1") continue;
      var parent = brand.parentNode;
      if (!parent) continue;
      var group = document.createElement("div");
      group.className = "brand-group";
      group.setAttribute("data-hub-split", "1");
      group.innerHTML =
        '<a class="brand brand-hub" href="' +
        www +
        '" data-www title="Back to AI24X Home">' +
        '<span class="brand-mark">AI</span><span>AI24X</span></a>' +
        '<span class="brand-sep" aria-hidden="true">·</span>' +
        '<a class="brand brand-local" href="/"><b>Markets</b></a>';
      parent.replaceChild(group, brand);
    }
  }

  function injectEcoStyles() {
    // 样式已进 mk-site.css；保留空实现兼容旧页
  }

  function wireAuthLinks() {
    var C = window.AI24X_CHROME;
    var www = "";
    try {
      if (C && typeof C.wwwBase === "function") www = C.wwwBase().replace(/\/$/, "");
      else if (typeof window.AI24X_WWW_BASE === "function") www = String(window.AI24X_WWW_BASE() || "").replace(/\/$/, "");
    } catch (e) {}
    if (!www) {
      var h = String(location.hostname || "").toLowerCase();
      www = h === "127.0.0.1" || h === "localhost" ? "http://127.0.0.1:8000" : "https://www.ai24x.com";
    }
    var back = encodeURIComponent(location.href);
    var s = document.getElementById("signin-link");
    if (s) s.href = www + "/login.html?next=" + back;
    var su = document.getElementById("signup-link");
    if (su) su.href = www + "/register.html?next=" + back;
  }

  function init() {
    var C = window.AI24X_CHROME;
    if (!C) return;
    injectEcoStyles();
    C.syncAuthFromCookie();
    splitMarketsBrand();
    wireAuthLinks();
    var host = document.getElementById("mk-product-bar");
    if (host) host.innerHTML = "";
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
