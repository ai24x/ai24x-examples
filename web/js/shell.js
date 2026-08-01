/**
 * 统一页眉 / 页脚（含子目录 models/ guides/ 的相对前缀）
 */
(function (global) {
  /** 国际站：默认蓝白品牌；关掉右上角主题切换（改 true 可恢复） */
  var THEME_PICKER_ENABLED = false;
  var DEFAULT_THEME = "blue";

  function esc(s) {
    return String(s || "").replace(/"/g, "&quot;");
  }

  function pathPrefix() {
    try {
      var p = String(location.pathname || "");
      if (p.indexOf("/models/") >= 0 || p.indexOf("/guides/") >= 0) return "../";
    } catch (e) {}
    return "";
  }

  function headerHtml(activePage) {
    var L = global.AI24X_I18N;
    var langs = L.LANGS;
    var pre = pathPrefix();
    var langOpts = langs
      .map(function (x) {
        return (
          '<option value="' +
          esc(x.code) +
          '">' +
          esc(x.label) +
          "</option>"
        );
      })
      .join("");

    function nav(href, key, id) {
      var c = activePage === id ? " is-active" : "";
      var label = "";
      try {
        if (L && typeof L.t === "function") label = L.t(key) || "";
      } catch (e) {}
      return (
        '<a href="' +
        pre +
        href +
        '" data-i18n="' +
        key +
        '" class="' +
        c.trim() +
        '">' +
        esc(label) +
        "</a>"
      );
    }

    return (
      '<div class="container header-inner">' +
      '<a class="brand" href="' +
      pre +
      'index.html">' +
      '<span class="brand-mark">AI</span>' +
      "<span>AI24X</span>" +
      "</a>" +
      '<button type="button" class="menu-toggle" id="menu-toggle" aria-label="Menu" aria-expanded="false"><span></span></button>' +
      '<nav class="nav-main" id="nav-main" aria-label="Main">' +
      nav("index.html", "nav.home", "index") +
      nav("product.html", "nav.product", "product") +
      nav("pricing.html", "nav.pricing", "pricing") +
      nav("models/index.html", "nav.models", "models") +
      nav("docs.html", "nav.docs", "docs") +
      nav("help.html", "nav.help", "help") +
      nav("console.html", "nav.console", "console") +
      nav("login.html", "nav.login", "login") +
      nav("register.html", "nav.register", "register") +
      "</nav>" +
      '<div class="header-actions">' +
      '<select id="lang-select" class="select-mini" aria-label="Language">' +
      langOpts +
      "</select>" +
      /* 国际站默认锁定蓝白；主题切换易 FOUC，先不露出选择器（CSS/逻辑仍保留） */
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
      pre +
      'product.html" data-i18n="footer.link.product"></a>' +
      '<a href="' +
      pre +
      'pricing.html" data-i18n="footer.link.pricing"></a>' +
      '<a href="' +
      pre +
      'models/index.html" data-i18n="footer.link.models"></a>' +
      '<a href="' +
      pre +
      'partner.html" data-i18n="footer.link.partner"></a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title" data-i18n="footer.col.dev"></div>' +
      '<a href="' +
      pre +
      'docs.html" data-i18n="footer.link.docs"></a>' +
      '<a href="' +
      pre +
      'guides/index.html" data-i18n="footer.link.guides"></a>' +
      '<a href="' +
      pre +
      'help.html" data-i18n="footer.link.help"></a>' +
      '<a href="' +
      pre +
      'refer.html" data-i18n="footer.link.refer"></a>' +
      '<a href="' +
      pre +
      'console.html" data-i18n="footer.link.console"></a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title" data-i18n="footer.col.corp"></div>' +
      '<a href="' +
      pre +
      'about.html" data-i18n="footer.link.about"></a>' +
      "</div>" +
      "</div>" +
      '<div class="footer-bottom">© 2026 AI24X · <span data-i18n="footer.copy"></span> · <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">浙ICP备10040624号-7</a></div>' +
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

    var lang = document.getElementById("lang-select");
    if (lang) {
      lang.addEventListener("change", function () {
        try {
          if (lang.value !== "zh") {
            document.documentElement.classList.add("i18n-pending");
          }
        } catch (e0) {}
        global.AI24X_I18N.setLang(lang.value);
        global.AI24X_I18N.apply(document);
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
    if (p.indexOf("pricing") >= 0) return "pricing";
    if (p.indexOf("register") >= 0) return "register";
    if (p.indexOf("refer") >= 0) return "refer";
    return "";
  }

  function exploreSubnavHtml(activeKey) {
    var pre = pathPrefix();
    var root = pre; /* models/guides 下为 ../ ，根页为空 */
    var items = [
      { key: "register", href: root + "register.html", i18n: "page.index.hero.cta.register", fallback: "免费注册" },
      { key: "pricing", href: root + "pricing.html", i18n: "nav.pricing", fallback: "价格" },
      { key: "guides", href: root + "guides/index.html", i18n: "btn.guides", fallback: "接入案例" },
      { key: "vip", href: root + "models/vip-picks.html", i18n: "page.models.vip.cta", fallback: "VIP 点名清单" },
      { key: "refer", href: root + "refer.html", i18n: "page.models.cta.invite", fallback: "邀请好友" },
    ];
    /* 非名模首页时加「名模」便于返回；名模首页保持原来 5 键顺序与主按钮 */
    if (activeKey !== "models") {
      items.unshift({
        key: "models",
        href: root + "models/index.html",
        i18n: "page.models.title",
        fallback: "名模",
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
      try {
        localStorage.setItem("ai24x_theme", DEFAULT_THEME);
      } catch (e) {}
    }
    applyTheme(th);
    if (THEME_PICKER_ENABLED) ensureThemePreloads();
    var ts = document.getElementById("theme-select");
    if (ts) ts.value = th;
  }

  global.AI24X_SHELL = { mount: mount, applyTheme: applyTheme, pathPrefix: pathPrefix };
})(typeof window !== "undefined" ? window : this);
