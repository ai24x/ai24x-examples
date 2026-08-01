/**
 * 尽早读语言偏好：非中文时给 <html> 加 i18n-pending，并内联隐藏 body，
 * 避免等 base.css / 底部脚本前先闪中文再切英文。
 * 首访无偏好时固定英文（与 i18n.js 一致，不跟浏览器自动切中文）。
 * locales/i18n.apply 会摘掉该类。
 */
(function () {
  var KEY = "ai24x_lang";
  try {
    var raw = String(localStorage.getItem(KEY) || "")
      .trim()
      .toLowerCase()
      .replace(/_/g, "-");
    var lang = raw.split("-")[0] || "";
    if (!lang) {
      lang = "en";
      localStorage.setItem(KEY, lang);
    }
    if (lang !== "zh") {
      document.documentElement.classList.add("i18n-pending");
      if (!document.getElementById("ai24x-i18n-pending")) {
        var st = document.createElement("style");
        st.id = "ai24x-i18n-pending";
        st.textContent =
          "html.i18n-pending body{visibility:hidden!important}";
        (document.head || document.documentElement).appendChild(st);
      }
      // 脚本失败时兜底露出，避免整页一直隐藏
      setTimeout(function () {
        document.documentElement.classList.remove("i18n-pending");
      }, 2800);
    }
  } catch (e) {}
})();
