/**
 * AI 行情官（p/a1/web）统一页眉 / 页脚（轻量版，无 i18n 依赖）
 */
(function (global) {
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /** Local static :18001 → API :18011; production same-origin (Nginx /api). */
  function getApiBase() {
    try {
      if (String(location.protocol || "") === "file:") return "http://127.0.0.1:18011";
      var host = String(location.hostname || "");
      var port = String(location.port || "");
      if ((host === "127.0.0.1" || host === "localhost") && port === "18001") return "http://127.0.0.1:18011";
      if ((host === "127.0.0.1" || host === "localhost") && port === "18003") return "http://127.0.0.1:18011";
    } catch (e0) {}
    return "";
  }

  function _getInviteCode() {
    // Keep invite code across pages: prefer URL ?i=CODE, fallback to localStorage.
    try {
      var u = new URL(String(location.href));
      var code = String(u.searchParams.get("i") || "").trim().toUpperCase();
      if (code) {
        try { localStorage.setItem("ai24x_invite_code", code); } catch (e0) {}
        return code;
      }
    } catch (e1) {}
    try {
      var v = String(localStorage.getItem("ai24x_invite_code") || "").trim().toUpperCase();
      return v || "";
    } catch (e2) {
      return "";
    }
  }

  function withInvite(href) {
    try {
      var code = _getInviteCode();
      if (!code) return href;
      // external link: do not append
      if (/^https?:\/\//i.test(String(href || ""))) return href;
      var base = String(location.origin || "");
      var u = new URL(String(href || ""), base + "/");
      if (!u.searchParams.get("i")) u.searchParams.set("i", code);
      var p = u.pathname.replace(/^\//, "");
      return p + (u.search ? u.search : "") + (u.hash ? u.hash : "");
    } catch (e) {
      return href;
    }
  }

  function footerHtml() {
    return (
      '<div class="container">' +
      '<div class="footer-grid">' +
      '<div class="footer-col">' +
      '<div class="footer-title">AI24X · AI 行情官｜灯塔版（V1.03）</div>' +
      '<div class="mt-2">行情与指标，一目了然</div>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title">产品</div>' +
      '<a href="demo.html">行情与信号</a>' +
      '<a href="help.html">使用帮助</a>' +
      '<a href="account.html">用户中心</a>' +
      '<a href="feedback.html">意见反馈</a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title">服务</div>' +
      '<a href="account.html#vip">开通 VIP</a>' +
      '<a href="account.html#invite">邀请奖励</a>' +
      '<a href="partner.html">伙伴合作</a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title">合规</div>' +
      '<a href="terms.html">用户协议</a>' +
      '<a href="privacy.html">隐私政策</a>' +
      '<a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">浙ICP备10040624号-7</a>' +
      "</div>" +
      "</div>" +
      '<div class="footer-bottom">© 2026 AI24X</div>' +
      "</div>"
    );
  }

  function bindChrome() {
    var toggle = document.getElementById("menu-toggle");
    var nav = document.getElementById("nav-main");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    // Theme: lock to calm (深蓝); theme select removed to avoid mobile header overflow
    try {
      var k = "ai24x_a_theme";
      try { localStorage.setItem(k, "calm"); } catch (e0) {}
      applyTheme("calm");
    } catch (e) {}

    // Service Worker update (avoid "Ctrl+F5 looks different" after deployments)
    try {
      if (!global.__AI24X_A_SW_INSTALLED && "serviceWorker" in navigator && String(location.protocol || "") !== "file:") {
        global.__AI24X_A_SW_INSTALLED = true;
        // Cache-bust SW URL so deployments don't require Ctrl+F5.
        // Use absolute paths so pages still work under subpaths like /i/{code}.
        navigator.serviceWorker.register("/sw.js?v=48", { scope: "/", updateViaCache: "none" }).then(function (reg) {
          try {
            reg.update && reg.update();
            if (reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" });
          } catch (e0) {}
        }).catch(function () {});
        navigator.serviceWorker.addEventListener("controllerchange", function () {
          try { location.reload(); } catch (e1) {}
        });
      }
    } catch (e) {}
  }

  function applyTheme(t) {
    try {
      t = String(t || "").trim() || "calm";
      document.documentElement.setAttribute("data-theme", t);
    } catch (e) {}
  }

  function _el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null) return;
      if (k === "class") node.className = String(v);
      else if (k === "text") node.textContent = String(v);
      else if (k === "html") node.innerHTML = String(v);
      else node.setAttribute(k, String(v));
    });
    (children || []).forEach(function (c) {
      if (c == null) return;
      if (typeof c === "string") node.appendChild(document.createTextNode(c));
      else node.appendChild(c);
    });
    return node;
  }

  function headerDom(active) {
    function nav(href, label, id) {
      href = withInvite(href);
      return _el(
        "a",
        { href: href, class: active === id ? "is-active" : "" },
        [String(label)]
      );
    }

    var wrap = _el("div", { class: "container header-inner" }, []);
    var brand = _el("a", { class: "brand", href: "index.html", "aria-label": "AI24X" }, [
      _el("span", { class: "brand-mark", text: "AI" }),
      _el("span", { class: "brand-text brand-text-full", text: "AI 行情官｜灯塔版" }),
      _el("span", { class: "brand-text brand-text-short", text: "AI行情官" }),
    ]);
    var toggle = _el(
      "button",
      { type: "button", class: "menu-toggle", id: "menu-toggle", "aria-label": "Menu", "aria-expanded": "false" },
      [_el("span", {}, [])]
    );
    var navMain = _el("nav", { class: "nav-main", id: "nav-main", "aria-label": "Main" }, [
      nav("index.html", "首页", "index"),
      nav("demo.html", "行情", "demo"),
      nav("gd.html", "掘金", "bjscreener"),
      nav("account.html", "我的", "account"),
      nav("help.html", "帮助", "help"),
      nav("feedback.html", "反馈", "feedback"),
    ]);
    var actions = _el("div", { class: "header-actions" }, []);
    var authWrap = _el("span", { id: "auth-actions", class: "auth-actions" }, []);
    authWrap.appendChild(_el("a", { class: "btn btn-ghost btn-auth-login", id: "btn-auth", href: "index.html?mode=login" }, ["登录"]));
    authWrap.appendChild(_el("a", { class: "btn btn-primary btn-auth-register", id: "btn-vip", href: "index.html?mode=register" }, ["免费注册"]));
    authWrap.appendChild(_el("button", { type: "button", class: "btn btn-ghost btn-header-logout", id: "btn-header-logout", style: "display:none;" }, ["退出"]));
    actions.appendChild(authWrap);

    wrap.appendChild(brand);
    wrap.appendChild(toggle);
    wrap.appendChild(navMain);
    wrap.appendChild(actions);
    return wrap;
  }

  function footerDom() {
    var wrap = _el("div", { class: "container" }, []);
    var grid = _el("div", { class: "footer-grid" }, []);

    var c1 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "AI24X · AI 行情官｜灯塔版（V1.03）" }),
      _el("div", { class: "mt-2", text: "行情与指标，一目了然" }),
    ]);
    var c2 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "产品" }),
      _el("a", { href: "demo.html", text: "行情与信号" }),
      _el("a", { href: "help.html", text: "使用帮助" }),
      _el("a", { href: "account.html", text: "用户中心" }),
      _el("a", { href: "feedback.html", text: "意见反馈" }),
    ]);
    var c3 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "服务" }),
      _el("a", { href: "account.html#vip", text: "开通 VIP" }),
      _el("a", { href: "account.html#invite", text: "邀请奖励" }),
      _el("a", { href: "partner.html", text: "伙伴合作" }),
    ]);
    var c4 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "合规" }),
      _el("a", { href: "terms.html", text: "用户协议" }),
      _el("a", { href: "privacy.html", text: "隐私政策" }),
      _el("a", { href: "https://beian.miit.gov.cn/", target: "_blank", rel: "noopener", text: "浙ICP备10040624号-7" }),
    ]);

    grid.appendChild(c1);
    grid.appendChild(c2);
    grid.appendChild(c3);
    grid.appendChild(c4);
    wrap.appendChild(grid);
    wrap.appendChild(_el("div", { class: "footer-bottom", text: "© 2026 AI24X" }));
    return wrap;
  }

  function mount(activePage) {
    var h = document.getElementById("site-header");
    var f = document.getElementById("site-footer");
    if (h) {
      try { h.textContent = ""; } catch (e0) {}
      h.appendChild(headerDom(activePage));
    }
    if (f) {
      try { f.textContent = ""; } catch (e1) {}
      f.appendChild(footerDom());
    }
    bindChrome();
    try{
      var TOKEN_KEY = "ai24x_a_token";
      var tok = "";
      try{ tok = localStorage.getItem(TOKEN_KEY) || ""; }catch(e0){ tok = ""; }
      var authWrap = document.getElementById("auth-actions");
      var btnAuth = document.getElementById("btn-auth");
      var btnVip = document.getElementById("btn-vip");
      var btnLogout = document.getElementById("btn-header-logout");
      function inviteCode() {
        try {
          var sp = new URLSearchParams(String(location.search || "").replace(/^\?/, ""));
          var v = sp.get("i") || sp.get("invite") || sp.get("inv") || sp.get("ref") || "";
          v = String(v || "").trim().toUpperCase();
          if (v) return v;
        } catch (e0) {}
        try {
          return String(localStorage.getItem("ai24x_invite_code") || "").trim().toUpperCase();
        } catch (e1) {
          return "";
        }
      }
      function authHref(mode) {
        var m = mode === "login" ? "login" : "register";
        var h = "index.html?mode=" + m;
        var ic = inviteCode();
        if (ic) h += "&i=" + encodeURIComponent(ic);
        return h;
      }
      function showAuthWrap(){
        if(!authWrap) return;
        try{ authWrap.style.display = "inline-flex"; }catch(e0){}
      }
      function setLoggedOutUi(){
        try{
          if(btnAuth) btnAuth.style.display = "";
          if(btnLogout) btnLogout.style.display = "none";
          // 游客：登录为次、免费注册为主（仅顶栏出现）
          // 极窄屏用「注册」，减轻华为浏览器顶栏撑宽导致整页右侧裁切
          var narrow = false;
          try {
            var w = Math.min(
              window.innerWidth || 9999,
              (window.visualViewport && window.visualViewport.width) || 9999,
              (window.screen && screen.width) || 9999
            );
            narrow = w > 0 && w <= 380;
          } catch (eN) {}
          if(btnAuth) {
            btnAuth.textContent = "登录";
            btnAuth.className = "btn btn-ghost btn-auth-login";
            btnAuth.setAttribute("href", authHref("login"));
          }
          if(btnVip) {
            btnVip.textContent = narrow ? "注册" : "免费注册";
            btnVip.className = "btn btn-primary btn-auth-register";
            btnVip.setAttribute("href", authHref("register"));
            btnVip.style.display = "";
          }
        }catch(e0){}
      }
      function setLoggedInUi(d){
        try{
          // 顶栏导航已有「我的」，右上角隐藏账号入口（避免双入口），仅保留「开通 VIP」。
          if(btnAuth) btnAuth.style.display = "none";
          if(btnLogout) btnLogout.style.display = "";
          if(btnVip) {
            btnVip.textContent = "开通 VIP";
            btnVip.className = "btn btn-primary";
            btnVip.setAttribute("href", "account.html#vip");
            btnVip.style.display = "";
          }
        }catch(e0){}
      }
      // Avoid "login flash": hide auth actions until we know state.
      if(!tok){
        setLoggedOutUi();
        showAuthWrap();
      }else{
        // Show stable entry immediately when token exists; refine state after /api/me.
        try{ setLoggedInUi(null); }catch(e0){}
        showAuthWrap();
        // Best-effort: if /api/me fails, keep partner hidden.
        try{
          var apiBase = getApiBase();
          fetch((apiBase || "") + "/api/me", { cache: "no-store", headers: { "Authorization": "Bearer " + String(tok) } })
            .then(function(r){ return r && r.ok ? r.json() : null; })
            .then(function(d){
              try{ setLoggedInUi(d); }catch(eU){}
              showAuthWrap();
            })
            .catch(function(){
              // keep "我的" shown; if token invalid, account page will guide relogin
            });
        }catch(e3){
          // keep "我的" shown
        }
      }
    }catch(eG){}
      try{
        var btnLogoutH = document.getElementById("btn-header-logout");
        if(btnLogoutH) btnLogoutH.addEventListener("click", function(){
          try{ localStorage.removeItem("ai24x_a_token"); }catch(e0){}
          try{ localStorage.removeItem("ai24x_a_watchlist"); }catch(e1){}
          try{ location.href = "index.html"; }catch(e2){}
        });
      }catch(eH){}

  }

  global.AI24X_A_SHELL = { mount: mount, applyTheme: applyTheme };
})(typeof window !== "undefined" ? window : this);

