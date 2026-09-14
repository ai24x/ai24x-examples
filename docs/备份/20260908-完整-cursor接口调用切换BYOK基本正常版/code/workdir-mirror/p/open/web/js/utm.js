/**
 * 广告 UTM / gclid 首触采集（localStorage）→ 注册时提交。
 * 首触不覆盖；与邀请码 invite.js 并列。
 */
(function (global) {
  var LS_KEY = "ai24x_utm_first";
  var FIELDS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "gclid",
  ];

  function clean(s) {
    return String(s || "")
      .trim()
      .replace(/[\u0000-\u001f]/g, "")
      .slice(0, 128);
  }

  function load() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
      var o = JSON.parse(raw);
      return o && typeof o === "object" ? o : null;
    } catch (e) {
      return null;
    }
  }

  function save(obj) {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(obj));
    } catch (e) {}
  }

  function fromSearch(search) {
    var out = {};
    try {
      var qs = new URLSearchParams(String(search || location.search || "").replace(/^\?/, ""));
      for (var i = 0; i < FIELDS.length; i++) {
        var k = FIELDS[i];
        var v = clean(qs.get(k));
        if (v) out[k] = v;
      }
    } catch (e) {}
    return out;
  }

  /** 从当前 URL 捕获；仅在无首触时写入 */
  function capture(search) {
    var incoming = fromSearch(search);
    if (!Object.keys(incoming).length) return load();
    var prev = load();
    if (prev && (prev.utm_source || prev.gclid)) {
      return prev;
    }
    var next = {
      utm_source: incoming.utm_source || "",
      utm_medium: incoming.utm_medium || "",
      utm_campaign: incoming.utm_campaign || "",
      utm_content: incoming.utm_content || "",
      utm_term: incoming.utm_term || "",
      gclid: incoming.gclid || "",
      landing: "",
      captured_at: new Date().toISOString(),
    };
    try {
      next.landing = String(location.pathname || "").slice(0, 200);
    } catch (e2) {}
    save(next);
    return next;
  }

  /** 注册 API body 可合并字段（空值省略） */
  function forRegisterPayload() {
    var o = capture() || load() || {};
    var body = {};
    for (var i = 0; i < FIELDS.length; i++) {
      var k = FIELDS[i];
      var v = clean(o[k]);
      if (v) body[k] = v;
    }
    return body;
  }

  try {
    capture();
  } catch (e0) {}

  global.AI24X_UTM = {
    LS_KEY: LS_KEY,
    capture: capture,
    load: load,
    forRegisterPayload: forRegisterPayload,
  };
})(typeof window !== "undefined" ? window : this);
