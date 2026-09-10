/**
 * 统一页眉 / 页脚（含子目录 models/ guides/ 的相对前缀）
 */
(function (global) {
  /** 国际站：默认蓝白品牌；关掉右上角主题切换（改 true 可恢复） */
  var THEME_PICKER_ENABLED = false;
  var DEFAULT_THEME = "blue";

  /**
   * 本机联调开关（localStorage.ai24x_local_products）：
   * - 缺省 / "1"：localhost|127.0.0.1 → 本地端口（open 18080 / markets 18012）
   * - "0"：本机仍链正式站（方便对照生产）
   * 生产域名永不改写。勿改成 ../p/open 相对路径——多源站/多端口无法共用一条相对链。
   */
  function preferLocalProducts() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      if (h !== "127.0.0.1" && h !== "localhost") return false;
      var flag = "";
      try {
        flag = String(localStorage.getItem("ai24x_local_products") || "").trim();
      } catch (e) {}
      return flag !== "0";
    } catch (e) {
      return false;
    }
  }

  /** AI24X Markets：生产域名；本机默认 18012（可用 ai24x_local_products=0 切回正式站） */
  function marketsUrl() {
    try {
      var h = String(location.hostname || "");
      if (h === "127.0.0.1" || h === "localhost") {
        var port = String(location.port || "");
        if (port === "18012") return "http://127.0.0.1:18012/";
        if (preferLocalProducts()) return "http://127.0.0.1:18012/";
      }
    } catch (e) {}
    return "https://markets.ai24x.com/";
  }

  /** open.ai24x.com AI Gateway；本机默认 18080（=0 切正式站） */
  function openUrl() {
    try {
      var h = String(location.hostname || "");
      if (h === "127.0.0.1" || h === "localhost") {
        var port = String(location.port || "");
        if (port === "18080") return "http://127.0.0.1:18080/";
        if (preferLocalProducts()) return "http://127.0.0.1:18080/";
      }
    } catch (e) {}
    return "https://open.ai24x.com/";
  }
  global.AI24X_MARKETS_URL = marketsUrl();
  global.AI24X_OPEN_URL = openUrl();

  function wwwBase() {
    if (global.AI24X_CHROME && global.AI24X_CHROME.wwwBase) return global.AI24X_CHROME.wwwBase();
    return "https://www.ai24x.com";
  }

  function resolveActiveProduct(activePage) {
    if (global.AI24X_CHROME && global.AI24X_CHROME.resolveActiveProduct) {
      return global.AI24X_CHROME.resolveActiveProduct(activePage);
    }
    if (activePage === "console" || activePage === "account") return "account";
    return null;
  }

  function isAi24xHref(href) {
    return /^(https?:\/\/)?([a-z0-9-]+\.)?ai24x\.com(\/|$)/i.test(String(href || ""));
  }

  function esc(s) {
    return String(s || "").replace(/"/g, "&quot;");
  }

  function pathPrefix() {
    try {
      var p = String(location.pathname || "");
      if (
        p.indexOf("/models/") >= 0 ||
        p.indexOf("/guides/") >= 0 ||
        p.indexOf("/blog/") >= 0
      )
        return "../";
    } catch (e) {}
    return "";
  }

  function headerHtml(activePage) {
    var L = global.AI24X_I18N;
    var langs = L && Array.isArray(L.LANGS) && L.LANGS.length ? L.LANGS : [{ code: "en", label: "English" }];
    var pre = pathPrefix();
    var isConsole = false;
    try {
      isConsole = document.body && document.body.getAttribute("data-page") === "console";
    } catch (e0) {}
    var curLang = "en";
    try {
      if (L && typeof L.getLang === "function") curLang = L.getLang() || "en";
    } catch (e1) {}
    var langOpts = langs
      .map(function (x) {
        return (
          '<option value="' +
          esc(x.code) +
          '"' +
          (x.code === curLang ? " selected" : "") +
          ">" +
          esc(x.label) +
          "</option>"
        );
      })
      .join("");

    /** 轻量产品切换器：仅在控制台页显示，避免全站视觉变化（腾讯云式全局顶栏的轻量版） */
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
    var psHtml = "";
    if (global.AI24X_CHROME && typeof global.AI24X_CHROME.productBarHtml === "function") {
      var showBar = true;
      if (typeof global.AI24X_CHROME.shouldShowProductBar === "function") {
        showBar = global.AI24X_CHROME.shouldShowProductBar(activePage);
      }
      if (showBar) {
        psHtml = global.AI24X_CHROME.productBarHtml(resolveActiveProduct(activePage));
      }
    } else {
      var wideEnough = true;
      try {
        wideEnough = (window.innerWidth || 1280) >= 860;
      } catch (e2) {}
      if (isConsole && wideEnough) {
        var gwHref = openUrl();
        var mkHref = marketsUrl();
        var acHref = pre + "console.html";
        psHtml =
          '<div class="product-switch-bar">' +
          '<div class="container">' +
          '<span class="product-switch-label">Products</span>' +
          '<span class="product-switch">' +
          ps(gwHref, "AI Gateway", activePage === "gateway") +
          ps(mkHref, "AI Markets", activePage === "markets") +
          ps(acHref, "Account", activePage === "account" || activePage === "console") +
          "</span>" +
          "</div>" +
          "</div>";
      }
    }

    function nav(href, key, id) {
      var c = activePage === id ? " is-active" : "";
      var ext = /^https?:\/\//i.test(href);
      var full = ext ? href : pre + href;
      var newTab = ext && !isAi24xHref(full);
      var label = tr(key);
      return (
        '<a href="' +
        full +
        '"' +
        (newTab ? ' target="_blank" rel="noopener"' : "") +
        ' data-i18n="' +
        key +
        '" class="' +
        c.trim() +
        '">' +
        esc(label) +
        "</a>"
      );
    }

    /** 登录态显示 Account + Sign out，未登录显示 Log in / Sign up */
    function authToken() {
      if (global.AI24X_CHROME && global.AI24X_CHROME.authToken) return global.AI24X_CHROME.authToken();
      try {
        return localStorage.getItem("ai24x_auth_token") || "";
      } catch (e) {
        return "";
      }
    }

    function loginNav() {
      if (authToken()) return "";
      return (
        nav("login.html", "nav.login", "login") +
        nav("register.html", "nav.register", "register")
      );
    }

    function tr(key) {
      try {
        if (L && typeof L.t === "function") return L.t(key) || "";
      } catch (e) {}
      return "";
    }

    function navDrop(key, items) {
      var c = items.some(function (it) { return activePage === it.id; })
        ? " is-active"
        : "";
      var links = items
        .map(function (it) {
          var cc = activePage === it.id ? " is-active" : "";
          var full = /^https?:\/\//i.test(it.href) ? it.href : pre + it.href;
          return (
            '<a href="' +
            full +
            '" data-i18n="' +
            it.key +
            '" class="' +
            cc.trim() +
            '">' +
            esc(tr(it.key)) +
            "</a>"
          );
        })
        .join("");
      return (
        '<span class="nav-drop' +
        c.trim() +
        '">' +
        '<button type="button" class="nav-drop-btn" aria-haspopup="true" aria-expanded="false" data-i18n="' +
        key +
        '">' +
        esc(tr(key)) +
        ' <span class="nav-caret">▾</span></button>' +
        '<span class="nav-drop-menu" role="menu">' +
        links +
        "</span>" +
        "</span>"
      );
    }

    // 右上排布：次要 CTA → 主 CTA → 语言（最右）；窄屏用 CSS 藏次要 CTA，主 CTA+语言不掉
    return (
      psHtml +
      '<div class="container header-inner">' +
      '<a class="brand" href="' +
      pre +
      'index.html">' +
      '<span class="brand-mark">AI</span>' +
      "<span>AI24X</span>" +
      "</a>" +
      '<button type="button" class="menu-toggle" id="menu-toggle" aria-label="Menu" aria-expanded="false"><span></span></button>' +
      '<nav class="nav-main" id="nav-main" aria-label="Main">' +
      nav("index.html", "nav.home", "home") +
      nav("pricing.html", "nav.pricing", "pricing") +
      nav("product.html", "nav.product", "product") +
      // Blog 仅放页脚：顶栏露出易像「新站内容池」，转化叙事优先
      nav("help.html", "nav.help", "help") +
      nav("about.html", "nav.about", "about") +
      loginNav() +
      "</nav>" +
      '<div class="header-actions">' +
      '<a class="header-gateway" href="' +
      pre +
      'console.html" data-i18n="nav.ctaGateway">' +
      esc(tr("nav.ctaGateway")) +
      "</a>" +
      '<a class="header-upgrade" href="' +
      pre +
      'register.html" data-i18n="nav.ctaStart">' +
      esc(tr("nav.ctaStart")) +
      "</a>" +
      '<select id="lang-select" class="select-mini lang-select" aria-label="Language">' +
      langOpts +
      "</select>" +
      (THEME_PICKER_ENABLED
        ? '<select id="theme-select" class="select-mini theme-select" aria-label="Theme">' +
          '<option value="blue" data-i18n="theme.blue"></option>' +
          '<option value="dark" data-i18n="theme.dark"></option>' +
          '<option value="cards" data-i18n="theme.cards"></option>' +
          "</select>"
        : "") +
      "</div>" +
      "</div>"
    );
  }

  function fixNavActive(activePage) {
    var nav = document.getElementById("nav-main");
    if (!nav) return;
    var pre = pathPrefix();
    var map = {
      index: "index.html",
      product: "product.html",
      pricing: "pricing.html",
      api: "api.html",
      models: "models/index.html",
      guides: "guides/index.html",
      help: "help.html",
      refer: "refer.html",
      partner: "partner.html",
      docs: "docs.html",
      about: "about.html",
      console: "console.html",
      login: "login.html",
      register: "register.html",
    };
    var file = map[activePage] ? pre + map[activePage] : "";
    nav.querySelectorAll("a").forEach(function (a) {
      var href = a.getAttribute("href") || "";
      a.classList.toggle("is-active", !!file && href === file);
    });
  }

  function footerHtml() {
    var pre = pathPrefix();
    return (
      '<div class="container">' +
      '<div class="footer-grid">' +
      '<div class="footer-col">' +
      '<div class="footer-title">AI24X</div>' +
      '<div class="mt-2" data-i18n="footer.tagline2"></div>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title" data-i18n="footer.col.product"></div>' +
      '<a href="' +
      openUrl() +
      '" data-i18n="footer.link.gateway"></a>' +
      '<a href="' +
      marketsUrl() +
      '" data-i18n="footer.link.markets"></a>' +
      '<a href="' +
      pre +
      'pricing.html" data-i18n="footer.link.pricing"></a>' +
      '<a href="' +
      pre +
      'product.html" data-i18n="footer.link.product"></a>' +
      '<a href="' +
      pre +
      'partner.html" data-i18n="footer.link.partner"></a>' +
      '<a href="' +
      pre +
      'blog/index.html" data-i18n="footer.link.blog"></a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title" data-i18n="footer.col.dev"></div>' +
      '<a href="' +
      pre +
      'help.html" data-i18n="footer.link.help"></a>' +
      '<a href="' +
      pre +
      'status.html" data-i18n="footer.link.status"></a>' +
      '<a href="' +
      openUrl() +
      '" data-i18n="footer.link.developer"></a>' +
      '<a href="' +
      pre +
      'tools.html" data-i18n="footer.link.tools"></a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title" data-i18n="footer.col.corp"></div>' +
      '<a href="' +
      pre +
      'about.html" data-i18n="footer.link.about"></a>' +
      '<a href="' +
      pre +
      'terms.html" data-i18n="footer.link.terms"></a>' +
      '<a href="' +
      pre +
      'privacy.html" data-i18n="footer.link.privacy"></a>' +
      '<a href="mailto:support@ai24x.com">support@ai24x.com</a>' +
      "</div>" +
      "</div>" +
      '<div class="footer-bottom">© 2026 AI24X · <a href="' +
      openUrl() +
      '" target="_blank" rel="noopener" data-i18n="footer.link.developer"></a> · <span data-i18n="footer.copy"></span></div>' +
      '<div class="footer-bottom" style="opacity:.62;font-size:.78rem;padding-top:0;" data-i18n="footer.fleet">Powered by the AI24X autonomous agent fleet</div>' +
      '<div class="footer-bottom" style="opacity:.62;font-size:.78rem;padding-top:0;" data-i18n="footer.disclaimer">Educational Markets content only — not investment advice. Market data may be delayed.</div>' +
      "</div>"
    );
  }

  function bindChrome() {
    try {
      var mkLinks = document.querySelectorAll("a[data-markets]");
      for (var i = 0; i < mkLinks.length; i++) {
        var href = mkLinks[i].getAttribute("href") || "";
        if (/^https?:\/\/markets\.ai24x\.com(?:\/|$)/.test(href)) {
          // 替换域名主机（保留路径/深链，如 app.html#sub、?plan=yearly），本机开发切 18012
          var rest = href.replace(/^https?:\/\/markets\.ai24x\.com/, "").replace(/^\//, "");
          mkLinks[i].setAttribute("href", marketsUrl() + rest);
        }
      }
      var opLinks = document.querySelectorAll("a[data-open]");
      for (var j = 0; j < opLinks.length; j++) {
        var ohref = opLinks[j].getAttribute("href") || "";
        if (/^https?:\/\/open\.ai24x\.com(?:\/|$)/.test(ohref)) {
          var orest = ohref.replace(/^https?:\/\/open\.ai24x\.com/, "").replace(/^\//, "");
          opLinks[j].setAttribute("href", openUrl() + orest);
        }
      }
      var signout = document.getElementById("nav-signout");
      if (signout) {
        if (global.AI24X_CHROME && global.AI24X_CHROME.bindSignOut) {
          global.AI24X_CHROME.bindSignOut("#nav-signout");
        } else {
          signout.addEventListener("click", function (ev) {
            ev.preventDefault();
            try {
              if (global.AI24X_API && typeof global.AI24X_API.logout === "function") {
                global.AI24X_API.logout();
              } else if (global.AI24X_API && typeof global.AI24X_API.clearAuth === "function") {
                global.AI24X_API.clearAuth();
              } else {
                try { localStorage.removeItem("ai24x_auth_token"); } catch (e) {}
                try { localStorage.removeItem("ai24x_auth_user"); } catch (e) {}
                try {
                  document.cookie = "ai24x_auth_token=; path=/; max-age=0; SameSite=Lax";
                  document.cookie = "ai24x_auth_user=; path=/; max-age=0; SameSite=Lax";
                } catch (e2) {}
              }
            } catch (e3) {}
            location.href = "login.html";
          });
        }
      }
      if (global.AI24X_CHROME && global.AI24X_CHROME.stripInAppNewTab) {
        global.AI24X_CHROME.stripInAppNewTab(document);
      }
    } catch (e) {}
    var toggle = document.getElementById("menu-toggle");
    var nav = document.getElementById("nav-main");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    var lang = document.getElementById("lang-select");
    if (lang) {
      try {
        if (global.AI24X_I18N && typeof global.AI24X_I18N.getLang === "function") {
          lang.value = global.AI24X_I18N.getLang();
        }
      } catch (e1) {}
      lang.addEventListener("change", function () {
        var next = lang.value;
        try {
          if (
            global.AI24X_I18N &&
            typeof global.AI24X_I18N.getLang === "function" &&
            next === global.AI24X_I18N.getLang()
          ) {
            return;
          }
        } catch (e2) {}
        global.AI24X_I18N.setLang(next);
        // 切语言必须整页刷新：apply 只重译静态 data-i18n，
        // JS 动态渲染的文案（控制台工单/账单备注等）不会跟着切，刷新才彻底
        try {
          location.reload();
        } catch (e3) {
          global.AI24X_I18N.apply(document);
        }
      });
    }

    var theme = document.getElementById("theme-select");
    if (theme) {
      theme.value =
        localStorage.getItem("ai24x_theme") || theme.value || "blue";
      theme.addEventListener("change", function () {
        localStorage.setItem("ai24x_theme", theme.value);
        applyTheme(theme.value);
      });
    }
  }

  var THEME_FILE = { blue: "theme-blue", dark: "theme-dark", cards: "theme-cards" };

  function themeNameFromHref(href) {
    var s = String(href || "");
    if (s.indexOf("theme-dark") >= 0) return "dark";
    if (s.indexOf("theme-cards") >= 0) return "cards";
    return "blue";
  }

  function themeQs(link) {
    var m = (link && link.getAttribute("href") || "").match(/\?v=[^&#]+/);
    return m ? m[0] : "?v=20260725a";
  }

  /** 预挂另外两套为 disabled stylesheet（仍走缓存），不改 body/html 选择器 */
  function ensureThemePreloads() {
    var primary = document.getElementById("theme-css");
    if (!primary || !primary.parentNode) return;
    var base = primary.getAttribute("data-base") || "css/themes/";
    var qs = themeQs(primary);
    var names = ["blue", "dark", "cards"];
    for (var i = 0; i < names.length; i++) {
      var n = names[i];
      var id = "theme-preload-" + n;
      if (document.getElementById(id)) continue;
      if (themeNameFromHref(primary.getAttribute("href")) === n) continue;
      var el = document.createElement("link");
      el.id = id;
      el.rel = "stylesheet";
      el.href = base + THEME_FILE[n] + ".css" + qs;
      el.setAttribute("data-base", base);
      el.disabled = true;
      primary.parentNode.insertBefore(el, primary.nextSibling);
    }
  }

  function setBodyTheme(name) {
    if (!THEME_FILE[name]) name = "blue";
    if (!document.body) return;
    document.body.classList.remove("theme-blue", "theme-dark", "theme-cards");
    document.body.classList.add("theme-" + name);
  }

  function applyTheme(name) {
    if (!THEME_FILE[name]) name = "blue";
    var primary = document.getElementById("theme-css");
    if (!primary) return;
    ensureThemePreloads();
    var base = primary.getAttribute("data-base") || "css/themes/";
    var qs = themeQs(primary);
    var cur = themeNameFromHref(primary.getAttribute("href"));
    if (cur === name) {
      setBodyTheme(name);
      return;
    }

    var preload = document.getElementById("theme-preload-" + name);

    function activateLoaded(el) {
      // 1) 先启用新表 2) 再改 body class（旧表选择器不匹配即失效）3) 旧表降为 preload
      el.disabled = false;
      setBodyTheme(name);
      var oldName = themeNameFromHref(primary.getAttribute("href"));
      var oldPreId = "theme-preload-" + oldName;
      var dup = document.getElementById(oldPreId);
      if (dup && dup !== primary && dup !== el) dup.remove();
      primary.disabled = true;
      primary.id = oldPreId;
      el.id = "theme-css";
      el.setAttribute("data-base", base);
      el.disabled = false;
    }

    if (preload) {
      // disabled 表在部分浏览器无 .sheet；先启用，缓存命中则同步可切
      preload.disabled = false;
      if (preload.sheet) {
        activateLoaded(preload);
        return;
      }
      var finished = false;
      var finish = function () {
        if (finished) return;
        finished = true;
        activateLoaded(preload);
      };
      preload.addEventListener("load", finish);
      setTimeout(finish, 200);
      return;
    }

    // 兜底：无 preload 时保留旧行为（并保留 ?v=）
    primary.href = base + THEME_FILE[name] + ".css" + qs;
    setBodyTheme(name);
  }

  /** 与名模页 hero 同簇入口：跨页同位置子导航，便于来回切换 */
  function exploreSubnavActive() {
    var p = "";
    try {
      p = String(location.pathname || "").replace(/\\/g, "/").toLowerCase();
    } catch (e) {
      return "";
    }
    if (p.indexOf("vip-picks") >= 0) return "vip";
    if (p.indexOf("/models/") >= 0) return "models";
    if (p.indexOf("/guides/") >= 0) return "guides";
    return "";
  }

  function exploreSubnavHtml(activeKey) {
    var pre = pathPrefix();
    var root = pre; /* models/guides 下为 ../ ，根页为空 */
    var zhUi = false;
    try {
      zhUi = !!(global.AI24X_I18N && global.AI24X_I18N.isZh && global.AI24X_I18N.isZh());
    } catch (eZh) {}
    var items = [
      {
        key: "register",
        href: root + "register.html",
        i18n: "page.index.hero.cta.register",
        fallback: zhUi ? "免费注册" : "Sign up",
      },
      {
        key: "pricing",
        href: root + "pricing.html",
        i18n: "nav.pricing",
        fallback: zhUi ? "价格" : "Pricing",
      },
      {
        key: "guides",
        href: openUrl() + "guides/",
        i18n: "btn.guides",
        fallback: zhUi ? "接入案例" : "Integrations",
      },
      {
        key: "vip",
        href: openUrl() + "models/vip-picks.html",
        i18n: "page.models.vip.cta",
        fallback: zhUi ? "VIP 点名清单" : "VIP model list",
      },
      {
        key: "refer",
        href: root + "refer.html",
        i18n: "page.models.cta.invite",
        fallback: zhUi ? "邀请好友" : "Invite friends",
      },
    ];
    /* 非名模首页时加「名模」便于返回；名模首页保持原来 5 键顺序与主按钮 */
    if (activeKey !== "models") {
      items.unshift({
        key: "models",
        href: openUrl() + "models/",
        i18n: "page.models.title",
        fallback: zhUi ? "名模" : "Models",
      });
    }
    var primaryKey = activeKey === "models" ? "register" : activeKey;
    var L = global.AI24X_I18N;
    var links = items
      .map(function (it) {
        var cls = "btn" + (it.key === primaryKey ? " btn-primary" : "");
        var label = it.fallback;
        try {
          if (L && typeof L.t === "function") {
            var tr = L.t(it.i18n);
            if (tr && tr !== it.i18n) label = tr;
          }
        } catch (e) {}
        return (
          '<a class="' +
          cls +
          '" href="' +
          esc(it.href) +
          '" data-i18n="' +
          esc(it.i18n) +
          '">' +
          esc(label) +
          "</a>"
        );
      })
      .join("");
    /* 放回 hero 内原 hero-cta 位置，样式与原先按钮组一致 */
    return (
      '<div class="hero-cta page-explore-cta" id="page-explore-subnav" role="navigation" aria-label="Explore">' +
      links +
      "</div>"
    );
  }

  function mountExploreSubnav() {
    var active = exploreSubnavActive();
    var old = document.getElementById("page-explore-subnav");
    if (old) old.remove();
    if (!active) return;
    var main = document.querySelector("main.page-main") || document.querySelector("main");
    if (!main) return;
    var heroBox =
      main.querySelector(".hero .container") ||
      main.querySelector(".hero-surface .container") ||
      main.querySelector("section.hero .container");
    var wrap = document.createElement("div");
    wrap.innerHTML = exploreSubnavHtml(active);
    var nav = wrap.firstChild;
    if (!nav) return;
    if (heroBox) {
      var existingCta = heroBox.querySelector(".hero-cta");
      if (existingCta) {
        /* 保留页内专用按钮（如控制台），探索条插在其前 */
        heroBox.insertBefore(nav, existingCta);
      } else {
        heroBox.appendChild(nav);
      }
      return;
    }
    /* 无 hero 的页（如注册）：插在 main 首段容器内顶部 */
    var firstSection = main.querySelector("section .container") || main.querySelector(".container");
    if (firstSection) firstSection.insertBefore(nav, firstSection.firstChild);
    else main.insertBefore(nav, main.firstChild);
  }

  function mount(activePage) {
    var h = document.getElementById("site-header");
    var f = document.getElementById("site-footer");
    if (h) {
      h.innerHTML = headerHtml(activePage);
      fixNavActive(activePage);
    }
    if (f) f.innerHTML = footerHtml();
    bindChrome();
    mountExploreSubnav();
    var th = DEFAULT_THEME;
    if (THEME_PICKER_ENABLED) {
      th = localStorage.getItem("ai24x_theme") || DEFAULT_THEME;
      if (!THEME_FILE[th]) th = DEFAULT_THEME;
    } else {
      // 无主题选择器时跟随 HTML 声明的主题（首页默认 theme-blue 母站气质）
      var linkHref = (document.getElementById("theme-css") || {}).getAttribute ?
        (document.getElementById("theme-css").getAttribute("href") || "") : "";
      if (linkHref.indexOf("theme-dark") >= 0) th = "dark";
      else if (linkHref.indexOf("theme-cards") >= 0) th = "cards";
      try {
        localStorage.setItem("ai24x_theme", th);
      } catch (e) {}
    }
    applyTheme(th);
    if (THEME_PICKER_ENABLED) ensureThemePreloads();
    var ts = document.getElementById("theme-select");
    if (ts) ts.value = th;
  }

  global.AI24X_SHELL = { mount: mount, applyTheme: applyTheme, pathPrefix: pathPrefix };
})(typeof window !== "undefined" ? window : this);
