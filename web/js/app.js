/**
 * 入口：主题 CSS → Shell → i18n
 */
document.addEventListener("DOMContentLoaded", function () {
  var page = document.body.getAttribute("data-page") || "index";
  var th = localStorage.getItem("ai24x_theme") || "blue";
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

  if (window.AI24X_SHELL) AI24X_SHELL.mount(page);
  if (window.AI24X_I18N) AI24X_I18N.apply(document);
});
