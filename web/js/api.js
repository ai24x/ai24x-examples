/**
 * AI24X 前端 API 封装（对接 api.ai24x.com 或当前站点同源 API）
 * 生产默认：https://api.ai24x.com
 * 本地：与当前页面同源（例如本机静态站与 API 同端口时）
 */
(function (global) {
  var STORAGE_BASE = "ai24x_api_base";
  var STORAGE_KEY = "ai24x_api_key";
  var PRODUCTION = "https://api.ai24x.com";

  function getBase() {
    var saved = localStorage.getItem(STORAGE_BASE);
    if (saved) return saved.replace(/\/$/, "");
    var h = location.hostname;
    if (h === "localhost" || h === "127.0.0.1" || h === "::1")
      return (location.origin || "").replace(/\/$/, "") || PRODUCTION;
    return PRODUCTION;
  }

  function setBase(url) {
    if (url) localStorage.setItem(STORAGE_BASE, url.replace(/\/$/, ""));
    else localStorage.removeItem(STORAGE_BASE);
  }

  function getApiKey() {
    return localStorage.getItem(STORAGE_KEY) || "";
  }

  function setApiKey(key) {
    if (key) localStorage.setItem(STORAGE_KEY, key);
    else localStorage.removeItem(STORAGE_KEY);
  }

  async function request(path, options) {
    options = options || {};
    var url = getBase() + path;
    var headers = Object.assign(
      { Accept: "application/json" },
      options.headers || {}
    );
    if (options.body && typeof options.body === "string" && !headers["Content-Type"])
      headers["Content-Type"] = "application/json";
    var k = getApiKey();
    if (k) headers["X-API-Key"] = k;
    var res = await fetch(url, Object.assign({}, options, { headers: headers }));
    var text = await res.text();
    var data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (e) {
      data = { raw: text };
    }
    if (!res.ok) {
      function pickStr(v) {
        if (v == null) return "";
        if (typeof v === "string") return v.trim();
        return "";
      }
      /** Flatten JSON error into one user-visible line (Chinese-first). */
      function humanErrorMessage(status, body, fallbackText) {
        var b = body && typeof body === "object" ? body : null;
        var parts = [];
        if (b) {
          parts.push(pickStr(b.error));
          parts.push(pickStr(b.message));
          var d = b.detail;
          if (typeof d === "string") parts.push(d.trim());
          else if (Array.isArray(d)) {
            parts.push(
              d
                .map(function (e) {
                  return pickStr(e && e.msg);
                })
                .filter(Boolean)
                .join("；")
            );
          }
        }
        var joined = parts.filter(Boolean).join(" ").trim();
        if (!joined && fallbackText) joined = String(fallbackText).trim();
        if (!joined) joined = "请求失败（" + status + "）";

        // Normalize known auth failure (avoid showing Python dict / machine keys).
        if (
          status === 401 &&
          (joined.indexOf("手机号/邮箱或密码错误") >= 0 ||
            joined.indexOf("手机号或密码错误") >= 0 ||
            joined.indexOf("邮箱或密码错误") >= 0 ||
            joined.indexOf("密码错误") >= 0)
        ) {
          return "手机号/邮箱或密码错误，请检查后重试。";
        }
        if (status === 401) return "登录已失效或未授权，请重新登录。";
        if (status === 403) return "没有权限执行此操作。";
        if (status === 429) return "请求过于频繁，请稍后再试。";
        if (status >= 500) return "服务暂时不可用，请稍后再试。";

        // If server still returned a JSON-looking blob, keep it short.
        if (joined.length > 180) joined = joined.slice(0, 177) + "…";
        return joined;
      }

      var msg = humanErrorMessage(res.status, data, text);
      var err = new Error(msg);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  /** POST /v1/chat/run — optional user_id query for integrations that pass it in the URL */
  function chatRun(body, userId) {
    var q = userId ? "?user_id=" + encodeURIComponent(userId) : "";
    return request("/v1/chat/run" + q, {
      method: "POST",
      body: JSON.stringify(body || {}),
    });
  }

  function health() {
    return request("/health", { method: "GET" });
  }

  function userInfo() {
    return request("/v1/user/info", { method: "GET" });
  }

  /** Auth: login */
  function authLogin(payload) {
    return request("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  }

  function authRegister(payload) {
    return request("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  }

  /** POST /v1/auth/sms/send — may require SMS_INTERNAL_KEY in headers when the server is configured for it */
  function authSmsSend(payload, headers) {
    return request("/v1/auth/sms/send", {
      method: "POST",
      body: JSON.stringify(payload || {}),
      headers: headers || {},
    });
  }

  function keysList() {
    return request("/v1/keys", { method: "GET" });
  }

  function keysCreate(payload) {
    return request("/v1/keys", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  }

  function billingBalance() {
    return request("/v1/billing/balance", { method: "GET" });
  }

  function referralsSummary() {
    return request("/v1/referrals/summary", { method: "GET" });
  }

  global.AI24X_API = {
    getBase: getBase,
    setBase: setBase,
    getApiKey: getApiKey,
    setApiKey: setApiKey,
    request: request,
    chatRun: chatRun,
    health: health,
    userInfo: userInfo,
    authLogin: authLogin,
    authRegister: authRegister,
    authSmsSend: authSmsSend,
    keysList: keysList,
    keysCreate: keysCreate,
    billingBalance: billingBalance,
    referralsSummary: referralsSummary,
  };
})(typeof window !== "undefined" ? window : this);
