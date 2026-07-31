/**
 * 统一页眉 / 页脚（含子目录 models/ guides/ 的相对前缀）
 */
(function (global) {
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
      return (
        '<a href="' +
        pre +
        href +
        '" data-i18n="' +
        key +
        '" class="' +
        c.trim() +
        '"></a>'
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
      '<select id="theme-select" class="select-mini theme-select" aria-label="Theme">' +
      '<option value="blue" data-i18n="theme.blue"></option>' +
      '<option value="dark" data-i18n="theme.dark"></option>' +
      '<option value="cards" data-i18n="theme.cards"></option>' +
      "</select>" +
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

  function applyTheme(name) {
    var link = document.getElementById("theme-css");
    if (!link) return;
    var map = { blue: "theme-blue", dark: "theme-dark", cards: "theme-cards" };
    var file = map[name] || "theme-blue";
    var base = link.getAttribute("data-base") || "css/themes/";
    link.href = base + file + ".css";
    document.body.classList.remove("theme-blue", "theme-dark", "theme-cards");
    document.body.classList.add("theme-" + name);
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
    var th = localStorage.getItem("ai24x_theme") || "blue";
    applyTheme(th);
    var ts = document.getElementById("theme-select");
    if (ts) ts.value = th;
  }

  global.AI24X_SHELL = { mount: mount, applyTheme: applyTheme, pathPrefix: pathPrefix };
})(typeof window !== "undefined" ? window : this);
