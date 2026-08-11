/**
 * 国际化 — 语言包为扁平 key：nav.home、page.index.title 等
 *
 * 策略（2026-08-02 · 国际站低调默认英文）：
 * - 已选过语言（localStorage）→ 永远尊重
 * - ?lang=xx 可强制并写入（便于自测 / 运营链接）
 * - 首访：固定英文（不跟浏览器语言自动切中文；中文等靠用户手动切）
 * - 其它语言选项：英文打底，避免缺译回落到中文造成中英混杂
 */
(function (global) {
  var LANG_KEY = "ai24x_lang";
  var ALLOWED = { zh: 1, en: 1, ja: 1, ko: 1, de: 1, fr: 1, es: 1 };

  function normalizeLang(code) {
    var c = String(code || "")
      .trim()
      .toLowerCase()
      .replace(/_/g, "-");
    if (!c) return "";
    if (ALLOWED[c]) return c;
    var base = c.split("-")[0];
    if (ALLOWED[base]) return base;
    if (base === "zh") return "zh";
    return "";
  }

  function detectFirstVisitLang() {
    try {
      var q = new URLSearchParams(window.location.search || "").get("lang");
      var fromQ = normalizeLang(q);
      if (fromQ) {
        localStorage.setItem(LANG_KEY, fromQ);
        return fromQ;
      }
    } catch (e) {}
    var saved = normalizeLang(localStorage.getItem(LANG_KEY));
    if (saved) return saved;
    var initial = "en";
    try {
      localStorage.setItem(LANG_KEY, initial);
    } catch (e2) {}
    return initial;
  }

  function getLang() {
    var saved = normalizeLang(localStorage.getItem(LANG_KEY));
    if (saved) return saved;
    return detectFirstVisitLang();
  }

  function setLang(code) {
    var n = normalizeLang(code) || "en";
    localStorage.setItem(LANG_KEY, n);
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
    return Object.assign({}, en, cur);
  }

  function t(key) {
    var lang = getLang();
    var d = dictFor(lang);
    if (d[key] != null && d[key] !== "") return d[key];
    var en = (global.AI24X_LOCALES && global.AI24X_LOCALES.en) || {};
    if (en[key] != null && en[key] !== "") return en[key];
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

    root.querySelectorAll("[data-i18n-zh-only]").forEach(function (el) {
      el.style.display = isZh() ? "" : "none";
    });

    root.querySelectorAll("[data-i18n-en-priority]").forEach(function (el) {
      if (isZh()) el.classList.remove("is-primary-cta");
      else el.classList.add("is-primary-cta");
    });

    var sel = document.getElementById("lang-select");
    if (sel) sel.value = getLang();
    var ts = document.getElementById("theme-select");
    if (ts) ts.value = localStorage.getItem("ai24x_theme") || "blue";

    try {
      document.documentElement.classList.remove("i18n-pending");
      var pendingStyle = document.getElementById("ai24x-i18n-pending");
      if (pendingStyle && pendingStyle.parentNode) pendingStyle.parentNode.removeChild(pendingStyle);
    } catch (e2) {}
  }

  // 尽早解析首访语言（与 i18n-boot 一致）；页面在 apply 前保持 i18n-pending 隐藏
  try {
    detectFirstVisitLang();
  } catch (e) {}

  global.AI24X_I18N = {
    getLang: getLang,
    setLang: setLang,
    isZh: isZh,
    t: t,
    apply: apply,
    LANGS: [
      { code: "en", label: "English" },
      { code: "de", label: "Deutsch" },
      { code: "fr", label: "Français" },
      { code: "es", label: "Español" },
      { code: "zh", label: "中文" },
      { code: "ko", label: "한국어" },
      { code: "ja", label: "日本語" },
    ],
  };
})(typeof window !== "undefined" ? window : this);
