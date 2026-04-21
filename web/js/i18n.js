/**
 * 国际化 — 语言包为扁平 key：nav.home、page.index.title 等
 */
(function (global) {
  var LANG_KEY = "ai24x_lang";

  function getLang() {
    return localStorage.getItem(LANG_KEY) || "zh";
  }

  function setLang(code) {
    localStorage.setItem(LANG_KEY, code);
  }

  function dictFor(code) {
    var L = global.AI24X_LOCALES || {};
    var zh = L.zh || {};
    var en = L.en || {};
    var cur = L[code] || {};
    if (code === "zh") return Object.assign({}, en, zh);
    return Object.assign({}, zh, en, cur);
  }

  function t(key) {
    var d = dictFor(getLang());
    if (d[key] != null && d[key] !== "") return d[key];
    var en = dictFor("en");
    if (en[key] != null && en[key] !== "") return en[key];
    var zh = dictFor("zh");
    return zh[key] != null ? zh[key] : key;
  }

  function apply(root) {
    root = root || document;
    var htmlMap = {
      zh: "zh-CN",
      en: "en",
      ja: "ja",
      ko: "ko",
      de: "de",
      fr: "fr",
      es: "es",
    };
    document.documentElement.lang = htmlMap[getLang()] || "zh-CN";

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
      // 语言包未加载 / 缓存旧版缺少 key 时，t() 会回退为 key 字符串；保留节点内默认 HTML（如登录页闭站说明）
      if (val === key) return;
      el.innerHTML = val;
    });

    var sel = document.getElementById("lang-select");
    if (sel) sel.value = getLang();
    var ts = document.getElementById("theme-select");
    if (ts) ts.value = localStorage.getItem("ai24x_theme") || "blue";
  }

  global.AI24X_I18N = {
    getLang: getLang,
    setLang: setLang,
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
