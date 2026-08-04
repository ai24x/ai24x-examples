/**
 * 控制台：余额 / Keys / 套餐下单(mock) / 用量 / 邀请
 */
(function () {
  function $(id) {
    return document.getElementById(id);
  }

  /** 中文界面用中文；英文及其他语言（ja/ko/de…）统一英文提示 */
  function tr(zh, en) {
    try {
      if (window.AI24X_I18N && typeof window.AI24X_I18N.isZh === "function") {
        return window.AI24X_I18N.isZh() ? zh : en;
      }
      if (window.AI24X_API && typeof window.AI24X_API.isZhUi === "function") {
        return window.AI24X_API.isZhUi() ? zh : en;
      }
    } catch (e) {}
    return en;
  }

  function fmtInt(v) {
    var n = Number(v);
    if (!isFinite(n)) return "--";
    return String(Math.round(n));
  }

  /** 用户端只展示品牌档，不暴露上游厂商/型号 */
  function brandModelLabel(requested, layer, upstreamModel) {
    var req = String(requested || "").trim().toLowerCase();
    if (req.indexOf("vip:") === 0) req = "vip-" + req.slice(4);
    if (req.indexOf("vip-") === 0) return req.slice(0, 64);
    var pub = String(upstreamModel || "").trim().toLowerCase();
    if (pub.indexOf("vip:") === 0) pub = "vip-" + pub.slice(4);
    if (pub.indexOf("vip-") === 0) return pub.slice(0, 64);
    if (
      req === "flash" ||
      req === "pro" ||
      req === "ultra" ||
      req === "auto" ||
      req === "free" ||
      req === "shared"
    ) {
      if (req === "free") return "auto";
      return req;
    }
    if (
      pub === "flash" ||
      pub === "pro" ||
      pub === "ultra" ||
      pub === "auto" ||
      pub === "shared"
    ) {
      return pub;
    }
    var ly = String(layer || "").toUpperCase();
    if (ly === "VIP") return req || pub || "vip_pick";
    if (ly === "L1") return "flash";
    if (ly === "L2") return "pro";
    if (ly === "L3") return "ultra";
    if (ly === "L0" || ly === "QI") return "auto";
    var m = pub;
    if (/v4-pro|deepseek-r1|reasoner|mimo-v2\.5-pro/.test(m)) return "pro";
    if (/flash|deepseek-chat|mimo|gpt-5-mini|gpt-4o-mini|turbo|qwen/.test(m)) return "flash";
    return "auto";
  }

  function formatChatOut(r, requested) {
    if (!r || typeof r !== "object") return String(r || "");
    // remaining_quota 为扣费后快照；勿再用 attribution 里的预扣 remain（会偏大）
    var remaining = r.remaining_quota;
    return JSON.stringify(
      {
        reply: r.response,
        tier: brandModelLabel(requested, r.layer, r.model),
        tokens: r.token_count,
        remaining: remaining,
        request_id: r.request_id,
      },
      null,
      2
    );
  }

  function labelEntryType(t) {
    if (!AI24X_API.isZhUi()) {
      var en = {
        consume: "Usage",
        topup: "Top-up",
        bonus: "Bonus",
        referral: "Referral",
        expire: "Expired",
      };
      return en[t] || t || "";
    }
    var m = {
      consume: "消耗",
      topup: "充值",
      bonus: "赠送",
      referral: "邀请奖励",
      expire: "过期核销",
    };
    return m[t] || t || "";
  }

  function labelPlanId(plan) {
    var m = {
      free: "免费档",
      FREE: "免费档",
      vip: "Token VIP",
      VIP: "Token VIP",
      token_pack_10k: "入门包",
      token_pack_100k: "开发包",
      token_vip_month: "Pro 月卡",
      token_vip_month_50w: "VIP名模包",
    };
    if (m[plan]) return m[plan];
    return plan || "--";
  }

  function labelPlanIdEn(plan) {
    var m = {
      free: "Free",
      FREE: "Free",
      vip: "Token VIP",
      VIP: "Token VIP",
      token_pack_10k: "Starter",
      token_pack_100k: "Builder",
      token_vip_month: "Pro Pass",
      token_vip_month_50w: "Scale",
    };
    return m[plan] || plan || "--";
  }

  function labelPlanForUi(plan) {
    return AI24X_API.isZhUi() ? labelPlanId(plan) : labelPlanIdEn(plan);
  }

  function labelOrderStatus(s) {
    if (!AI24X_API.isZhUi()) {
      var en = { pending: "Pending", paid: "Paid", failed: "Failed" };
      return en[s] || s || "";
    }
    var m = { pending: "待支付", paid: "已支付", failed: "失败" };
    return m[s] || s || "";
  }

  function labelChannel(c) {
    if (!AI24X_API.isZhUi()) {
      var en = { wechat: "WeChat", alipay: "Alipay", paypal: "PayPal", mock: "Mock" };
      return en[c] || c || "";
    }
    var m = { wechat: "微信", alipay: "支付宝", paypal: "PayPal", mock: "模拟" };
    return m[c] || c || "";
  }

  function humanizeLedgerNote(note) {
    var n = String(note || "");
    if (!n) return "";
    var zh = AI24X_API.isZhUi();
    if (/^signup_welcome$/i.test(n)) {
      return zh ? "注册欢迎礼" : "Signup welcome bonus";
    }
    if (/^free_shared\b/i.test(n) || /^shared\b/i.test(n)) {
      return zh ? "免费共享调用" : "Free shared usage";
    }
    if (/^free_shared\s+\d{4}-\d{2}-\d{2}/i.test(n)) {
      return zh ? "免费共享调用" : "Free shared usage";
    }
    if (/^invite_register_bonus\s+referee=/i.test(n)) {
      return zh ? "邀请注册奖励（邀请人侧）" : "Invite bonus (referrer)";
    }
    if (/^invite_register_bonus\s+referrer=/i.test(n)) {
      return zh ? "邀请注册奖励（新用户侧）" : "Invite bonus (new user)";
    }
    if (/^vip\s*日额度/i.test(n) || /^VIP 日额度/i.test(n)) {
      return zh ? n : n.replace(/vip\s*日额度|VIP 日额度/gi, "VIP daily quota");
    }
    if (/^chat\/run$/i.test(n)) return zh ? "API 调用" : "API call";
    if (/^lot_expire\b/i.test(n)) return zh ? "额度到期自动核销" : "Credit lot expired";
    if (/^(wechat|alipay|paypal|mock|paypal_capture|paypal_webhook):/i.test(n)) {
      var parts = n.split(":");
      var ch0 = String(parts[0] || "").replace(/_capture|_webhook/i, "");
      return (
        labelChannel(ch0) +
        (zh ? "支付到账" : " payment") +
        (parts[2] ? " · " + labelPlanForUi(parts[2]) : "")
      );
    }
    if (/vip_daily_bonus/i.test(n)) {
      return n.replace(/vip_daily_bonus/gi, zh ? "每日赠送额度" : "daily bonus");
    }
    return n;
  }

  /** 就近提示：试调用用面板内卡片；其它优先主区，避免英雄区顶部看不见 */
  function msgBox(preferId) {
    if (preferId && $(preferId)) return $(preferId);
    var active = document.querySelector(".console-panel.is-active");
    if (active) {
      var local = active.querySelector("[data-console-msg]");
      if (local) return local;
    }
    return $("consoleMainMsg") || $("consoleMsg");
  }

  var _toastTimer = null;
  var _payModalSession = 0;
  var _pendingCheckoutWin = null;
  var _payDeepLinkDone = false;

  function showToast(text, ok) {
    var msg = String(text || "").replace(/<[^>]+>/g, "").trim();
    if (!msg) return;
    var t = document.getElementById("ai24x-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "ai24x-toast";
      t.setAttribute("role", "status");
      t.setAttribute("aria-live", "polite");
      document.body.appendChild(t);
    }
    t.className = "ai24x-toast " + (ok ? "is-ok" : "is-error");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(function () {
      t.hidden = true;
    }, ok ? 5600 : 9000);
  }

  /** 页内卡片提示（优先）；toastOnly=true 时仅浮层。默认不再双重弹出。 */
  function showMsg(el, text, ok, opts) {
    opts = opts || {};
    var msg = String(text || "").replace(/<[^>]+>/g, "").trim();
    if (!msg) return;
    var box = el || msgBox();
    if (box && !opts.toastOnly) {
      box.innerHTML =
        '<div class="alert console-inline-alert ' +
        (ok ? "alert-success" : "alert-error") +
        '" role="status">' +
        msg +
        ' <button type="button" class="btn btn-sm console-alert-dismiss" aria-label="OK">OK</button></div>';
      var btn = box.querySelector(".console-alert-dismiss");
      if (btn) {
        btn.addEventListener("click", function () {
          box.innerHTML = "";
        });
      }
      try {
        box.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } catch (eScroll) {}
    }
    if (opts.toast || opts.toastOnly || (!box && !opts.noToast)) {
      showToast(msg, ok);
    }
  }

  function requireLogin() {
    if (!AI24X_API.getAuthToken()) {
      location.href = "login.html?next=" + encodeURIComponent("console.html");
      return false;
    }
    return true;
  }

  function defaultKeyName() {
    if (window.AI24X_I18N && AI24X_I18N.t) {
      var v = AI24X_I18N.t("page.console.modal.keyNameDefault");
      if (v && v !== "page.console.modal.keyNameDefault") return v;
    }
    return tr("默认密钥", "Default key");
  }

  function formatKeyDate(iso) {
    if (!iso) return tr("从未", "Never");
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso).slice(0, 10);
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    var hh = String(d.getHours()).padStart(2, "0");
    var mm = String(d.getMinutes()).padStart(2, "0");
    return y + "-" + m + "-" + day + " " + hh + ":" + mm;
  }

  function iconBtn(kind, label) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-icon";
    btn.title = label;
    btn.setAttribute("aria-label", label);
    if (kind === "edit") {
      btn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';
    } else if (kind === "delete") {
      btn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>';
    }
    return btn;
  }

  function renderKeys(keys) {
    var box = $("keysList");
    if (!box) return;
    box.innerHTML = "";
    if (!keys || !keys.length) {
      var empty = document.createElement("tr");
      empty.className = "keys-empty";
      empty.innerHTML =
        '<td colspan="5">' +
        tr("暂无密钥，点击右上角创建。", "No keys yet — create one above.") +
        "</td>";
      box.appendChild(empty);
      return;
    }
    keys.forEach(function (k) {
      var trEl = document.createElement("tr");
      var tdName = document.createElement("td");
      tdName.className = "keys-name";
      tdName.textContent = k.name || tr("密钥", "Key");

      var tdKey = document.createElement("td");
      tdKey.className = "keys-prefix mono";
      tdKey.textContent = (k.key_prefix || "sk-…") + "…";

      var tdCreated = document.createElement("td");
      tdCreated.className = "keys-date";
      tdCreated.textContent = formatKeyDate(k.created_at);

      var tdUsed = document.createElement("td");
      tdUsed.className = "keys-date";
      tdUsed.textContent = k.last_used_at
        ? formatKeyDate(k.last_used_at)
        : tr("从未", "Never");

      var tdAct = document.createElement("td");
      tdAct.className = "keys-actions";
      var btnEdit = iconBtn("edit", tr("修改名称", "Rename"));
      btnEdit.addEventListener("click", function () {
        var next = window.prompt(
          tr("新的密钥名称", "New key name"),
          k.name || ""
        );
        if (next == null) return;
        next = String(next).trim();
        if (!next) {
          showMsg(msgBox(), tr("名称不能为空", "Name cannot be empty"), false);
          return;
        }
        if (next === (k.name || "")) return;
        AI24X_API.keysRename(k.id, { name: next })
          .then(refreshAll)
          .catch(function (e) {
            showMsg(msgBox(), e.message || tr("改名失败", "Rename failed"), false);
          });
      });
      var btnDel = iconBtn("delete", tr("删除", "Delete"));
      btnDel.classList.add("btn-icon-danger");
      btnDel.addEventListener("click", function () {
        if (!confirm(tr("确认停用该 Key？", "Disable this key?"))) return;
        AI24X_API.keysDelete(k.id)
          .then(refreshAll)
          .catch(function (e) {
            showMsg(msgBox(), e.message || tr("删除失败", "Delete failed"), false);
          });
      });
      tdAct.appendChild(btnEdit);
      tdAct.appendChild(btnDel);

      trEl.appendChild(tdName);
      trEl.appendChild(tdKey);
      trEl.appendChild(tdCreated);
      trEl.appendChild(tdUsed);
      trEl.appendChild(tdAct);
      box.appendChild(trEl);
    });
  }

  function renderPlans(data) {
    var box = $("plansList");
    if (!box) return;
    if (data) window.__tokenPlansPayload = data;
    data = data || window.__tokenPlansPayload;
    if (!data) return;
    box.innerHTML = "";
    var plans = (data && data.plans) || [];
    var pay = (data && data.pay) || {};
    window.__tokenPay = pay;
    var zh = AI24X_API.isZhUi();
    var hint = $("payHint");
    if (hint) {
      if (zh) {
        if (pay.enabled && (pay.wechat_ready || pay.alipay_ready || pay.paypal_ready)) {
          var ch = [];
          if (pay.wechat_ready) ch.push("微信");
          if (pay.alipay_ready) ch.push("支付宝");
          if (pay.paypal_ready) ch.push("PayPal");
          hint.textContent =
            "选择套餐后可用 " +
            ch.join(" / ") +
            " 支付。" +
            (pay.mock_allowed ? " 也可使用「模拟到账」。" : "");
        } else if (pay.wechat_configured || pay.alipay_configured || pay.paypal_configured) {
          hint.textContent = "在线支付准备中" + (pay.mock_allowed ? "，可用「模拟到账」。" : "。");
        } else if (pay.mock_allowed) {
          hint.textContent = "可用「模拟到账」完成体验充值。";
        } else {
          hint.textContent = "在线支付暂未开放。";
        }
      } else {
        if (pay.enabled && (pay.wechat_ready || pay.alipay_ready || pay.paypal_ready)) {
          var enCh = [];
          if (pay.wechat_ready) enCh.push("WeChat");
          if (pay.alipay_ready) enCh.push("Alipay");
          if (pay.paypal_ready) enCh.push("PayPal");
          hint.textContent =
            "Choose a plan and pay with " +
            enCh.join(" / ") +
            "." +
            (pay.mock_allowed ? " Mock top-up is also available." : "");
        } else {
          hint.textContent = pay.mock_allowed
            ? "Online pay is not open yet. Mock top-up is available."
            : "Online pay is not open yet.";
        }
      }
    }
    if (!plans.length) {
      box.innerHTML = '<p class="sub">' + tr("暂无套餐", "No plans") + "</p>";
      return;
    }

    function payIconSvg(channel) {
      if (channel === "wechat") {
        return (
          '<svg class="pay-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path fill="#07C160" d="M9.5 4C5.9 4 3 6.5 3 9.6c0 1.8 1 3.3 2.6 4.4L5 16.2l2.4-1.2c.7.2 1.4.3 2.1.3.2 0 .4 0 .6 0-.2-.5-.3-1-.3-1.6 0-3.2 3.1-5.8 6.9-5.8.2 0 .4 0 .6.1C16.4 5.3 13.2 4 9.5 4zm-2.3 3.1c.5 0 .9.4.9.9s-.4.9-.9.9-.9-.4-.9-.9.4-.9.9-.9zm4.6 0c.5 0 .9.4.9.9s-.4.9-.9.9-.9-.4-.9-.9.4-.9.9-.9zM16.8 9c-3.1 0-5.6 2.1-5.6 4.7s2.5 4.7 5.6 4.7c.6 0 1.2-.1 1.8-.3l1.9.9-.5-1.7c1.2-.9 2-2.2 2-3.6C21.9 11.1 19.5 9 16.8 9zm-1.9 3.1c.3 0 .6.3.6.6s-.3.6-.6.6-.6-.3-.6-.6.3-.6.6-.6zm3.8 0c.3 0 .6.3.6.6s-.3.6-.6.6-.6-.3-.6-.6.3-.6.6-.6z"/></svg>'
        );
      }
      if (channel === "alipay") {
        return (
          '<svg class="pay-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path fill="#1677FF" d="M21.5 12.2c0-4.6-3.4-8.2-8.3-8.2H5.2v16h8.1c4.8 0 8.2-3.5 8.2-7.8zm-9.9 3.3c-2.2 0-3.4-1-3.4-2.5 0-1.6 1.3-2.5 3.5-2.5.6 0 1.2.1 1.8.2-.3.6-.6 1.3-.9 2.1H10c-.5 0-.8.2-.8.6 0 .4.4.7 1.1.7.7 0 1.4-.2 2-.5.2.6.4 1.1.5 1.5-.9.3-1.8.4-2.7.4zm5.7-1.1c-.4.7-.9 1.4-1.5 2-.2-.5-.4-1.1-.5-1.7.7-.1 1.4-.2 2-.3zm1.3-2.5c-.9.2-1.9.4-2.9.8.3-.8.6-1.5 1-2.1.7.3 1.3.8 1.9 1.3z"/></svg>'
        );
      }
      if (channel === "paypal") {
        return (
          '<svg class="pay-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path fill="#003087" d="M7.2 20.5h1.7l.5-3.1h1.7c3.3 0 5.5-1.4 6.1-4.3.1-.5.1-.9.1-1.2 0-.2 0-.4-.1-.6H19l.1-.5c.4-2.5-.9-4.2-3.8-4.2H9.2L7.2 20.5zm4.2-11.5h1.7c1.3 0 2 .5 1.8 1.7-.2 1.4-1.2 1.7-2.5 1.7h-1.5l.5-3.4z"/>' +
          '<path fill="#009CDE" d="M9.5 21.5h1.7l.4-2.5H13c2.7 0 4.4-1.1 4.9-3.5.1-.4.1-.7.1-1 0-.1 0-.3 0-.4h1.5l.1-.4c.3-2-.7-3.4-3.1-3.4h-4.3l-1.9 11.2h1.7l.5 3.1h1.4c1.1 0 1.7.4 1.5 1.4-.2 1.1-1 1.4-2.1 1.4H10l.5 3.3z"/></svg>'
        );
      }
      return "";
    }

    var wrap = document.createElement("div");
    wrap.className = "plan-compare-wrap";
    var table = document.createElement("table");
    table.className = "plan-compare";
    table.innerHTML =
      "<thead><tr>" +
      "<th>" +
      tr("套餐", "Plan") +
      "</th><th>" +
      tr("价格", "Price") +
      "</th><th>" +
      tr("额", "Value") +
      "</th><th>" +
      tr("点名模", "Name models") +
      "</th><th>" +
      tr("适合", "Best for") +
      "</th><th>" +
      tr("购买", "Buy") +
      "</th></tr></thead>";
    var tbody = document.createElement("tbody");
    plans.forEach(function (p) {
      var caps = AI24X_API.planCaps(p);
      var trEl = document.createElement("tr");
      if (p.recommended) trEl.className = "is-recommended";
      if (p.plan) trEl.setAttribute("data-plan", String(p.plan));
      var nameCell = document.createElement("td");
      nameCell.innerHTML =
        "<strong>" +
        (AI24X_API.planTitle(p) || "") +
        "</strong>" +
        (p.recommended
          ? '<span class="plan-rec">' + tr("推荐", "Rec") + "</span>"
          : "");
      trEl.appendChild(nameCell);
      function tdText(t) {
        var td = document.createElement("td");
        td.textContent = t;
        return td;
      }
      trEl.appendChild(tdText(AI24X_API.planPriceLabel(p)));
      // Show flash-equivalent value: $X = ~Y flash calls
      var tokens = Number(p.credit_tokens || 0);
      var flashVal = tokens > 0 ? ("≈ " + AI24X_API.planCreditsShort(p) + " flash") : (p.price_usd ? "$" + p.price_usd : "—");
      var td = document.createElement("td");
      td.textContent = flashVal;
      trEl.appendChild(td);
      trEl.appendChild(tdText(AI24X_API.planYesNo(!!caps.vip)));
      trEl.appendChild(tdText(AI24X_API.planOneLiner(p) || "—"));
      var payTd = document.createElement("td");
      payTd.className = "plan-compare-pay";
      var actions = document.createElement("div");
      actions.className = "card-actions plan-compare-actions";
      function addBtn(label, cls, channel) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = cls + (channel !== "mock" ? " btn-pay" : "");
        btn.innerHTML = (channel !== "mock" ? payIconSvg(channel) : "") + "<span>" + label + "</span>";
        btn.setAttribute("data-pay-channel", channel);
        btn.addEventListener("click", function () {
          buyPlan(p.plan, channel, p);
        });
        actions.appendChild(btn);
      }
      if (pay.wechat_ready) addBtn(tr("微信", "WeChat"), "btn", "wechat");
      if (pay.alipay_ready) addBtn(tr("支付宝", "Alipay"), "btn", "alipay");
      if (pay.paypal_ready) addBtn("PayPal", "btn btn-primary", "paypal");
      if (pay.mock_allowed) addBtn(tr("模拟", "Mock"), "btn", "mock");
      if (
        !pay.wechat_ready &&
        !pay.alipay_ready &&
        !pay.paypal_ready &&
        !pay.mock_allowed
      ) {
        var disabled = document.createElement("button");
        disabled.type = "button";
        disabled.className = "btn";
        disabled.disabled = true;
        disabled.textContent = tr("暂不可买", "Unavailable");
        actions.appendChild(disabled);
      }
      payTd.appendChild(actions);
      trEl.appendChild(payTd);
      tbody.appendChild(trEl);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    var tip = document.createElement("p");
    tip.className = "sub";
    tip.style.marginTop = "10px";
    tip.textContent = tr(
      "Flash $0.45/百万 · Pro $1.35/百万 · 自定义充值即将开放。Scale = 可点名模。",
      "Flash $0.45/M · Pro $1.35/M · Custom top-up coming soon. Scale = named-model access."
    );
    wrap.appendChild(tip);
    box.appendChild(wrap);
    tryApplyPayDeepLink();
  }

  function clearPayDeepLinkFromUrl() {
    try {
      var u = new URL(window.location.href);
      if (!u.searchParams.has("plan") && !u.searchParams.has("pay")) return;
      u.searchParams.delete("plan");
      u.searchParams.delete("pay");
      var q = u.searchParams.toString();
      history.replaceState({}, "", u.pathname + (q ? "?" + q : "") + u.hash);
    } catch (e) {}
  }

  function tryApplyPayDeepLink() {
    try {
      if (_payDeepLinkDone) return;
      var qs = new URLSearchParams(window.location.search || "");
      var wantPlan = (qs.get("plan") || "").trim();
      var wantPay = (qs.get("pay") || "").trim().toLowerCase();
      if (!wantPlan && !wantPay) return;
      /* 只引导一次：清掉 URL，禁止自动 click（否则无用户手势→弹窗被拦→刷新套餐又自动点→死循环） */
      _payDeepLinkDone = true;
      clearPayDeepLinkFromUrl();
      var box = $("plansList");
      if (!box) return;
      var card = null;
      if (wantPlan) {
        card = box.querySelector('[data-plan="' + wantPlan.replace(/"/g, "") + '"]');
      }
      if (!card) card = box.querySelector("tr[data-plan], .card");
      var plansAnchor = $("token-plans");
      if (plansAnchor) {
        try {
          plansAnchor.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (e0) {}
      }
      if (card) {
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        card.style.outline = "2px solid #0070ba";
        card.style.outlineOffset = "2px";
      }
      var chBtn =
        wantPay && card
          ? card.querySelector('button[data-pay-channel="' + wantPay + '"]')
          : null;
      if (wantPay && chBtn && !chBtn.disabled) {
        var guide = tr(
          "已从价格页带入套餐，请点击下方支付按钮完成付款。",
          "Plan selected from pricing — tap a pay button below to continue."
        );
        showMsg(msgBox(), guide, true);
      } else if (wantPay || wantPlan) {
        var guide2 = tr(
          "请在下方套餐选择支付方式。",
          "Choose a payment method on the plan card below."
        );
        showMsg(msgBox(), guide2, true);
      }
    } catch (e) {}
  }

  function openPayModal(title, sub) {
    var root = $("modal-pay");
    if (!root) return;
    $("modal-pay-title").textContent = title || tr("支付", "Pay");
    $("modal-pay-sub").textContent = sub || "";
    $("modal-pay-channels").innerHTML = "";
    $("modal-pay-result").style.display = "none";
    $("modal-pay-qr").style.display = "none";
    $("modal-pay-url").style.display = "none";
    var hintEl = $("modal-pay-result-hint");
    if (hintEl) {
      hintEl.className = "ui-modal-sub";
      hintEl.textContent = "";
    }
    root.classList.add("is-open");
    root.setAttribute("aria-hidden", "false");
  }

  function closePayModal() {
    _payModalSession += 1;
    closeCheckoutWin(_pendingCheckoutWin);
    _pendingCheckoutWin = null;
    var root = $("modal-pay");
    if (!root) return;
    root.classList.remove("is-open");
    root.setAttribute("aria-hidden", "true");
  }

  function showPayResult(opts) {
    opts = opts || {};
    $("modal-pay-result").style.display = "block";
    var hintEl = $("modal-pay-result-hint");
    if (hintEl) {
      hintEl.className = opts.isError ? "alert alert-error" : "ui-modal-sub";
      hintEl.style.marginTop = opts.isError ? "0" : "";
      hintEl.textContent = opts.hint || "";
    }
    var img = $("modal-pay-qr");
    var urlBox = $("modal-pay-url");
    var openLink = $("modal-pay-open-link");
    if (opts.qrData) {
      img.style.display = "inline-block";
      img.src =
        "https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=" +
        encodeURIComponent(opts.qrData);
    } else {
      img.style.display = "none";
    }
    if (opts.urlText && !/^https?:\/\//i.test(String(opts.urlText))) {
      urlBox.style.display = "block";
      urlBox.textContent = opts.urlText;
    } else {
      urlBox.style.display = "none";
      urlBox.textContent = "";
    }
    if (openLink) {
      if (opts.openUrl) {
        openLink.href = opts.openUrl;
        openLink.style.display = "inline-block";
        openLink.textContent =
          opts.openLabel ||
          tr("在新窗口打开", "Open in new window");
      } else {
        openLink.removeAttribute("href");
        openLink.style.display = "none";
      }
    }
  }

  /** 点击当下同步开窗，避免异步回调后被浏览器拦截；绝不 location 顶掉控制台 */
  function openPayInNewWindow(payUrl) {
    if (!payUrl) return false;
    try {
      var w = window.open(payUrl, "_blank", "noopener,noreferrer");
      if (w) {
        try {
          w.opener = null;
        } catch (e) {}
        return true;
      }
    } catch (e) {}
    return false;
  }
  /** @deprecated 兼容旧名 */
  function openAlipayInNewWindow(payUrl) {
    return openPayInNewWindow(payUrl);
  }

  function openCheckoutPlaceholder(labelZh, labelEn) {
    var win = null;
    try {
      win = window.open("about:blank", "_blank");
      if (win) {
        try {
          win.document.write(
            "<!doctype html><title>Checkout</title><p style='font:14px/1.5 system-ui,sans-serif;padding:24px;color:#334'>" +
              tr(labelZh, labelEn) +
              "</p>"
          );
        } catch (e) {}
      }
    } catch (e) {
      win = null;
    }
    return win;
  }

  function navigateCheckoutWin(win, payUrl) {
    if (win && !win.closed && payUrl) {
      try {
        win.location.href = payUrl;
        return true;
      } catch (e) {}
    }
    return openPayInNewWindow(payUrl);
  }

  function closeCheckoutWin(win) {
    if (win && !win.closed) {
      try {
        win.close();
      } catch (e) {}
    }
  }

  var _fulfillPollTimer = null;
  var _lastPayPlanId = null;
  /** 支付后主动查单补履约（异步 notify 未到时的兜底） */
  function startFulfillPoll(outTradeNo, channel, planId) {
    if (!outTradeNo) return;
    if (planId) _lastPayPlanId = planId;
    if (_fulfillPollTimer) {
      clearInterval(_fulfillPollTimer);
      _fulfillPollTimer = null;
    }
    var tries = 0;
    var maxTries = 40; // ~2 分钟（每 3 秒）
    _fulfillPollTimer = setInterval(function () {
      tries += 1;
      if (tries > maxTries) {
        clearInterval(_fulfillPollTimer);
        _fulfillPollTimer = null;
        return;
      }
      AI24X_API.billingQueryFulfill(outTradeNo, channel || "wechat")
        .then(function (r) {
          if (r && r.ok) {
            clearInterval(_fulfillPollTimer);
            _fulfillPollTimer = null;
            showMsg(
              msgBox(),
              AI24X_API.planFulfillMessage(_lastPayPlanId || planId, outTradeNo),
              true
            );
            try {
              closePayModal();
            } catch (e) {}
            return refreshAll();
          }
        })
        .catch(function () {
          /* 未支付成功时接口可能 4xx，继续轮询 */
        });
    }, 3000);
  }

  function buyPlan(planId, channel, planMeta) {
    var pay = window.__tokenPay || {};
    var price = AI24X_API.planPriceLabel(planMeta) || "";
    var planTitle = AI24X_API.planTitle(planMeta) || planId;
    var session = ++_payModalSession;
    _lastPayPlanId = planId || null;

    if (channel === "mock" || (!pay.wechat_ready && !pay.alipay_ready && pay.mock_allowed)) {
      showMsg(msgBox(), tr("正在创建模拟订单…", "Creating mock order…"), true);
      AI24X_API.billingWechatNative(planId)
        .then(function (r) {
          showMsg(
            msgBox(),
            tr(
              "已创建 " + (r && r.out_trade_no) + "。请在「我的订单」点「模拟到账」。",
              "Created " + (r && r.out_trade_no) + ". Use Mock pay under My orders."
            ),
            true
          );
          return refreshAll();
        })
        .catch(function (e) {
          showMsg(msgBox(), e.message || tr("下单失败", "Order failed"), false);
        });
      return;
    }

    var checkoutWin = null;
    if (channel === "alipay") {
      checkoutWin = openCheckoutPlaceholder(
        "正在打开支付宝，请稍候…",
        "Opening Alipay…"
      );
    } else if (channel === "paypal") {
      checkoutWin = openCheckoutPlaceholder(
        "正在创建 PayPal 订单，请稍候…（勿关闭此窗口）",
        "Creating PayPal order… Keep this tab open."
      );
      showMsg(
        msgBox(),
        tr(
          "正在创建 PayPal 订单，请稍候…（勿关闭此窗口）",
          "Creating PayPal order… Keep this tab open."
        ),
        true
      );
    }
    _pendingCheckoutWin = checkoutWin;

    var payBusyHint =
      channel === "wechat"
        ? tr("正在拉起微信扫码…", "Preparing WeChat QR…")
        : channel === "alipay"
          ? tr("将在新窗口打开支付宝；本页控制台保留。", "Alipay opens in a new window; this console stays.")
          : channel === "paypal"
            ? tr(
                "正在创建 PayPal 订单，请稍候；若未弹出窗口，用下方按钮打开。",
                "Creating PayPal order… If no window opens, use the button below."
              )
            : tr("请选择支付方式", "Choose a payment method");
    openPayModal(planTitle + (price ? " · " + price : ""), payBusyHint);

    var req =
      channel === "alipay"
        ? AI24X_API.billingAlipayWap(planId)
        : channel === "paypal"
          ? AI24X_API.billingPaypalOrder(planId)
          : AI24X_API.billingWechatNative(planId);

    req
      .then(function (r) {
        if (session !== _payModalSession) {
          closeCheckoutWin(checkoutWin);
          return;
        }
        if (_pendingCheckoutWin === checkoutWin) _pendingCheckoutWin = null;
        if (r && r.mock) {
          closeCheckoutWin(checkoutWin);
          showPayResult({
            hint: tr(
              "当前仍为模拟单（" +
                (r.out_trade_no || "") +
                "）。请关闭后在订单列表点「模拟到账」。",
              "This is still a mock order (" +
                (r.out_trade_no || "") +
                "). Close and tap Mock pay in the order list."
            ),
          });
          return refreshAll();
        }
        if (channel === "wechat" && r && r.code_url) {
          showPayResult({
            hint: tr(
              "请用微信扫码支付。付完后本页会自动查单到账；也可到「我的订单」点「确认到账」。单号：" +
                (r.out_trade_no || ""),
              "Scan with WeChat. This page auto-confirms after pay; or tap Confirm under My orders. Order: " +
                (r.out_trade_no || "")
            ),
            qrData: r.code_url,
          });
          startFulfillPoll(r.out_trade_no, "wechat", planId);
        } else if (channel === "alipay" && r && r.pay_url) {
          var opened = navigateCheckoutWin(checkoutWin, r.pay_url);
          showPayResult({
            hint:
              (opened
                ? tr(
                    "已在新窗口打开支付宝，请在新窗口完成付款。",
                    "Alipay opened in a new window — finish payment there."
                  )
                : tr(
                    "浏览器拦截了新窗口时，请点下方按钮打开支付宝。",
                    "If the browser blocked the window, open Alipay with the button below."
                  )) +
              tr(
                " 付完后本页会自动查单到账；也可点「确认到账」。单号：",
                " This page auto-confirms after pay; or tap Confirm. Order: "
              ) +
              (r.out_trade_no || ""),
            openUrl: r.pay_url,
            openLabel: tr("在新窗口打开支付宝", "Open Alipay in a new window"),
          });
          startFulfillPoll(r.out_trade_no, "alipay", planId);
        } else if (channel === "paypal" && r && r.pay_url) {
          var ppOpened = navigateCheckoutWin(checkoutWin, r.pay_url);
          showPayResult({
            hint:
              (ppOpened
                ? tr("已打开 PayPal，请在新窗口完成付款。", "PayPal opened — finish payment there.")
                : tr(
                    "浏览器拦截了新窗口时，请点下方按钮打开 PayPal。",
                    "If the browser blocked the window, open PayPal with the button below."
                  )) +
              tr(
                " 付完返回本页会自动确认到账。单号：",
                " After return, this page auto-confirms. Order: "
              ) +
              (r.out_trade_no || "") +
              (r.amount_usd ? " · $" + r.amount_usd : ""),
            openUrl: r.pay_url,
            openLabel: tr("打开 PayPal", "Open PayPal"),
          });
          startFulfillPoll(r.out_trade_no, "paypal", planId);
        } else {
          closeCheckoutWin(checkoutWin);
          var badHint = tr(
            "下单未完成，请稍后重试或换一种支付方式。单号：" +
              ((r && r.out_trade_no) || ""),
            "Could not start checkout. Try again or another method. Order: " +
              ((r && r.out_trade_no) || "")
          );
          // 错误只显示在支付卡片内，避免与页面顶部 consoleMsg 重复
          var topMsg0 = msgBox();
          if (topMsg0) topMsg0.innerHTML = "";
          showPayResult({ isError: true, hint: badHint });
        }
        return refreshAll();
      })
      .catch(function (e) {
        if (session !== _payModalSession) {
          closeCheckoutWin(checkoutWin);
          return;
        }
        if (_pendingCheckoutWin === checkoutWin) _pendingCheckoutWin = null;
        closeCheckoutWin(checkoutWin);
        var errText = e.message || tr("下单失败", "Order failed");
        // 限购/下单失败等：只留支付弹层提示，清掉页面顶部以免重复
        var topMsg = msgBox();
        if (topMsg) topMsg.innerHTML = "";
        showPayResult({ isError: true, hint: errText });
      });
  }

  function renderOrders(rows) {
    var box = $("ordersList");
    if (!box) return;
    box.innerHTML = "";
    if (!rows || !rows.length) {
      box.innerHTML =
        '<li class="list-item"><span>' +
        tr("暂无订单", "No orders") +
        "</span><span></span></li>";
      return;
    }
    rows.forEach(function (o) {
      var li = document.createElement("li");
      li.className = "list-item";
      var left = document.createElement("span");
      var amt = ((Number(o.amount_fen) || 0) / 100).toFixed(2);
      left.textContent =
        labelPlanForUi(o.plan) +
        " · " +
        (AI24X_API.isZhUi() ? "¥" + amt : "CNY " + amt) +
        " · " +
        labelOrderStatus(o.status) +
        (o.channel ? " · " + labelChannel(o.channel) : "") +
        (o.out_trade_no ? " · " + o.out_trade_no : "");
      var right = document.createElement("span");
      if (o.status === "pending") {
        var payCfg = window.__tokenPay || {};
        if (payCfg.mock_allowed) {
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "btn btn-primary";
          btn.textContent = tr("模拟到账", "Mock pay");
          btn.addEventListener("click", function () {
            AI24X_API.billingMockFulfill(o.out_trade_no)
              .then(function () {
                showMsg(msgBox(), tr("模拟到账成功", "Mock pay OK"), true);
                return refreshAll();
              })
              .catch(function (e) {
                showMsg(msgBox(), e.message || tr("模拟失败", "Mock failed"), false);
              });
          });
          right.appendChild(btn);
        }
        var btnQ = document.createElement("button");
        btnQ.type = "button";
        btnQ.className = payCfg.mock_allowed ? "btn" : "btn btn-primary";
        if (payCfg.mock_allowed) btnQ.style.marginLeft = "6px";
        btnQ.textContent = tr("确认到账", "Confirm");
        btnQ.addEventListener("click", function () {
          AI24X_API.billingQueryFulfill(o.out_trade_no, o.channel || "wechat")
            .then(function (r) {
              showMsg(
                msgBox(),
                r && r.ok
                  ? AI24X_API.planFulfillMessage(o.plan || _lastPayPlanId, o.out_trade_no)
                  : tr("尚未支付成功或查单未完成", "Not paid yet / still pending"),
                !!(r && r.ok)
              );
              return refreshAll();
            })
            .catch(function (e) {
              showMsg(msgBox(), e.message || tr("查单失败", "Query failed"), false);
            });
        });
        right.appendChild(btnQ);
      } else {
        right.textContent = o.transaction_id || o.out_trade_no || "";
      }
      li.appendChild(left);
      li.appendChild(right);
      box.appendChild(li);
    });
  }

  function renderUsage(rows) {
    var box = $("activityList");
    if (!box) return;
    box.innerHTML = "";
    if (!rows || !rows.length) {
      box.innerHTML =
        '<li class="list-item"><span>' +
        tr("暂无流水", "No ledger entries") +
        "</span><span></span></li>";
      return;
    }
    rows.slice(0, 12).forEach(function (r) {
      var li = document.createElement("li");
      li.className = "list-item";
      var left = document.createElement("span");
      left.textContent =
        labelEntryType(r.entry_type) +
        (r.model ? " · " + brandModelLabel("", "", r.model) : "") +
        (r.note ? " · " + humanizeLedgerNote(r.note) : "");
      var right = document.createElement("span");
      right.textContent = (r.amount > 0 ? "+" : "") + String(r.amount);
      li.appendChild(left);
      li.appendChild(right);
      box.appendChild(li);
    });
  }

  function fillVipPickOptions(isVip) {
    var sel = $("chat-model");
    if (!sel || !AI24X_API.listModels) return;
    var prev = String(sel.value || "");
    AI24X_API.listModels()
      .then(function (m) {
        var picks = (m && m.vip_picks) || [];
        // 清掉旧 vip 选项，保留基础档（并记住当前选中，避免刷新后掉回 auto）
        var keep = { auto: 1, flash: 1, pro: 1, ultra: 1, shared: 1 };
        Array.prototype.slice.call(sel.options).forEach(function (opt) {
          if (!keep[opt.value]) sel.removeChild(opt);
        });
        picks.forEach(function (p) {
          if (!p || !p.id) return;
          var opt = document.createElement("option");
          opt.value = p.id;
          var lock = p.locked ? tr("（需会员）", " (VIP)") : "";
          var mult = p.billing_mult ? " ×" + p.billing_mult : "";
          var zhUi = AI24X_API.isZhUi();
          var est = "";
          if (p.est_cny_per_m != null || p.est_usd_per_m != null) {
            est = zhUi
              ? " · 约¥" + (p.est_cny_per_m != null ? p.est_cny_per_m : "—") + "/百万"
              : " · ~$" + (p.est_usd_per_m != null ? p.est_usd_per_m : "—") + "/1M";
          }
          var title =
            !zhUi && p.title_en ? p.title_en : p.title || p.id;
          opt.textContent = title + mult + est + lock;
          opt.disabled = !!p.locked;
          sel.appendChild(opt);
        });
        if (prev) {
          sel.value = prev;
          if (sel.value !== prev) {
            // 选项尚未就绪或已锁定时尽量保留原值（加回临时 option）
            var still = false;
            Array.prototype.slice.call(sel.options).forEach(function (o) {
              if (o.value === prev) still = true;
            });
            if (!still && String(prev).indexOf("vip-") === 0) {
              var tmp = document.createElement("option");
              tmp.value = prev;
              tmp.textContent = prev;
              sel.appendChild(tmp);
              sel.value = prev;
            }
          }
        }
      })
      .catch(function () {});
  }

  async function refreshAll() {
    if (!requireLogin()) return;
    var user = AI24X_API.getAuthUser() || {};
    var userLabel = user.email || user.phone || user.id || "--";
    if ($("acct-user")) $("acct-user").textContent = userLabel;
    if ($("overview-user")) $("overview-user").textContent = userLabel;
    var phoneUnset =
      (window.AI24X_I18N && AI24X_I18N.t && AI24X_I18N.t("page.console.phoneUnset")) ||
      tr("未绑定", "Not bound");
    if ($("acct-phone")) $("acct-phone").textContent = user.phone || phoneUnset;

    try {
      var bal = await AI24X_API.billingBalance();
      // 会话串号防护：余额接口邮箱 vs 本地登录身份不一致 → 强制重登
      var balEmail = String((bal && bal.email) || "")
        .trim()
        .toLowerCase();
      var uiEmail = String(user.email || "")
        .trim()
        .toLowerCase();
      if (balEmail && uiEmail && balEmail !== uiEmail) {
        // 多半是 Playground 残留了其它账号的 API Key；先清 Key 再拉一次，勿直接踢登录
        try {
          AI24X_API.setApiKey("");
          if ($("api-key")) $("api-key").value = "";
        } catch (eClearKey) {}
        if (!window._ai24xBalanceIdentityRetried) {
          window._ai24xBalanceIdentityRetried = true;
          showMsg(
            msgBox(),
            tr(
              "检测到调试 Key 与登录账号不一致，已清除本地 API Key 并刷新。",
              "Playground API key did not match your login. Cleared local key and refreshing."
            ),
            true
          );
          return refreshAll();
        }
        showMsg(
          msgBox(),
          tr(
            "登录身份与钱包账号仍不一致（本地 " +
              uiEmail +
              " / 钱包 " +
              balEmail +
              "）。已退出，请重新登录。",
            "Login still does not match wallet (UI " +
              uiEmail +
              " / wallet " +
              balEmail +
              "). Signed out — please log in again."
          ),
          false
        );
        AI24X_API.clearAuth();
        requireLogin();
        return;
      }
      window._ai24xBalanceIdentityRetried = false;
      if (balEmail && !uiEmail) {
        try {
          var merged = Object.assign({}, user, { email: bal.email });
          AI24X_API.setAuthUser(merged);
          user = merged;
          if ($("acct-user")) $("acct-user").textContent = bal.email;
          if ($("overview-user")) $("overview-user").textContent = bal.email;
        } catch (eMerge) {}
      }
      // 2026-08-04: 口径只剩两条——充值余额 vs 今日免费 shared；不再叠「余额不足+欢迎卡+日赠」
      var usd = Number(bal.balance_usd) || 0;
      var usdDisplay = "$" + (usd / 100).toFixed(2);
      var planIsFree = String(bal.plan || "").toLowerCase() === "free";
      var isVip = !!bal.is_vip_active;
      var walletTokens = Number(bal.balance_tokens) || 0;
      var walletEmpty = walletTokens <= 0 && usd <= 0;
      var sharedOn = !!bal.shared_enabled;
      var sharedLeft = bal.shared_remain_tokens != null ? Number(bal.shared_remain_tokens) : null;
      var sharedCap = Number(bal.shared_daily_token_cap) || 0;

      var tokenDisplay = fmtInt(walletTokens);
      if ($("stat-balance")) $("stat-balance").textContent = usdDisplay;
      var balSub = $("stat-balance-sub");
      if (balSub) {
        if (usd > 0) {
          balSub.textContent =
            "≈ " +
            tokenDisplay +
            " tokens" +
            (bal.credits_expire_at
              ? tr(" · 最早到期 ", " · earliest ") + String(bal.credits_expire_at).slice(0, 10)
              : "");
        } else if (walletTokens > 0) {
          balSub.textContent =
            tokenDisplay +
            " tokens" +
            tr(" · 可用于 flash / pro", " · for flash / pro");
        } else {
          balSub.textContent = tr(
            "充值后可用 flash / pro / 点名模",
            "Top up for flash / pro / named models"
          );
        }
      }

      var sharedVal = $("stat-shared");
      var sharedSub = $("stat-shared-sub");
      var sharedCard = $("stat-shared-card");
      if (sharedCard) sharedCard.style.display = sharedOn ? "" : "none";
      if (sharedOn && sharedVal) {
        sharedVal.textContent =
          sharedLeft != null ? fmtInt(sharedLeft) : "--";
        if (sharedSub) {
          sharedSub.textContent =
            sharedCap > 0
              ? tr("今日剩余 / 日帽 ", "Left / daily cap ") +
                fmtInt(sharedLeft) +
                " / " +
                fmtInt(sharedCap) +
                tr(" · 档位选 shared", " · pick model=shared")
              : tr("档位选 shared 即可试用", "Pick model=shared to try");
        }
      }

      // 单一引导卡（取代「余额不足」+「免费共享已可用」双卡）
      var howto = $("howto-card");
      var howtoTitle = $("howto-title");
      var howtoBody = $("howto-body");
      var btnShared = $("btn-continue-shared");
      var btnTry = $("howto-cta-try");
      var btnBill = $("howto-cta-billing");
      if (howto) {
        var showHowto = false;
        if (!isVip && sharedOn) {
          showHowto = true;
          howto.style.borderColor = "#0f7b4e";
          if (howtoTitle)
            howtoTitle.textContent = tr("怎么开始", "How to start");
          if (howtoBody)
            howtoBody.textContent = tr(
              "两条路：① 试调用选 shared，用今日免费额度；② 充值后可用 flash / pro。两者分开看，互不顶替。",
              "Two paths: ① Try-call with model=shared (free daily pool); ② Top up for flash/pro. Separate quotas."
            );
          if (btnTry) {
            btnTry.style.display = "";
            btnTry.textContent = tr("去试调用（shared）", "Try call (shared)");
          }
          if (btnShared) btnShared.style.display = "none";
          if (btnBill) {
            btnBill.style.display = "";
            btnBill.textContent = tr("去充值", "Top up");
          }
        } else if (isVip && walletEmpty && sharedOn) {
          showHowto = true;
          howto.style.borderColor = "#d4a84b";
          if (howtoTitle)
            howtoTitle.textContent = tr("充值余额已用完", "Paid balance is empty");
          if (howtoBody)
            howtoBody.textContent = tr(
              "flash / pro 需要充值。今日仍可用免费 shared（见右侧「今日免费」）。",
              "flash/pro need a top-up. Free shared may still be available today (see Free today)."
            );
          if (btnTry) btnTry.style.display = "none";
          if (btnShared) {
            btnShared.style.display = "";
            btnShared.className = "btn btn-primary";
            btnShared.textContent = tr("用今日免费 shared", "Use free shared today");
          }
          if (btnBill) {
            btnBill.style.display = "";
            btnBill.className = "btn";
            btnBill.textContent = tr("去充值", "Top up");
          }
        } else if (isVip && walletEmpty && !sharedOn) {
          showHowto = true;
          howto.style.borderColor = "#d4a84b";
          if (howtoTitle)
            howtoTitle.textContent = tr("充值余额已用完", "Paid balance is empty");
          if (howtoBody)
            howtoBody.textContent = tr(
              "请充值后续用 flash / pro / 点名模。",
              "Top up to keep using flash / pro / named models."
            );
          if (btnTry) btnTry.style.display = "none";
          if (btnShared) btnShared.style.display = "none";
          if (btnBill) {
            btnBill.style.display = "";
            btnBill.className = "btn btn-primary";
            btnBill.textContent = tr("去充值", "Top up");
          }
        } else {
          showHowto = false;
        }
        howto.style.display = showHowto ? "" : "none";
      }
      // 旧卡保持隐藏
      var legacyCta = $("balance-cta");
      if (legacyCta) legacyCta.style.display = "none";
      var welcomeCard = $("free-welcome");
      if (welcomeCard) welcomeCard.style.display = "none";

      var planLabel = labelPlanForUi(bal.plan);
      // 仅真实 VIP 且在有效期内显示到期时间
      if (isVip && bal.vip_expires_at && !planIsFree) {
        planLabel +=
          tr(" · 到期 ", " · expires ") + String(bal.vip_expires_at).slice(0, 10);
      } else if (!planIsFree && !isVip && bal.vip_expires_at) {
        planLabel = tr("免费档（VIP 已过期）", "Free (VIP expired)");
      } else if (planIsFree) {
        planLabel = labelPlanForUi("free");
      }
      if ($("acct-plan")) $("acct-plan").textContent = planLabel;
      if ($("overview-plan")) $("overview-plan").textContent = planLabel;
      window._ai24xIsVip = isVip;
      // 免费档：先默认 shared，再填 VIP 选项（避免异步重建把选中值打回 auto）
      var chatSel = $("chat-model");
      if (chatSel && !isVip && bal.shared_enabled) {
        if (!window._ai24xFreeModelBootstrapped) {
          chatSel.value = "shared";
          window._ai24xFreeModelBootstrapped = true;
        } else if (!chatSel.value || chatSel.value === "auto") {
          // 刷新后若仍停在 auto，拉回 shared（免费档 flash/auto 易撞余额不足）
          chatSel.value = "shared";
        }
      }
      fillVipPickOptions(isVip);
    } catch (e) {
      if (e && e.status === 401) {
        AI24X_API.clearAuth();
        requireLogin();
        return;
      }
      showMsg(msgBox(), e.message || tr("余额加载失败", "Failed to load balance"), false);
    }

    try {
      var keysRes = await AI24X_API.keysList();
      var keys = (keysRes && keysRes.keys) || [];
      $("stat-keys").textContent = String(keys.length);
      renderKeys(keys);
    } catch (e) {
      $("stat-keys").textContent = "--";
    }

    try {
      var ref = await AI24X_API.referralsSummary();
      $("stat-referrals").textContent = String(ref.invitees_l1 != null ? ref.invitees_l1 : 0);
      if ($("inviteCode")) $("inviteCode").textContent = ref.code || "--";
      window._ai24xInviteCode = ref.code || "";
      if ($("inviteShortLink")) {
        var sl =
          window.AI24X_INVITE && ref.code
            ? AI24X_INVITE.shortLink(ref.code)
            : ref.code
              ? location.origin + "/r/" + encodeURIComponent(ref.code)
              : "--";
        $("inviteShortLink").textContent = sl || "--";
      }
      if ($("inviteL1Card")) {
        $("inviteL1Card").textContent = String(ref.invitees_l1 != null ? ref.invitees_l1 : 0);
      }
    } catch (e) {
      $("stat-referrals").textContent = "--";
    }

    try {
      var usage = await AI24X_API.billingUsage({ limit: 30 });
      var rows = (usage && usage.rows) || [];
      var consumes = rows.filter(function (r) {
        return r.entry_type === "consume";
      }).length;
      if ($("stat-calls")) $("stat-calls").textContent = String(consumes);
      renderUsage(rows);
    } catch (e) {
      if ($("stat-calls")) $("stat-calls").textContent = "--";
    }

    try {
      var plans = await AI24X_API.billingPlans();
      renderPlans(plans);
    } catch (e) {}

    try {
      var orders = await AI24X_API.billingOrders(20);
      renderOrders((orders && orders.rows) || []);
    } catch (e) {}
  }

  var CONSOLE_PANELS = [
    "overview",
    "keys",
    "billing",
    "usage",
    "playground",
    "invite",
    "account",
  ];

  function normalizeConsolePanel(name) {
    var n = String(name || "")
      .replace(/^#/, "")
      .trim()
      .toLowerCase();
    if (n === "token-plans" || n === "plans" || n === "orders") return "billing";
    if (n === "activity" || n === "ledger") return "usage";
    if (n === "chat" || n === "try") return "playground";
    if (n === "refer" || n === "referral") return "invite";
    if (CONSOLE_PANELS.indexOf(n) >= 0) return n;
    return "overview";
  }

  function showConsolePanel(name, opts) {
    var id = normalizeConsolePanel(name);
    var pushHash = !opts || opts.pushHash !== false;
    document.querySelectorAll(".console-panel").forEach(function (panel) {
      var match = panel.getAttribute("data-console-panel") === id;
      panel.classList.toggle("is-active", match);
      if (match) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
    });
    document.querySelectorAll(".console-nav-item").forEach(function (btn) {
      btn.classList.toggle(
        "is-active",
        btn.getAttribute("data-console-panel") === id
      );
    });
    if (pushHash) {
      try {
        var next = "#" + id;
        if (location.hash !== next) {
          history.replaceState(null, "", next);
        }
      } catch (e) {}
    }
    var msg = msgBox();
    if (msg && id !== "overview") {
      /* keep message visible across panels */
    }
  }

  function bind() {
    function doLogout() {
      if (typeof AI24X_API.logout === "function") AI24X_API.logout();
      else AI24X_API.clearAuth();
      location.href = "login.html";
    }
    var btnLogout = $("btn-logout");
    if (btnLogout) btnLogout.addEventListener("click", doLogout);
    var btnLogoutAcct = $("btn-logout-account");
    if (btnLogoutAcct) btnLogoutAcct.addEventListener("click", doLogout);
    var btnSaveApi = $("btn-save-api");
    if (btnSaveApi) {
      btnSaveApi.addEventListener("click", function () {
        var b = ($("api-base") && $("api-base").value.trim()) || "";
        var k = ($("api-key") && $("api-key").value.trim()) || "";
        if (b) AI24X_API.setBase(b);
        else AI24X_API.setBase("");
        if (k) AI24X_API.setApiKey(k);
        else AI24X_API.setApiKey("");
        showMsg(msgBox(), tr("已保存 API 设置", "API settings saved"), true);
      });
    }
    var btnRefresh = $("btn-refresh");
    if (btnRefresh) {
      btnRefresh.addEventListener("click", function () {
        refreshAll();
      });
    }
    var navTickets = $("nav-tickets");
    if (navTickets) {
      navTickets.addEventListener("click", function (e) {
        e.preventDefault();
        if (window.AI24X_SUPPORT_WIDGET && typeof AI24X_SUPPORT_WIDGET.open === "function") {
          AI24X_SUPPORT_WIDGET.open("ticket");
        } else {
          showMsg(
            msgBox(),
            tr("请使用右下角「协助」打开工单。", "Use the help widget (bottom-right) for tickets."),
            true
          );
        }
      });
    }
    function openModal(id) {
      var el = $(id);
      if (!el) return;
      el.classList.add("is-open");
      el.setAttribute("aria-hidden", "false");
    }
    function closeModal(id) {
      if (id === "modal-pay") {
        closePayModal();
        return;
      }
      var el = $(id);
      if (!el) return;
      el.classList.remove("is-open");
      el.setAttribute("aria-hidden", "true");
    }
    document.querySelectorAll("[data-close-modal]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        closeModal(btn.getAttribute("data-close-modal"));
      });
    });
    function openCreateKeyModal() {
      var inp = $("create-key-name");
      if (inp && !(inp.value || "").trim()) inp.value = defaultKeyName();
      openModal("modal-create-key");
      if (inp) {
        setTimeout(function () {
          inp.focus();
          inp.select();
        }, 0);
      }
    }
    document.querySelectorAll("[data-action='create-key']").forEach(function (btn) {
      btn.addEventListener("click", openCreateKeyModal);
    });
    document.querySelectorAll("[data-console-panel]").forEach(function (el) {
      if (el.classList && el.classList.contains("console-panel")) return;
      el.addEventListener("click", function (ev) {
        var target = el.getAttribute("data-console-panel");
        if (!target) return;
        if (el.tagName === "A") return;
        ev.preventDefault();
        showConsolePanel(target);
        if (el.getAttribute("data-action") === "create-key") openCreateKeyModal();
      });
    });
    window.addEventListener("hashchange", function () {
      showConsolePanel(location.hash || "overview", { pushHash: false });
    });
    showConsolePanel(location.hash || "overview", { pushHash: true });
    var btnConfirmKey = $("btn-create-key-confirm");
    if (btnConfirmKey) {
      btnConfirmKey.addEventListener("click", function () {
        var name = (($("create-key-name") && $("create-key-name").value) || "").trim() || defaultKeyName();
        btnConfirmKey.disabled = true;
        AI24X_API.keysCreate({ name: name })
          .then(function (r) {
            closeModal("modal-create-key");
            if (r && r.api_key) {
              AI24X_API.setApiKey(r.api_key);
              if ($("api-key")) $("api-key").value = r.api_key;
              if ($("modal-show-key-value")) $("modal-show-key-value").textContent = r.api_key;
              openModal("modal-show-key");
              showMsg(
                msgBox(),
                tr("密钥已创建，请复制保存。", "Key created — copy and save it."),
                true
              );
            }
            return refreshAll();
          })
          .catch(function (e) {
            showMsg(msgBox(), e.message || tr("创建失败", "Create failed"), false);
          })
          .finally(function () {
            btnConfirmKey.disabled = false;
          });
      });
    }
    var btnModalCopy = $("btn-modal-copy-key");
    if (btnModalCopy) {
      btnModalCopy.addEventListener("click", function () {
        var t = (($("modal-show-key-value") && $("modal-show-key-value").textContent) || "").trim();
        if (!t || t === "--") return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(t).then(
            function () {
              showMsg(msgBox(), tr("已复制到剪贴板", "Copied to clipboard"), true);
            },
            function () {
              showMsg(
                msgBox(),
                tr("复制失败，请手动选择下方密钥", "Copy failed — select the key manually"),
                false
              );
            }
          );
        }
      });
    }
    var btnCopyKey = $("btn-copy-key");
    if (btnCopyKey) {
      btnCopyKey.addEventListener("click", function () {
        var t = (($("api-key") && $("api-key").value) || "").trim();
        if (!t || t === "--" || t.indexOf("…") >= 0) {
          showMsg(
            msgBox(),
            tr(
              "没有可复制的完整 Key（请在创建弹窗中复制，或到试调页粘贴已保存的 Key）",
              "No full key to copy — use the create dialog, or paste a saved key in Playground"
            ),
            false
          );
          return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(t).then(
            function () {
              showMsg(msgBox(), tr("已复制", "Copied"), true);
            },
            function () {
              showMsg(
                msgBox(),
                tr("复制失败，请手动选择", "Copy failed — select manually"),
                false
              );
            }
          );
        }
      });
    }
    var btnChat = $("btn-chat-run");
    if (btnChat) {
      btnChat.addEventListener("click", function () {
        var out = $("chat-out");
        var chatMsg = msgBox("playgroundMsg");
        var useKey = $("chat-use-api-key") && $("chat-use-api-key").checked;
        var key = ($("api-key").value || AI24X_API.getApiKey() || "").trim();
        if (useKey) {
          if (!key || key.indexOf("…") >= 0 || key.indexOf("...") >= 0) {
            showMsg(
              chatMsg,
              tr(
                "已勾选「用 API Key」。请先到「API 密钥」创建，再把完整 Key 粘到上方。",
                "“Use API key” is on. Create a key under API keys, then paste the full key above."
              ),
              false
            );
            return;
          }
          AI24X_API.setApiKey(key);
        } else if (!AI24X_API.getAuthToken()) {
          showMsg(
            chatMsg,
            tr(
              "请先登录后再发送；或勾选「用 API Key」并用本账号完整密钥。",
              "Sign in first — or check “Use API key” and paste your full key."
            ),
            false
          );
          return;
        }
        var model = ($("chat-model").value || "auto").trim() || "auto";
        out.textContent = tr("请求中…", "Requesting…");
        AI24X_API.chatRun(
          {
            prompt: ($("chat-prompt").value || "").trim() || tr("你好", "Hello"),
            model: model,
            max_tokens: model === "shared" ? 128 : 1000,
          },
          null,
          { preferApiKey: !!useKey }
        )
          .then(function (r) {
            var requested = ($("chat-model").value || "auto").trim() || "auto";
            var reply = (r && r.response) || "";
            var junk =
              /\bon(\s+on){4,}\b/i.test(reply) ||
              /ononon|AIon4X|AI on4X|AI on the 24X|on the 24X|variety\s+variety|ultra\s+tier/i.test(
                reply
              );
            if (junk && requested === "shared") {
              var safe = tr(
                "你好！我是 AI24X 助手，有什么可以帮你的？",
                "Hello! I'm the AI24X assistant. How can I help you today?"
              );
              r = Object.assign({}, r, { response: safe });
              out.textContent = formatChatOut(r, requested);
              showMsg(
                chatMsg,
                tr(
                  "通道已自动换了一条更稳的回复。可再试一次。",
                  "Switched to a cleaner reply. You can try again."
                ),
                true
              );
            } else {
              out.textContent = formatChatOut(r, requested);
              if (requested === "shared") {
                showMsg(
                  chatMsg,
                  tr("免费共享试调完成。", "Free shared try-call done."),
                  true
                );
              }
            }
            return refreshAll();
          })
          .catch(function (e) {
            var errMsg = e.message || tr("试调失败", "Try-call failed");
            if (e && e.status === 401) {
              if (useKey) {
                errMsg = tr(
                  "API Key 无效。请到「API 密钥」创建并粘贴完整 Key；或取消勾选，改用登录发送。",
                  "Invalid API key. Create & paste a full key under API keys — or uncheck to use login."
                );
              } else if (
                /API Key 无效|Invalid API key|鉴权失败|未被试调用接受/i.test(errMsg)
              ) {
                errMsg = tr(
                  "登录会话未被试调用接受。请稍后再试；急需可用时请勾选「用 API Key」发送。",
                  "Try-call did not accept the login session. Try again later, or check “Use API key”."
                );
              } else if (
                /登录已失效|未授权|Unauthorized|需要登录/i.test(errMsg)
              ) {
                errMsg = tr(
                  "登录已失效，请重新登录后再试。",
                  "Session expired. Please sign in again."
                );
              }
            }
            out.textContent = errMsg;
            showMsg(chatMsg, errMsg, false);
            if (e && e.status === 402) {
              var howto402 = $("howto-card");
              var ht = $("howto-title");
              var hb = $("howto-body");
              if (ht) ht.textContent = tr("余额不足", "Insufficient balance");
              if (hb)
                hb.textContent = tr(
                  "请充值后续用 flash / pro；今日免费请改选 shared。",
                  "Top up for flash/pro, or pick shared for today’s free pool."
                );
              if (howto402) howto402.style.display = "";
              showConsolePanel("overview");
            }
          });
      });
    }
    function goTryShared() {
      var sel = $("chat-model");
      if (sel) sel.value = "shared";
      var howto = $("howto-card");
      if (howto) howto.style.display = "none";
      showConsolePanel("playground");
      showMsg(
        msgBox("playgroundMsg"),
        tr(
          "已选 shared。点发送即可用今日免费额度（登录会话，不必勾 API Key）。",
          "model=shared selected. Tap Send to use today’s free pool (login session — no API key needed)."
        ),
        true
      );
      var prompt = $("chat-prompt");
      if (prompt && !(prompt.value || "").trim()) prompt.value = "Hello";
    }
    var btnShared = $("btn-continue-shared");
    if (btnShared) btnShared.addEventListener("click", goTryShared);
    var btnTryHow = $("howto-cta-try");
    if (btnTryHow) {
      btnTryHow.addEventListener("click", function () {
        goTryShared();
      });
    }
    var btnInv = $("btn-copy-invite-link");
    if (btnInv) {
      btnInv.addEventListener("click", function () {
        var code = window._ai24xInviteCode || ($("inviteCode") && $("inviteCode").textContent) || "";
        code = String(code || "").trim();
        if (!code || code === "--") {
          showMsg(msgBox(), tr("暂无邀请码", "No invite code yet"), false);
          return;
        }
        var link =
          (window.AI24X_INVITE && AI24X_INVITE.shortLink(code)) ||
          location.origin + "/r/" + encodeURIComponent(code);
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(link).then(
            function () {
              showMsg(msgBox(), tr("邀请短链已复制", "Short invite link copied"), true);
            },
            function () {
              showMsg(msgBox(), link, true);
            }
          );
        } else {
          showMsg(msgBox(), link, true);
        }
      });
    }
    var btnCode = $("btn-copy-invite-code");
    if (btnCode) {
      btnCode.addEventListener("click", function () {
        var code = window._ai24xInviteCode || ($("inviteCode") && $("inviteCode").textContent) || "";
        code = String(code || "").trim();
        if (!code || code === "--") {
          showMsg(msgBox(), tr("暂无邀请码", "No invite code yet"), false);
          return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(code).then(
            function () {
              showMsg(msgBox(), tr("邀请码已复制", "Invite code copied"), true);
            },
            function () {
              showMsg(msgBox(), code, true);
            }
          );
        } else {
          showMsg(msgBox(), code, true);
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!requireLogin()) return;
    $("api-base").value = AI24X_API.getBase();
    $("api-key").value = AI24X_API.getApiKey();
    bind();
    refreshAll();
    // PayPal return：?paypal=1&out_trade_no=T…
    try {
      var qs = new URLSearchParams(window.location.search || "");
      var otn = qs.get("out_trade_no") || "";
      if (qs.get("paypal") === "1" && otn) {
        if (_fulfillPollTimer) {
          clearInterval(_fulfillPollTimer);
          _fulfillPollTimer = null;
        }
        showMsg(msgBox(), tr("正在确认 PayPal 支付…", "Confirming PayPal…"), true);
        function tryPaypalCapture(attempt) {
          return AI24X_API.billingQueryFulfill(otn, "paypal").catch(function (e) {
            var msg = (e && e.message) || "";
            if (/ALREADY_CAPTURED|已到账|duplicate/i.test(msg)) {
              return { ok: true, duplicate: true };
            }
            // 回跳后偶发连不上 API：自动再试 2 次
            if (attempt < 3 && (e.status === 0 || /无法连接|Cannot reach|Failed to fetch/i.test(msg))) {
              return new Promise(function (resolve, reject) {
                setTimeout(function () {
                  tryPaypalCapture(attempt + 1).then(resolve, reject);
                }, 1500 * attempt);
              });
            }
            throw e;
          });
        }
        tryPaypalCapture(1)
          .then(function (r) {
            showMsg(
              msgBox(),
              r && r.ok
                ? AI24X_API.planFulfillMessage(_lastPayPlanId, null)
                : tr("PayPal 尚未完成，可在「我的订单」点确认到账", "PayPal pending — tap Confirm under My orders"),
              !!(r && r.ok)
            );
            return refreshAll();
          })
          .catch(function (e) {
            var msg = (e && e.message) || "";
            showMsg(
              msgBox(),
              (msg || tr("PayPal 确认失败", "PayPal confirm failed")) +
                tr(" — 请在「我的订单」点「确认到账」", " — tap Confirm under My orders"),
              false
            );
          });
      }
    } catch (e) {}
    var langSel = document.getElementById("lang-select");
    if (langSel) {
      langSel.addEventListener("change", function () {
        refreshAll();
      });
    }
  });
})();
