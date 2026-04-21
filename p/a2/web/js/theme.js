/**
 * p/a theme bridge:
 * - follows main site setting `localStorage.ai24x_theme`
 * - supports: blue / dark / cards
 */
document.addEventListener("DOMContentLoaded", function () {
  var th = localStorage.getItem("ai24x_theme") || "blue";
  var map = { blue: "theme-blue", dark: "theme-dark", cards: "theme-cards" };
  var link = document.getElementById("theme-css");
  if (link) {
    var base = link.getAttribute("data-base") || "css/themes/";
    link.href = base + (map[th] || "theme-blue") + ".css";
  }
  document.body.classList.remove("theme-blue", "theme-dark", "theme-cards");
  document.body.classList.add("theme-" + th);
});

