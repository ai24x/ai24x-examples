/**
 * 国际化 — 语言包为扁平 key：nav.home、page.index.title 等
 *
 * 策略（2026-07-26）：
 * - 中文：zh
 * - 其它语言选项：统一以英文为内容底稿（避免缺译时回落到中文造成中英混杂）
 * - 日/德/法等若有独立词条可覆盖英文；暂无完整译稿前等同 English UX
 */
(function (global) {
  var LANG_KEY = "ai24x_lang";

  function getLang() {
    return localStorage.getItem(LANG_KEY) || "zh";
  }

  function setLang(code) {
    localStorage.setItem(LANG_KEY, code);
  }

  function isZh() {
    return getLang() === "zh";
  }

  function dictFor(code) {
    var L = global.AI24X_LOCALES || {};
    var zh = L.zh || {};
    var en = L.en || {};
    var cur = L[code] || {};
    if (code === "zh") return Object.assign({}, en, zh);
    // 国际语言：英文打底 + 当前语言覆盖；绝不混入中文
    return Object.assign({}, en, cur);
  }

  function t(key) {
    var lang = getLang();
    var d = dictFor(lang);
    if (d[key] != null && d[key] !== "") return d[key];
    var en = (global.AI24X_LOCALES && global.AI24X_LOCALES.en) || {};
    if (en[key] != null && en[key] !== "") return en[key];
    // 仅中文界面才回退到 zh；国际界面缺 key 时显示 key，避免蹦出中文
    if (lang === "zh") {
      var zh = (global.AI24X_LOCALES && global.AI24X_LOCALES.zh) || {};
      if (zh[key] != null && zh[key] !== "") return zh[key];
    }
    return key;
  }

  function apply(root) {
    root = root || document;
    var htmlMap = {
      zh: "zh-CN",
      en: "en",
      ja: "en",
      ko: "en",
      de: "en",
      fr: "en",
      es: "en",
    };
    var lang = getLang();
    document.documentElement.lang = htmlMap[lang] || (lang === "zh" ? "zh-CN" : "en");

    root.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (!key) return;
      var val = t(key);
      if (val === key) return;
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
        if (el.hasAttribute("placeholder")) el.placeholder = val;
        else el.value = val;
      } else el.textContent = val;
    });

    root.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-placeholder");
      if (!key) return;
      var val = t(key);
      if (val === key) return;
      el.placeholder = val;
    });

    root.querySelectorAll("[data-i18n-html]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-html");
      if (!key) return;
      var val = t(key);
      if (val === key) return;
      el.innerHTML = val;
    });

    // 无 data-i18n 的中文默认节点：国际语言下隐藏或由页面脚本重绘
    root.querySelectorAll("[data-i18n-zh-only]").forEach(function (el) {
      el.style.display = isZh() ? "" : "none";
    });

    var sel = document.getElementById("lang-select");
    if (sel) sel.value = getLang();
    var ts = document.getElementById("theme-select");
    if (ts) ts.value = localStorage.getItem("ai24x_theme") || "blue";
  }

  global.AI24X_I18N = {
    getLang: getLang,
    setLang: setLang,
    isZh: isZh,
    t: t,
    apply: apply,
    LANGS: [
      { code: "zh", label: "中文" },
      { code: "en", label: "English" },
      { code: "ja", label: "日本語" },
      { code: "ko", label: "한국어" },
      { code: "de", label: "Deutsch" },
      { code: "fr", label: "Français" },
      { code: "es", label: "Español" },
    ],
  };
})(typeof window !== "undefined" ? window : this);
