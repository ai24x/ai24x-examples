/**
 * AI24X 前端 API 封装（对接 api.ai24x.com 或当前站点同源 API）
 * 生产默认：https://api.ai24x.com
 * 本地：与当前页面同源（例如本机静态站与 API 同端口时）
 */
(function (global) {
  var STORAGE_BASE = "ai24x_api_base";
  var STORAGE_KEY = "ai24x_api_key";
  var STORAGE_TOKEN = "ai24x_auth_token";
  var STORAGE_USER = "ai24x_auth_user";
  var PRODUCTION = "https://api.ai24x.com";

  function getBase() {
    var h = (location.hostname || "").toLowerCase();
    var onProdHost = h === "ai24x.com" || h.endsWith(".ai24x.com");
    var saved = localStorage.getItem(STORAGE_BASE);
    if (saved) {
      saved = saved.replace(/\/$/, "");
      // 公网页若误存了本机 API，会导致 Failed to fetch / 无法到账
      if (onProdHost && /^(https?:\/\/)?(localhost|127\.0\.0\.1|::1)(:|\/|$)/i.test(saved)) {
        try {
          localStorage.removeItem(STORAGE_BASE);
        } catch (e) {}
        return PRODUCTION;
      }
      return saved;
    }
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

  function getAuthToken() {
    return localStorage.getItem(STORAGE_TOKEN) || "";
  }

  function setAuthToken(token) {
    if (token) localStorage.setItem(STORAGE_TOKEN, token);
    else localStorage.removeItem(STORAGE_TOKEN);
  }

  function getAuthUser() {
    try {
      var raw = localStorage.getItem(STORAGE_USER);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function setAuthUser(user) {
    if (user) localStorage.setItem(STORAGE_USER, JSON.stringify(user));
    else localStorage.removeItem(STORAGE_USER);
  }

  function clearAuth() {
    localStorage.removeItem(STORAGE_TOKEN);
    localStorage.removeItem(STORAGE_USER);
  }

  function saveAuthSession(data) {
    if (!data || !data.token) return;
    setAuthToken(data.token);
    if (data.user) setAuthUser(data.user);
  }

  /**
   * 主站登录/注册 UI 是否开放。
   * - 本机 / ai24x.com：默认开放（Token 实付联调需要）
   * - 其它域名：默认关；?auth=1 强制开，?auth=0 强制关
   */
  function isLocalAuthOpen() {
    try {
      var q = location.search || "";
      if (/(?:^|[?&])auth=0(?:&|$)/.test(q)) return false;
      if (/(?:^|[?&])auth=1(?:&|$)/.test(q)) return true;
    } catch (e) {}
    var h = (location.hostname || "").toLowerCase();
    if (h === "localhost" || h === "127.0.0.1" || h === "::1") return true;
    if (h === "ai24x.com" || h.endsWith(".ai24x.com")) return true;
    return false;
  }

  /** 是否本机预览（用于展示本地联调提示） */
  function isLocalHost() {
    var h = (location.hostname || "").toLowerCase();
    return h === "localhost" || h === "127.0.0.1" || h === "::1";
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
    var tok = getAuthToken();
    if (tok && !headers.Authorization) headers.Authorization = "Bearer " + tok;
    var k = getApiKey();
    if (k && !headers["X-API-Key"]) headers["X-API-Key"] = k;
    var res;
    try {
      res = await fetch(url, Object.assign({}, options, { headers: headers }));
    } catch (e) {
      var raw = String((e && e.message) || e || "");
      var netZh =
        "无法连接 API 服务。请稍后重试；若持续失败，请检查 api.ai24x.com 是否正常。";
      var netEn =
        "Cannot reach the API. Try again later, or check that api.ai24x.com is up.";
      var msg = /failed to fetch|networkerror|load failed|network request failed|fetch failed/i.test(
        raw
      )
        ? isZhUi()
          ? netZh
          : netEn
        : raw || (isZhUi() ? "网络错误" : "Network error");
      var err = new Error(msg);
      err.status = 0;
      err.cause = e;
      throw err;
    }
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
        // Nginx/HTML 502 等无 JSON 时，避免把整页 HTML 抛给用户
        if (/<\s*html|bad gateway|502/i.test(joined)) {
          joined = isZhUi()
            ? "API 网关异常（" + status + "）。服务可能未启动，请稍后重试。"
            : "API gateway error (" + status + "). The service may be down.";
        }
        if (!joined) joined = isZhUi() ? "请求失败（" + status + "）" : "Request failed (" + status + ")";

        if (
          status === 401 &&
          (joined.indexOf("手机号/邮箱或密码错误") >= 0 ||
            joined.indexOf("手机号或密码错误") >= 0 ||
            joined.indexOf("邮箱或密码错误") >= 0 ||
            joined.indexOf("密码错误") >= 0)
        ) {
          return "手机号/邮箱或密码错误，请检查后重试。";
        }
        if (status === 401)
          return isZhUi() ? "登录已失效或未授权，请重新登录。" : "Unauthorized. Please sign in again.";
        if (status === 403) return isZhUi() ? "没有权限执行此操作。" : "Forbidden.";
        if (status === 429) return isZhUi() ? "请求过于频繁，请稍后再试。" : "Too many requests. Try later.";
        // 支付下单 502 需露出上游原因，便于副脑排障（勿整页 HTML）
        if (status >= 500) {
          if (
            joined &&
            !/<\s*html/i.test(joined) &&
            /(微信|支付宝|下单失败|wechat|alipay|pay)/i.test(joined)
          ) {
            return joined.length > 240 ? joined.slice(0, 237) + "…" : joined;
          }
          return isZhUi() ? "服务暂时不可用，请稍后再试。" : "Service temporarily unavailable.";
        }

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

  function authLogin(payload) {
    return request("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    }).then(function (data) {
      saveAuthSession(data);
      return data;
    });
  }

  function authRegister(payload) {
    return request("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    }).then(function (data) {
      saveAuthSession(data);
      return data;
    });
  }

  function authSmsSend(payload, headers) {
    return request("/v1/auth/sms/send", {
      method: "POST",
      body: JSON.stringify(payload || {}),
      headers: headers || {},
    });
  }

  function authEmailSend(payload) {
    return request("/v1/auth/email/send", {
      method: "POST",
      body: JSON.stringify(payload || {}),
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

  function keysDelete(keyId) {
    return request("/v1/keys/" + encodeURIComponent(keyId), { method: "DELETE" });
  }

  function billingBalance() {
    return request("/v1/billing/balance", { method: "GET" });
  }

  function billingUsage(params) {
    params = params || {};
    var q = [];
    if (params.limit != null) q.push("limit=" + encodeURIComponent(params.limit));
    if (params.offset != null) q.push("offset=" + encodeURIComponent(params.offset));
    if (params.entry_type) q.push("entry_type=" + encodeURIComponent(params.entry_type));
    return request("/v1/billing/usage" + (q.length ? "?" + q.join("&") : ""), { method: "GET" });
  }

  function billingPlans() {
    return request("/v1/billing/plans", { method: "GET" });
  }

  function billingWechatNative(plan) {
    return request("/v1/billing/wechat/native", {
      method: "POST",
      body: JSON.stringify({ plan: plan }),
    });
  }

  function billingAlipayWap(plan) {
    return request("/v1/billing/alipay/wap", {
      method: "POST",
      body: JSON.stringify({ plan: plan }),
    });
  }

  function billingPaypalOrder(plan) {
    return request("/v1/billing/paypal/order", {
      method: "POST",
      body: JSON.stringify({ plan: plan }),
    });
  }

  function billingOrders(limit) {
    var q = limit != null ? "?limit=" + encodeURIComponent(limit) : "";
    return request("/v1/billing/orders" + q, { method: "GET" });
  }

  function billingMockFulfill(outTradeNo) {
    return request("/v1/billing/orders/mock_fulfill", {
      method: "POST",
      body: JSON.stringify({ out_trade_no: outTradeNo }),
    });
  }

  function billingQueryFulfill(outTradeNo, channel) {
    var path =
      channel === "alipay"
        ? "/v1/billing/alipay/query_and_fulfill"
        : channel === "paypal"
          ? "/v1/billing/paypal/capture"
          : "/v1/billing/wechat/query_and_fulfill";
    return request(path, {
      method: "POST",
      body: JSON.stringify({ out_trade_no: outTradeNo }),
    });
  }

  function listModels() {
    return request("/v1/models", { method: "GET" });
  }

  function referralsSummary() {
    return request("/v1/referrals/summary", { method: "GET" });
  }

  function referralsCode() {
    return request("/v1/referrals/code", { method: "GET" });
  }

  /** 中文 UI 只展示人民币；其它语言展示美元（不混写） */
  function isZhUi() {
    try {
      if (global.AI24X_I18N && typeof global.AI24X_I18N.isZh === "function") {
        return global.AI24X_I18N.isZh();
      }
      return !global.AI24X_I18N || global.AI24X_I18N.getLang() === "zh";
    } catch (e) {
      return true;
    }
  }

  function planTitle(p) {
    if (!p) return "";
    if (isZhUi()) return p.title_zh || p.title || p.plan || "";
    return p.title_en || p.title_zh || p.title || p.plan || "";
  }

  function planPriceLabel(p) {
    if (!p) return "";
    if (isZhUi()) return "¥" + (p.price_yuan || "");
    return p.price_usd ? "$" + p.price_usd : "¥" + (p.price_yuan || "");
  }

  function planNote(p) {
    if (!p) return "";
    if (isZhUi()) return p.note_zh || p.note || "";
    return p.note_en || p.note_zh || p.note || "";
  }

  function planSettleHint(p) {
    if (isZhUi()) {
      return (p && p.settle_hint_zh) || "支持微信支付、支付宝";
    }
    return (p && p.settle_hint_en) || "Pay with PayPal (USD) on the international site";
  }

  global.AI24X_API = {
    getBase: getBase,
    setBase: setBase,
    getApiKey: getApiKey,
    setApiKey: setApiKey,
    getAuthToken: getAuthToken,
    setAuthToken: setAuthToken,
    getAuthUser: getAuthUser,
    setAuthUser: setAuthUser,
    clearAuth: clearAuth,
    saveAuthSession: saveAuthSession,
    isLocalAuthOpen: isLocalAuthOpen,
    isLocalHost: isLocalHost,
    request: request,
    chatRun: chatRun,
    health: health,
    userInfo: userInfo,
    authLogin: authLogin,
    authRegister: authRegister,
    authSmsSend: authSmsSend,
    authEmailSend: authEmailSend,
    keysList: keysList,
    keysCreate: keysCreate,
    keysDelete: keysDelete,
    billingBalance: billingBalance,
    billingUsage: billingUsage,
    billingPlans: billingPlans,
    billingWechatNative: billingWechatNative,
    billingAlipayWap: billingAlipayWap,
    billingPaypalOrder: billingPaypalOrder,
    billingOrders: billingOrders,
    billingMockFulfill: billingMockFulfill,
    billingQueryFulfill: billingQueryFulfill,
    listModels: listModels,
    referralsSummary: referralsSummary,
    referralsCode: referralsCode,
    isZhUi: isZhUi,
    planTitle: planTitle,
    planPriceLabel: planPriceLabel,
    planNote: planNote,
    planSettleHint: planSettleHint,
  };
})(typeof window !== "undefined" ? window : this);
