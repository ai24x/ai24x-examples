/**
 * 邀请码 / 短链工具（控制台、邀请页、注册页共用）
 * 短链形态：{origin}/r/{CODE} → 服务端 302 到 register.html?invite=CODE
 */
(function (global) {
  var LS_KEY = "ai24x_invite_code";

  function normalizeCode(raw) {
    return String(raw || "")
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "")
      .slice(0, 32);
  }

  function siteOrigin() {
    try {
      return String(location.origin || "").replace(/\/$/, "");
    } catch (e) {
      return "";
    }
  }

  /** 短链：https://www.ai24x.com/r/ABCD1234 */
  function shortLink(code) {
    var c = normalizeCode(code);
    if (!c) return "";
    return siteOrigin() + "/r/" + encodeURIComponent(c);
  }

  /** 兼容长链（含 UTM，一般不再主推） */
  function registerLink(code) {
    var c = normalizeCode(code);
    if (!c) return "";
    return siteOrigin() + "/register.html?invite=" + encodeURIComponent(c);
  }

  function save(code) {
    var c = normalizeCode(code);
    if (!c) return;
    try {
      localStorage.setItem(LS_KEY, c);
    } catch (e) {}
  }

  function load() {
    try {
      return normalizeCode(localStorage.getItem(LS_KEY) || "");
    } catch (e) {
      return "";
    }
  }

  /** 从 URL 捕获：?invite= / ?ref= / ?i= / ?invite_code= */
  function captureFromSearch(search) {
    try {
      var qs = new URLSearchParams(String(search || location.search || "").replace(/^\?/, ""));
      var inv = qs.get("invite") || qs.get("ref") || qs.get("i") || qs.get("invite_code") || "";
      inv = normalizeCode(inv);
      if (inv) save(inv);
      return inv;
    } catch (e) {
      return "";
    }
  }

  /** 填入注册表单：URL 优先，其次 localStorage */
  function applyToInput(inputEl) {
    if (!inputEl) return "";
    var fromUrl = captureFromSearch();
    var cur = normalizeCode(inputEl.value);
    if (cur) {
      save(cur);
      return cur;
    }
    if (fromUrl) {
      inputEl.value = fromUrl;
      return fromUrl;
    }
    var stored = load();
    if (stored) {
      inputEl.value = stored;
      return stored;
    }
    return "";
  }

  global.AI24X_INVITE = {
    LS_KEY: LS_KEY,
    normalizeCode: normalizeCode,
    shortLink: shortLink,
    registerLink: registerLink,
    save: save,
    load: load,
    captureFromSearch: captureFromSearch,
    applyToInput: applyToInput,
  };
})(typeof window !== "undefined" ? window : this);
