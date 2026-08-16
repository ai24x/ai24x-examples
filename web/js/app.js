/**
 * 入口：主题 CSS → Shell → i18n
 * 脚本在 body 末尾时立刻 mount+apply，不拖到 DOMContentLoaded（缩短中文可见窗口）。
 */
(function () {
  function bootAi24xPage() {
    if (bootAi24xPage._done) return;
    bootAi24xPage._done = true;

    var page = document.body.getAttribute("data-page") || "index";
    /* 默认跟随 HTML 声明的主题：主页已声明 theme-dark（深色默认），其余页面仍 theme-blue；
       不再强制写死 blue，避免深色首页被运行时切回蓝白。 */
    var link0 = document.getElementById("theme-css");
    var href0 = link0 ? (link0.getAttribute("href") || "") : "";
    var th = href0.indexOf("theme-dark") >= 0 ? "dark"
      : (href0.indexOf("theme-cards") >= 0 ? "cards" : "blue");
    try {
      localStorage.setItem("ai24x_theme", th);
    } catch (e) {}
    var map = { blue: "theme-blue", dark: "theme-dark", cards: "theme-cards" };
    var link = document.getElementById("theme-css");
    if (link) {
      var base = link.getAttribute("data-base") || "css/themes/";
      var cur = link.getAttribute("href") || "";
      var qs = "";
      var m = cur.match(/\?v=[^&#]+/);
      if (m) qs = m[0];
      link.href = base + (map[th] || "theme-blue") + ".css" + qs;
    }
    document.body.classList.remove("theme-blue", "theme-dark", "theme-cards");
    document.body.classList.add("theme-" + th);

    try {
      if (window.AI24X_SHELL) AI24X_SHELL.mount(page);
    } catch (eMount) {}
    if (window.AI24X_I18N) AI24X_I18N.apply(document);
  }

  if (document.body) bootAi24xPage();
  else document.addEventListener("DOMContentLoaded", bootAi24xPage);
})();
