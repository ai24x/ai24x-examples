/**
 * AI24X 跨站统一壳层：产品切换条 + 会话读写 + 同 tab 站内跳转
 * www / open / markets 共用（各站复制或同源加载此文件）
 */
(function (global) {
  var AUTH_COOKIE = "ai24x_auth_token";
  var AUTH_USER_COOKIE = "ai24x_auth_user";
  var WWW_PROD = "https://www.ai24x.com";
  var API_PROD = "https://api.ai24x.com";

  /** 计费 API 基址（markets 支付弹窗用 api 子域，非 www 静态站） */
  function apiBase() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      if (h === "127.0.0.1" || h === "localhost") return "http://127.0.0.1:8000";
    } catch (e) {}
    return API_PROD;
  }

  // 兜底：EdgeOne/浏览器若仍缓存旧 app.html（hubFetch 打 www），改写为 api.ai24x.com
  if (typeof global.fetch === "function" && !global.__ai24xBillingFetchPatched) {
    global.__ai24xBillingFetchPatched = true;
    var nativeFetch = global.fetch.bind(global);
    global.fetch = function (input, init) {
      var url = typeof input === "string" ? input : input && input.url;
      if (typeof url === "string" && url.indexOf(WWW_PROD + "/v1/billing") === 0) {
        var fixed = API_PROD + url.slice(WWW_PROD.length);
        if (typeof input === "string") input = fixed;
        else input = new Request(fixed, input);
      }
      return nativeFetch(input, init);
    };
  }

  function preferLocalProducts() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      if (h !== "127.0.0.1" && h !== "localhost") return false;
      try {
        return String(localStorage.getItem("ai24x_local_products") || "").trim() !== "0";
      } catch (e) {
        return true;
      }
    } catch (e) {
      return false;
    }
  }

  function wwwBase() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      if ((h === "127.0.0.1" || h === "localhost") && preferLocalProducts()) {
        return "http://127.0.0.1:8000";
      }
    } catch (e) {}
    return "https://www.ai24x.com";
  }

  function openUrl() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      var port = String(location.port || "");
      if (h === "127.0.0.1" || h === "localhost") {
        if (port === "18080") return "http://127.0.0.1:18080/";
        if (preferLocalProducts()) return "http://127.0.0.1:18080/";
      }
    } catch (e) {}
    return "https://open.ai24x.com/";
  }

  function marketsUrl() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      var port = String(location.port || "");
      if (h === "127.0.0.1" || h === "localhost") {
        if (port === "18012") return "http://127.0.0.1:18012/";
        if (preferLocalProducts()) return "http://127.0.0.1:18012/";
      }
    } catch (e) {}
    return "https://markets.ai24x.com/";
  }

  /** 国内 AI 行情官（独立垂直应用，Hub 新窗打开） */
  function a1Url() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      var port = String(location.port || "");
      if (h === "127.0.0.1" || h === "localhost") {
        if (port === "18001" || port === "18003") return "http://127.0.0.1:18001/";
        if (preferLocalProducts()) return "http://127.0.0.1:18001/";
      }
    } catch (e) {}
    return "https://a.ai24x.com/";
  }

  function hubUrl() {
    return wwwBase().replace(/\/$/, "") + "/console.html";
  }

  function gatewayWorkspaceUrl() {
    return openUrl().replace(/\/$/, "") + "/console.html";
  }

  function siteKind() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      var port = String(location.port || "");
      if (h === "open.ai24x.com" || port === "18080") return "gateway";
      if (h === "markets.ai24x.com" || port === "18012") return "markets";
    } catch (e) {}
    return "www";
  }

  function authCookieDomain() {
    var h = (location.hostname || "").toLowerCase();
    return h === "ai24x.com" || h.endsWith(".ai24x.com") ? ".ai24x.com" : "";
  }

  function readCookie(name) {
    try {
      var esc = name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1");
      var m = document.cookie.match(new RegExp("(?:^|; )" + esc + "=([^;]*)"));
      return m ? decodeURIComponent(m[1]) : "";
    } catch (e) {
      return "";
    }
  }

  function authToken() {
    try {
      var ls = localStorage.getItem("ai24x_auth_token") || "";
      if (ls) return ls;
    } catch (e) {}
    return readCookie(AUTH_COOKIE) || "";
  }

  function ingestOauthFragment() {
    try {
      var hash = (location.hash || "").replace(/^#/, "");
      if (!hash || hash.indexOf("oauth=1") < 0) return;
      var params = new URLSearchParams(hash);
      var tok = params.get("access_token") || "";
      if (!tok) return;
      try {
        localStorage.setItem("ai24x_auth_token", tok);
      } catch (e0) {}
      var rawUser = params.get("user");
      if (rawUser) {
        try {
          localStorage.setItem("ai24x_auth_user", rawUser);
        } catch (e1) {}
      }
      try {
        history.replaceState(null, "", location.pathname + (location.search || ""));
      } catch (e2) {
        try {
          location.hash = "";
        } catch (e3) {}
      }
    } catch (e) {}
  }

  function syncAuthFromCookie() {
    try {
      var token = readCookie(AUTH_COOKIE);
      if (!token) return;
      if (localStorage.getItem("ai24x_auth_token") === token) return;
      localStorage.setItem("ai24x_auth_token", token);
      var raw = readCookie(AUTH_USER_COOKIE);
      if (raw) {
        try {
          localStorage.setItem("ai24x_auth_user", raw);
        } catch (e) {}
      }
    } catch (e) {}
  }

  function bootstrapAuthFromSession() {
    try {
      var ls = "";
      try {
        ls = localStorage.getItem("ai24x_auth_token") || "";
      } catch (e0) {}
      if (ls) return;
      if (!authCookieDomain()) return;
      fetch("https://api.ai24x.com/v1/auth/session", {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          return r.ok ? r.json() : null;
        })
        .then(function (data) {
          if (!data) return;
          var tok = data.access_token || data.token;
          if (!tok) return;
          try {
            localStorage.setItem("ai24x_auth_token", tok);
            if (data.user)
              localStorage.setItem("ai24x_auth_user", JSON.stringify(data.user));
          } catch (e1) {}
        })
        .catch(function () {});
    } catch (e) {}
  }

  function clearAuthSession() {
    try {
      if (global.AI24X_API && typeof global.AI24X_API.logout === "function") {
        global.AI24X_API.logout();
        return;
      }
    } catch (e) {}
    try {
      localStorage.removeItem("ai24x_auth_token");
      localStorage.removeItem("ai24x_auth_user");
    } catch (e2) {}
    try {
      var d = authCookieDomain();
      var secure = location.protocol === "https:" ? "; Secure" : "";
      document.cookie = AUTH_COOKIE + "=; path=/; max-age=0; SameSite=Lax" + (d ? "; domain=" + d : "") + secure;
      document.cookie = AUTH_USER_COOKIE + "=; path=/; max-age=0; SameSite=Lax" + (d ? "; domain=" + d : "") + secure;
    } catch (e3) {}
    try {
      fetch("https://api.ai24x.com/v1/auth/logout", {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      }).catch(function () {});
    } catch (e4) {}
  }

  function isAi24xUrl(href) {
    return /^(https?:\/\/)?([a-z0-9-]+\.)?ai24x\.com(\/|$)/i.test(String(href || ""));
  }

  /** 站内默认同 tab；Markets / data-hub-external 保留新窗口（独立产品） */
  function stripInAppNewTab(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll('a[target="_blank"]');
    for (var i = 0; i < nodes.length; i++) {
      var a = nodes[i];
      if (a.hasAttribute("data-hub-external") || a.hasAttribute("data-markets")) continue;
      var href = a.getAttribute("href") || "";
      if (isAi24xUrl(href) || a.hasAttribute("data-open") || a.hasAttribute("data-www")) {
        a.removeAttribute("target");
        if (!a.getAttribute("rel")) a.removeAttribute("rel");
      }
    }
  }

  /** Markets 自有顶栏，不再挂全站产品条（避免与主菜单重复） */
  function shouldShowProductBar(activePage) {
    if (activePage === "console" || activePage === "dashboard") return false;
    var sk = siteKind();
    if (sk === "gateway" || sk === "markets") return false;
    return false;
  }

  function marketsHomeUrl() {
    return marketsUrl().replace(/\/$/, "") + "/";
  }

  /** Hub 上打开独立应用（行情官等）：新窗口，当前页留在 Hub */
  function openHubExternal(url) {
    try {
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      try {
        location.href = url;
      } catch (e2) {}
    }
  }

  function productBarHtml(activeProduct) {
    var home = wwwBase().replace(/\/$/, "") + "/";
    var gw = gatewayWorkspaceUrl();
    var mk = marketsHomeUrl();
    var ac = hubUrl();
    function ps(href, label, on) {
      return (
        '<a href="' +
        href +
        '" class="' +
        (on ? "is-on" : "") +
        '">' +
        label +
        "</a>"
      );
    }
    var ap = activeProduct;
    if (ap === "www") ap = "home";
    return (
      '<div class="ai24x-product-bar" role="navigation" aria-label="AI24X products">' +
      '<div class="ai24x-product-bar-inner">' +
      '<a class="ai24x-hub-brand' +
      (ap === "home" ? " is-on" : "") +
      '" href="' +
      home +
      '" data-www title="AI24X Home">' +
      '<span class="ai24x-hub-mark">AI</span><span class="ai24x-hub-name">AI24X</span></a>' +
      '<span class="product-switch" role="group" aria-label="Products">' +
      ps(gw, "AI Gateway", ap === "gateway") +
      ps(mk, "AI Markets", ap === "markets") +
      ps(ac, "Account", ap === "account") +
      "</span>" +
      '<span class="ai24x-eco-hint">Hub · one login</span>' +
      "</div></div>"
    );
  }

  function mountProductBar(host, activeProduct) {
    if (!host) return;
    host.innerHTML = productBarHtml(activeProduct);
  }

  function bindSignOut(selector) {
    var el = document.querySelector(selector || "#nav-signout");
    if (!el) return;
    el.addEventListener("click", function (ev) {
      ev.preventDefault();
      clearAuthSession();
      var login = wwwBase() + "/login.html";
      try {
        if (siteKind() === "www") login = "login.html";
        else if (siteKind() === "gateway") login = "login.html";
      } catch (e) {}
      location.href = login;
    });
  }

  ingestOauthFragment();
  syncAuthFromCookie();
  bootstrapAuthFromSession();

  function resolveActiveProduct(activePage) {
    if (activePage === "console" || activePage === "account") return "account";
    var sk = siteKind();
    if (sk === "gateway") return "gateway";
    if (sk === "markets") return "markets";
    return "home";
  }

  global.AI24X_CHROME = {
    wwwBase: wwwBase,
    apiBase: apiBase,
    openUrl: openUrl,
    marketsUrl: marketsUrl,
    marketsHomeUrl: marketsHomeUrl,
    a1Url: a1Url,
    hubUrl: hubUrl,
    gatewayWorkspaceUrl: gatewayWorkspaceUrl,
    openHubExternal: openHubExternal,
    siteKind: siteKind,
    authToken: authToken,
    syncAuthFromCookie: syncAuthFromCookie,
    clearAuthSession: clearAuthSession,
    stripInAppNewTab: stripInAppNewTab,
    shouldShowProductBar: shouldShowProductBar,
    productBarHtml: productBarHtml,
    mountProductBar: mountProductBar,
    bindSignOut: bindSignOut,
    resolveActiveProduct: resolveActiveProduct,
  };
  global.AI24X_OPEN_URL = openUrl();
  global.AI24X_MARKETS_URL = marketsUrl();
})(typeof window !== "undefined" ? window : this);
