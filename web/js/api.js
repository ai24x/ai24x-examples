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
    // true=只用 Key；false=只用登录会话；undefined=自动（有 JWT 不带 Key，无 JWT 才带 Key）
    var preferApiKey = options.preferApiKey;
    var url = getBase() + path;
    var headers = Object.assign(
      { Accept: "application/json" },
      options.headers || {}
    );
    if (options.body && typeof options.body === "string" && !headers["Content-Type"])
      headers["Content-Type"] = "application/json";
    var tok = getAuthToken();
    var k = getApiKey();
    if (preferApiKey === true) {
      // 勾选「用 API Key」：只带 Key，勿带 JWT（否则后端 JWT 优先，勾选无效）
      if (k && !headers["X-API-Key"]) headers["X-API-Key"] = k;
    } else if (preferApiKey === false) {
      // 默认试调用：只带登录会话，绝不偷带残留 sk
      if (tok && !headers.Authorization) headers.Authorization = "Bearer " + tok;
    } else {
      // 余额/密钥等：已登录只走 JWT，避免串号；未登录才用本地 Key
      if (tok && !headers.Authorization) headers.Authorization = "Bearer " + tok;
      if (k && !headers["X-API-Key"] && !tok) headers["X-API-Key"] = k;
    }
    var fetchOpts = Object.assign({}, options, { headers: headers });
    delete fetchOpts.preferApiKey;
    var res;
    try {
      res = await fetch(url, fetchOpts);
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
      /** 后端仍返回中文 detail 时，英文 UI 映射（含精确句与前缀） */
      var DETAIL_EN = {
        "该优惠套餐每位用户限购一次，请选择其它套餐。":
          "This promo plan is limited to one purchase per account. Please choose another plan.",
        "账号暂不可用，请联系客服。": "This account is unavailable. Please contact support.",
        "用户不存在": "User not found.",
        "需要登录": "Please sign in.",
        "登录已失效": "Session expired. Please sign in again.",
        "余额不足，请充值后再试": "Insufficient balance. Please top up and try again.",
        "余额不足，请充值": "Insufficient balance. Please top up.",
        "今日免费额度已用完，请充值继续使用，或明日再试。":
          "Today’s free quota is used up. Top up to continue, or try again tomorrow.",
        "Token 在线支付未开启（TOKEN_PAY_ENABLED）": "Online payment is not available right now.",
        "Token 在线支付未开启": "Online payment is not available right now.",
        "微信未配置完整，或 TOKEN_WECHAT_NOTIFY_URL 为空（须指向主站 Token 回调，勿复用 a1 回调）":
          "WeChat Pay is not available right now.",
        "支付宝未配置完整，或 TOKEN_ALIPAY_NOTIFY_URL 为空（须指向主站 Token 回调）":
          "Alipay is not available right now.",
        "PayPal 未配置（PAYPAL_CLIENT_ID / SECRET）": "PayPal is not available right now.",
        "PayPal 未配置": "PayPal is not available right now.",
        "微信未配置": "WeChat Pay is not available right now.",
        "支付宝未配置": "Alipay is not available right now.",
        "订单不存在": "Order not found.",
        "订单不属于当前用户": "This order does not belong to your account.",
        "支付尚未完成，请稍后再试。": "Payment is not completed yet. Please try again shortly.",
        "mock 支付未开启": "Mock payment is disabled.",
        "手机号格式不正确，请填写 11 位手机号": "Enter a valid 11-digit mobile number.",
        "该手机号已注册": "This mobile number is already registered.",
        "该邮箱已注册": "This email is already registered.",
        "邮箱格式不正确": "Enter a valid email address.",
        "验证码错误或已过期，请重新获取": "Invalid or expired code. Please request a new one.",
        "验证码错误或已过期，请重新获取验证码": "Invalid or expired code. Please request a new one.",
        "邮箱验证码错误或已过期，请重新获取": "Invalid or expired email code. Please request a new one.",
        "手机号或密码错误，请检查后重试。": "Incorrect account or password. Please try again.",
        "短信服务暂不可用，请稍后再试。": "SMS is temporarily unavailable. Please try again later.",
        "短信服务暂时不可用，请稍后再试。": "SMS is temporarily unavailable. Please try again later.",
        "邮件服务暂不可用，请稍后再试。": "Email is temporarily unavailable. Please try again later.",
        "服务暂不可用，请稍后再试。": "Service temporarily unavailable. Please try again later.",
        "禁止访问": "Access denied.",
        "参数无效，请检查后再试。": "Invalid parameters. Please check and try again.",
        "无效的 API Key": "Invalid API key.",
        "需要有效的 X-API-Key": "A valid API key is required.",
        "无效的API Key或用户ID": "Invalid API key or user id.",
        "请填写手机号或邮箱": "Enter a mobile number or email.",
        "账号暂不可用，请联系客服。": "This account is unavailable. Please contact support.",
        "密钥无效，请检查后再试。": "Invalid key. Please check and try again.",
        "点名模型需有效会员权益，请升级后再试。":
          "This model requires an active membership. Please upgrade and try again.",
        "模型服务暂时繁忙，请稍后再试。": "The model service is busy. Please try again later.",
        "PayPal 商户凭证无效，请稍后重试或联系客服。":
          "PayPal merchant credentials are invalid. Please try again later or contact support.",
        "PayPal 下单暂时失败，请稍后重试。": "PayPal checkout failed temporarily. Please try again later.",
        "PayPal 确认失败，请稍后在「我的订单」点确认到账。":
          "PayPal confirmation failed. Please confirm payment later under My Orders.",
      };
      function localizeDetail(text) {
        var s = pickStr(text);
        if (!s || isZhUi()) return s;
        if (DETAIL_EN[s]) return DETAIL_EN[s];
        var keys = Object.keys(DETAIL_EN);
        for (var i = 0; i < keys.length; i++) {
          if (s.indexOf(keys[i]) >= 0) return DETAIL_EN[keys[i]];
        }
        if (/微信下单失败/i.test(s)) return "WeChat order failed. Please try again later.";
        if (/支付宝下单失败/i.test(s)) return "Alipay order failed. Please try again later.";
        if (/额度不足/.test(s)) return "Not enough credits for this request. Please top up.";
        // 英文 UI 仍收到中文：勿原样露出
        if (/[\u4e00-\u9fff]/.test(s)) return "Something went wrong. Please try again.";
        return s;
      }
      /** 兼容旧后端把双语 dict 写成 Python str(dict) 塞进 error 的事故 */
      function parseBilingualBlob(text) {
        var s = pickStr(text);
        if (!s || s.indexOf("message_zh") < 0) return null;
        function grab(key) {
          var re = new RegExp(
            "['\"]" + key + "['\"]\\s*:\\s*['\"]([^'\"]*)['\"]"
          );
          var m = s.match(re);
          return m ? m[1] : "";
        }
        var zh = grab("message_zh");
        var en = grab("message_en");
        var msg = grab("message");
        if (!zh && !en && !msg) {
          try {
            var j = JSON.parse(s);
            if (j && typeof j === "object") {
              zh = pickStr(j.message_zh);
              en = pickStr(j.message_en);
              msg = pickStr(j.message);
            }
          } catch (e) {
            return null;
          }
        }
        if (!zh && !en && !msg) return null;
        return { message_zh: zh, message_en: en, message: msg || zh };
      }
      function pickDetail(d) {
        if (d == null) return "";
        if (typeof d === "string") {
          var blob = parseBilingualBlob(d);
          if (blob) return pickDetail(blob);
          return localizeDetail(d);
        }
        if (Array.isArray(d)) {
          return d
            .map(function (e) {
              return localizeDetail(pickStr(e && (e.msg || e.message)));
            })
            .filter(Boolean)
            .join(isZhUi() ? "；" : "; ");
        }
        if (typeof d === "object") {
          if (isZhUi())
            return pickStr(d.message_zh) || pickStr(d.message) || localizeDetail(pickStr(d.message_en));
          return (
            pickStr(d.message_en) ||
            localizeDetail(pickStr(d.message_zh) || pickStr(d.message)) ||
            pickStr(d.message)
          );
        }
        return "";
      }
      function humanErrorMessage(status, body, fallbackText) {
        var b = body && typeof body === "object" ? body : null;
        var parts = [];
        if (b) {
          // 双语 detail 对象优先；勿把 error 里的 str(dict) 原样拼进文案
          var fromDetail = b.detail != null ? pickDetail(b.detail) : "";
          if (fromDetail) {
            parts.push(fromDetail);
          } else {
            var fromError = pickDetail(b.error);
            if (fromError) parts.push(fromError);
            else parts.push(localizeDetail(pickStr(b.message)));
          }
        }
        var joined = parts.filter(Boolean).join(" ").trim();
        if (!joined && fallbackText) {
          var fb = pickDetail(String(fallbackText).trim());
          joined = fb || localizeDetail(String(fallbackText).trim());
        }
        // 仍含 message_zh 字样则视为泄漏，兜底短句
        if (/message_zh|message_en/.test(joined)) {
          joined = isZhUi()
            ? "操作失败，请选择其它套餐或稍后重试。"
            : "That didn’t work. Please choose another plan or try again.";
        }
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
            joined.indexOf("密码错误") >= 0 ||
            /incorrect account or password/i.test(joined))
        ) {
          return isZhUi()
            ? "手机号/邮箱或密码错误，请检查后重试。"
            : "Incorrect account or password. Please try again.";
        }
        if (status === 401) {
          var code =
            b && typeof b.detail === "object" && b.detail
              ? String(b.detail.code || "")
              : "";
          if (
            code === "invalid_api_key" ||
            /无效的\s*API\s*Key|Invalid API key/i.test(joined)
          ) {
            if (preferApiKey === true) {
              return isZhUi()
                ? "API Key 无效。请到「API 密钥」创建后，把完整 Key 粘到上方；或取消勾选，改用登录发送。"
                : "Invalid API key. Create one under API keys, paste the full key above — or uncheck to use login.";
            }
            // 线上旧版 chat/run 会把登录 JWT 误判成 Key；勿引导用户去「取消勾选」
            return isZhUi()
              ? "登录会话未被试调用接受。请稍后再试；或勾选「用 API Key」发送。"
              : "Login session was not accepted for try-call. Try again later, or check “Use API key”.";
          }
          return isZhUi()
            ? "登录已失效或未授权，请重新登录。"
            : "Unauthorized. Please sign in again.";
        }
        if (status === 403) {
          // 保留已本地化的具体原因（如账号冻结）；泛化「禁止访问」才用默认句
          if (
            joined &&
            joined !== "禁止访问" &&
            joined !== "Access denied." &&
            (isZhUi() || !/[\u4e00-\u9fff]/.test(joined))
          ) {
            return joined.length > 180 ? joined.slice(0, 177) + "…" : joined;
          }
          return isZhUi() ? "没有权限执行此操作。" : "Forbidden.";
        }
        if (status === 429) {
          if (
            joined &&
            (joined.indexOf("免费额度") >= 0 ||
              /free quota/i.test(joined) ||
              /not enough credits/i.test(joined) ||
              joined.indexOf("额度不足") >= 0)
          ) {
            return isZhUi() || !/[\u4e00-\u9fff]/.test(joined)
              ? joined.length > 180
                ? joined.slice(0, 177) + "…"
                : joined
              : localizeDetail(joined);
          }
          return isZhUi() ? "请求过于频繁，请稍后再试。" : "Too many requests. Try later.";
        }
        // 支付下单 502：中文 UI 可保留简短原因；英文已 localize
        if (status >= 500) {
          if (
            joined &&
            !/<\s*html/i.test(joined) &&
            /(微信|支付宝|下单失败|wechat|alipay|pay)/i.test(joined)
          ) {
            var payMsg = isZhUi() ? joined : localizeDetail(joined);
            return payMsg.length > 240 ? payMsg.slice(0, 237) + "…" : payMsg;
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

  function chatRun(body, userId, opts) {
    opts = opts || {};
    var q = userId ? "?user_id=" + encodeURIComponent(userId) : "";
    return request("/v1/chat/run" + q, {
      method: "POST",
      body: JSON.stringify(body || {}),
      // 显式 true/false，避免 undefined 落到「无 token 偷带 Key」
      preferApiKey: !!opts.preferApiKey,
    });
  }

  function logout() {
    clearAuth();
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
    var p = Object.assign({}, payload || {});
    if (!p.lang) {
      p.lang = (typeof isZhUi === "function" && isZhUi()) ? "zh" : "en";
    }
    return request("/v1/auth/email/send", {
      method: "POST",
      body: JSON.stringify(p),
    });
  }

  function authCaptchaGet() {
    return request("/v1/auth/captcha", { method: "GET" });
  }
  function authPasswordChange(payload) {
    return request("/v1/auth/password/change", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    }).then(function (data) {
      if (data && data.token) saveAuthSession(data);
      return data;
    });
  }
  function authPasswordReset(payload) {
    return request("/v1/auth/password/reset", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    }).then(function (data) {
      if (data && data.token) saveAuthSession(data);
      return data;
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

  function keysRename(keyId, payload) {
    return request("/v1/keys/" + encodeURIComponent(keyId), {
      method: "PATCH",
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

  function billingCreemOrder(plan) {
    return request("/v1/billing/creem/order", {
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

  function billingCryptoOrder(plan) {
    return request("/v1/billing/crypto/order", {
      method: "POST",
      body: JSON.stringify({ plan: plan }),
    });
  }

  function billingCryptoSubmit(outTradeNo, txid) {
    return request("/v1/billing/crypto/submit", {
      method: "POST",
      body: JSON.stringify({ out_trade_no: outTradeNo, txid: txid }),
    });
  }

  function billingCryptoVerify(outTradeNo) {
    return request("/v1/billing/crypto/verify", {
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
          : channel === "creem"
            ? "/v1/billing/creem/query"
            : "/v1/billing/wechat/query_and_fulfill";
    return request(path, {
      method: "POST",
      body: JSON.stringify({ out_trade_no: outTradeNo }),
    });
  }

  function listModels() {
    return request("/v1/models", { method: "GET" });
  }

  function supportAsk(question, lang) {
    return request("/v1/support/ask", {
      method: "POST",
      body: JSON.stringify({
        question: question || "",
        lang: lang || (isZhUi() ? "zh" : "en"),
      }),
    });
  }

  function supportTicketCreate(payload) {
    return request("/v1/support/tickets", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  }

  function supportTicketList(limit, offset) {
    var qs = "limit=" + (limit || 20) + "&offset=" + (offset || 0);
    return request("/v1/support/tickets?" + qs, { method: "GET" });
  }

  function referralsSummary() {
    return request("/v1/referrals/summary", { method: "GET" });
  }

  function referralsCode() {
    return request("/v1/referrals/code", { method: "GET" });
  }

  /** 被邀请人列表：脱敏用户名 / 注册时间 / 是否激活 */
  function referralsInvitees(limit, offset) {
    var qs = "limit=" + (limit || 50) + "&offset=" + (offset || 0);
    return request("/v1/referrals/invitees?" + qs, { method: "GET" });
  }

  /** 中文 UI 只展示人民币；其它语言（含 en/ja/ko…）展示美元与英文文案 */
  function isZhUi() {
    try {
      if (global.AI24X_I18N && typeof global.AI24X_I18N.isZh === "function") {
        return !!global.AI24X_I18N.isZh();
      }
      if (global.AI24X_I18N && typeof global.AI24X_I18N.getLang === "function") {
        return global.AI24X_I18N.getLang() === "zh";
      }
      // 国际站默认英文；勿在缺 i18n 时回落中文
      return false;
    } catch (e) {
      return false;
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

  /** 套餐能力：额度 / 名模资格 / 是否齐备可点名 */
  function planCaps(p) {
    var credits =
      p && (p.cap_credits != null ? !!p.cap_credits : Number(p.credit_tokens || 0) > 0);
    var vip = p && (p.cap_vip != null ? !!p.cap_vip : !!p.set_vip);
    var named =
      p &&
      (p.cap_named_ready != null ? !!p.cap_named_ready : !!(vip && credits));
    return {
      credits: !!credits,
      vip: !!vip,
      named: !!named,
      vipOnly: !!vip && !credits,
      creditsOnly: !!credits && !vip,
      recommended: !!(p && p.recommended),
    };
  }

  function planCreditsShort(p) {
    var n = Number((p && p.credit_tokens) || 0);
    if (!n) return "—";
    if (isZhUi()) {
      if (n >= 1e8) return (n / 1e8).toFixed(n % 1e8 === 0 ? 0 : 1) + " 亿";
      if (n >= 1e4) return Math.round(n / 1e4) + " 万";
      return String(n);
    }
    if (n >= 1e6) return Math.round(n / 1e6) + "M";
    if (n >= 1e3) return Math.round(n / 1e3) + "k";
    return String(n);
  }

  /** 一句话定位（对比表用，避免多段说明） */
  function planOneLiner(p) {
    var zh = isZhUi();
    var c = planCaps(p);
    if (c.named) {
      return zh ? "名模可直接用（资格+额度齐）" : "Named models ready (access + credits)";
    }
    if (c.vipOnly) {
      return zh ? "会员资格" : "VIP access";
    }
    if (c.creditsOnly && Number((p && p.credit_tokens) || 0) <= 2000000) {
      return zh ? "小额预充先跑通；要点名选 Scale" : "Small prepaid to start; Scale to name models";
    }
    if (c.creditsOnly) {
      return zh ? "日常预充；要点名选 Scale" : "Everyday credits; Scale to name models";
    }
    return "";
  }


  /** 套餐有效期标签：额度有效期 + 点名资格有效期（无则显示长期） */
  function planValidityLabel(p) {
    var zh = isZhUi();
    var parts = [];
    function fmtDays(d, kind) {
      var n = Number(d) || 0;
      if (n <= 0) return "";
      if (zh) {
        if (n % 365 === 0) return (kind === "credit" ? "额度 " : "资格 ") + (n / 365) + " 年有效";
        if (n % 30 === 0) return (kind === "credit" ? "额度 " : "资格 ") + (n / 30) + " 个月有效";
        return (kind === "credit" ? "额度 " : "资格 ") + n + " 天有效";
      }
      if (n % 365 === 0) return (kind === "credit" ? "Credits " : "Access ") + (n / 365) + "yr";
      if (n % 30 === 0) return (kind === "credit" ? "Credits " : "Access ") + (n / 30) + "mo";
      return (kind === "credit" ? "Credits " : "Access ") + n + "d";
    }
    var vd = Number((p && p.validity_days) || 0);
    var pd = Number((p && p.vip_days) || 0);
    var hasCredits = Number((p && p.credit_tokens) || 0) > 0;
    var hasVip = !!(p && (p.set_vip || p.value_pack || p.cap_vip));
    if (hasCredits && vd > 0) parts.push(fmtDays(vd, "credit"));
    if (hasVip && pd > 0) parts.push(fmtDays(pd, "access"));
    if (!parts.length) return zh ? "长期有效" : "No expiry";
    return parts.join(" \u00b7 ");
  }

  function planYesNo(flag) {
    if (isZhUi()) return flag ? "有" : "无";
    return flag ? "Yes" : "No";
  }

  /** 点名模列：无资格=无；仅资格无额度=有（需额度）；资格+额度=有 */
  function planNameAccess(p) {
    var c = planCaps(p);
    if (!c.vip) return isZhUi() ? "无" : "No";
    if (!c.credits) return isZhUi() ? "有（需额度）" : "Yes (needs credits)";
    return isZhUi() ? "有" : "Yes";
  }

  function planCapabilityTags(p) {
    var zh = isZhUi();
    var c = planCaps(p);
    var tags = [];
    if (c.recommended) tags.push(zh ? "推荐" : "Recommended");
    return tags;
  }

  function planCanLine(p) {
    return planOneLiner(p);
  }

  function planNotLine(p) {
    return "";
  }

  function planFulfillMessage(planId, outTradeNo) {
    var zh = isZhUi();
    var otn = outTradeNo ? String(outTradeNo) : "";
    var suffix = otn ? (zh ? " 单号：" + otn : " Order: " + otn) : "";
    if (planId === "token_vip_month") {
      return zh
        ? "VIP 资格已开通（30 天）：可点名名模（消耗预充额度）。" + suffix
        : "VIP access active (30 days): you can name models (billed from prepaid credits)." + suffix;
    }
    if (planId === "token_pack_100k" || planId === "token_pack_10k" || planId === "token_pack_mid") {
      return zh
        ? "预充额度已到账。要点名：选 Scale 或补购 VIP 资格包。" + suffix
        : "Credits added. For named models: choose Scale, or add VIP Pass." + suffix;
    }
    if (planId === "token_vip_month_50w") {
      return zh
        ? "Scale 已到账：12 个月名模资格 + 2.5 亿预充额度。" + suffix
        : "Scale ready: 12-month named access + 250M prepaid credits." + suffix;
    }
    if (planId === "token_value_pack") {
      return zh
        ? "限时特惠超值包已到账：3000 万 credits + 30 天白名单点名资格（白名单内名模可直接点名）。" + suffix
        : "Limited-time Value Pack credited: 30M credits + 30-day whitelist named-model access." + suffix;
    }
    return zh
      ? "支付已确认，已到账。" + suffix
      : "Paid and credited." + suffix;
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
    logout: logout,
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
    authCaptchaGet: authCaptchaGet,
    authPasswordChange: authPasswordChange,
    authPasswordReset: authPasswordReset,
    keysList: keysList,
    keysCreate: keysCreate,
    keysRename: keysRename,
    keysDelete: keysDelete,
    billingBalance: billingBalance,
    billingUsage: billingUsage,
    billingPlans: billingPlans,
    billingWechatNative: billingWechatNative,
    billingAlipayWap: billingAlipayWap,
    billingPaypalOrder: billingPaypalOrder,
    billingCreemOrder: billingCreemOrder,
    billingOrders: billingOrders,
    billingCryptoOrder: billingCryptoOrder,
    billingCryptoSubmit: billingCryptoSubmit,
    billingCryptoVerify: billingCryptoVerify,
    billingMockFulfill: billingMockFulfill,
    billingQueryFulfill: billingQueryFulfill,
    listModels: listModels,
    supportAsk: supportAsk,
    supportTicketCreate: supportTicketCreate,
    supportTicketList: supportTicketList,
    referralsSummary: referralsSummary,
    referralsCode: referralsCode,
    referralsInvitees: referralsInvitees,
    isZhUi: isZhUi,
    planTitle: planTitle,
    planPriceLabel: planPriceLabel,
    planNote: planNote,
    planValidityLabel: planValidityLabel,
    planSettleHint: planSettleHint,
    planCaps: planCaps,
    planCapabilityTags: planCapabilityTags,
    planCanLine: planCanLine,
    planNotLine: planNotLine,
    planOneLiner: planOneLiner,
    planCreditsShort: planCreditsShort,
    planYesNo: planYesNo,
    planNameAccess: planNameAccess,
    planFulfillMessage: planFulfillMessage,
  };
})(typeof window !== "undefined" ? window : this);
