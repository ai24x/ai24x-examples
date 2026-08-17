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
        token_pack_mid: "进阶包",
        token_vip_month: "VIP 资格包",
        token_vip_month_50w: "VIP名模包",
        token_value_pack: "超值包",
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
        token_pack_mid: "Advanced",
        token_vip_month: "VIP Pass",
        token_vip_month_50w: "Scale",
        token_value_pack: "Value Pack",
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
      var ch = String(c || "").replace(/_query|_capture|_webhook/gi, "");
      if (ch === "creem") return "Creem";
      if (ch === "crypto") return "USDT";
      if (
        ch === "topup" ||
        ch === "topup_usd" ||
        ch === "batch_t2" ||
        ch === "batch_t3" ||
        ch === "joint_test_topup" ||
        ch === "smoke_validity"
      ) {
        return AI24X_API.isZhUi() ? "充值" : "Top-up";
      }
      if (!AI24X_API.isZhUi()) {
        var en = { wechat: "WeChat", alipay: "Alipay", paypal: "PayPal", mock: "Mock" };
        return en[ch] || ch || "";
      }
      var m = { wechat: "微信", alipay: "支付宝", paypal: "PayPal", mock: "模拟" };
      return m[ch] || ch || "";
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
    if (/^FREE\s*月赠额度/i.test(n)) {
      return zh ? n : n.replace(/FREE\s*月赠额度/gi, "Monthly free quota");
    }
    if (/^chat\/run$/i.test(n)) return zh ? "API 调用" : "API call";
    if (/^lot_expire\b/i.test(n)) return zh ? "额度到期自动核销" : "Credit lot expired";
    if (
      /^batch_t\d+$/i.test(n) ||
      /^joint_test_topup$/i.test(n) ||
      /^smoke_validity$/i.test(n)
    ) {
      return zh ? "充值到账" : "Top-up";
    }
    if (
      /^(wechat|alipay|paypal|creem|mock|crypto|topup|topup_usd)(_query|_capture|_webhook)?:/i.test(n) ||
      /^[a-z0-9_]+:T\d+:[a-z0-9_]+$/i.test(n)
    ) {
      var parts = n.split(":");
      var ch0 = String(parts[0] || "");
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
        if (pay.enabled && (pay.wechat_ready || pay.alipay_ready || pay.paypal_ready || pay.creem_ready)) {
          var ch = [];
          if (pay.wechat_ready) ch.push("微信");
          if (pay.alipay_ready) ch.push("支付宝");
          if (pay.paypal_ready) ch.push("PayPal");
          if (pay.creem_ready) ch.push("Creem");
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
        if (pay.enabled && (pay.wechat_ready || pay.alipay_ready || pay.paypal_ready || pay.creem_ready)) {
          var enCh = [];
          if (pay.wechat_ready) enCh.push("WeChat");
          if (pay.alipay_ready) enCh.push("Alipay");
          if (pay.paypal_ready) enCh.push("PayPal");
          if (pay.creem_ready) enCh.push("Creem");
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
          '<path fill="#1677FF" d="M19.695 15.07c3.426 1.158 4.203 1.22 4.203 1.22V3.846c0-2.124-1.705-3.845-3.81-3.845H3.914C1.808.001.102 1.722.102 3.846v16.31c0 2.123 1.706 3.845 3.813 3.845h16.173c2.105 0 3.81-1.722 3.81-3.845v-.157s-6.19-2.602-9.315-4.119c-2.096 2.602-4.8 4.181-7.607 4.181-4.75 0-6.361-4.19-4.112-6.949.49-.602 1.324-1.175 2.617-1.497 2.025-.502 5.247.313 8.266 1.317a16.796 16.796 0 0 0 1.341-3.302H5.781v-.952h4.799V6.975H4.77v-.953h5.81V3.591s0-.409.411-.409h2.347v2.84h5.744v.951h-5.744v1.704h4.69a19.453 19.453 0 0 1-1.986 5.06c1.424.52 2.702 1.011 3.654 1.333m-13.81-2.032c-.596.06-1.71.325-2.321.869-1.83 1.608-.735 4.55 2.968 4.55 2.151 0 4.301-1.388 5.99-3.61-2.403-1.182-4.438-2.028-6.637-1.809"/></svg>'
        );
      }
      if (channel === "creem") {
        return (
          '<svg class="pay-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path fill="#7C3AED" d="M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm0 2v10h16V7H4zm2 2h4v2H6V9zm6 0h6v2h-6V9z"/></svg>'
        );
      }
      if (channel === "paypal") {
        return (
          '<svg class="pay-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path fill="#003087" d="M7.2 20.5h1.7l.5-3.1h1.7c3.3 0 5.5-1.4 6.1-4.3.1-.5.1-.9.1-1.2 0-.2 0-.4-.1-.6H19l.1-.5c.4-2.5-.9-4.2-3.8-4.2H9.2L7.2 20.5zm4.2-11.5h1.7c1.3 0 2 .5 1.8 1.7-.2 1.4-1.2 1.7-2.5 1.7h-1.5l.5-3.4z"/>' +
          '<path fill="#009CDE" d="M9.5 21.5h1.7l.4-2.5H13c2.7 0 4.4-1.1 4.9-3.5.1-.4.1-.7.1-1 0-.1 0-.3 0-.4h1.5l.1-.4c.3-2-.7-3.4-3.1-3.4h-4.3l-1.9 11.2h1.7l.5 3.1h1.4c1.1 0 1.7.4 1.5 1.4-.2 1.1-1 1.4-2.1 1.4H10l.5 3.3z"/></svg>'
        );
      }
      if (channel === "crypto") {
        return (
          '<svg class="pay-ico" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm3.2 11.2c-.1 1.9-1.4 2.9-3.4 3.1v1.7H10.7v-1.7c-2.4-.2-4.2-1.2-4.3-3h2.2c.1 1 1 1.6 2.1 1.7v-4.6c-2.8-.7-4.6-1.9-4.6-3.7 0-1.9 1.7-3.1 4.6-3.3V3h1.1v1.6c2 .2 3.7 1.2 3.8 3h-2.1c0-1-.8-1.6-1.7-1.7v4.3c2.9.8 4.5 1.9 4.5 4zm-2.2-4.2v4.3c1.3-.3 2-1 2-1.9 0-1-.8-1.7-2-2.4z"/></svg>'
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
      tr("有效期", "Validity") +
      "</th><th>" +
      tr("适合", "Best for") +
      "</th><th>" +
      tr("购买", "Buy") +
      "</th></tr></thead>";
    var tbody = document.createElement("tbody");
    plans.forEach(function (p) {
      var caps = AI24X_API.planCaps(p);
      var lit = !!(p.value_pack && window.__isValuePackActive);
      var trEl = document.createElement("tr");
      trEl.className = lit ? "vp-lit" : p.recommended ? "is-recommended" : "";
      if (p.plan) trEl.setAttribute("data-plan", String(p.plan));
      var nameCell = document.createElement("td");
      nameCell.className = "vp-name-cell";
      nameCell.innerHTML =
        "<strong>" +
        (AI24X_API.planTitle(p) || "") +
        "</strong>" +
        (lit
          ? '<span class="vp-lit-badge">' + tr("✓ 已点亮", "✓ Lit") + "</span>"
          : "") +
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
      var flashVal = tokens > 0
        ? "≈ " + AI24X_API.planCreditsShort(p) + " flash"
        : p.set_vip
          ? tr("无额度", "No credits")
          : p.price_usd
            ? "$" + p.price_usd
            : "—";
      var td = document.createElement("td");
      td.textContent = flashVal;
      trEl.appendChild(td);
      trEl.appendChild(tdText(AI24X_API.planNameAccess(p)));
      trEl.appendChild(tdText(AI24X_API.planValidityLabel(p)));
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
      if (pay.creem_ready) addBtn("Creem", "btn btn-primary", "creem");
      if (pay.crypto_ready) addBtn("USDT", "btn btn-usdt", "crypto");
      if (pay.mock_allowed) addBtn(tr("模拟", "Mock"), "btn", "mock");
      if (
        !pay.wechat_ready &&
        !pay.alipay_ready &&
        !pay.paypal_ready &&
        !pay.creem_ready &&
        !pay.crypto_ready &&
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
      "Flash $0.35/百万 · Pro $1.05/百万。Scale：12 个月名模资格 + 2 亿额度；已有额度可补购 VIP 资格包。额度到期后剩余自动核销。",
      "Flash $0.35/M · Pro $1.05/M. Scale = 12-mo named access + 200M credits; VIP Pass adds access if you already have credits. Unused credits expire with the plan."
    );
    wrap.appendChild(tip);
    box.appendChild(wrap);
    if (window.__isValuePackActive) {
      litValuePackRows();
    } else {
      try {
        AI24X_API.billingBalance()
          .then(function (bal) {
            if (bal && bal.is_value_pack_active) {
              window.__isValuePackActive = true;
              litValuePackRows();
            }
          })
          .catch(function () {});
      } catch (eBal) {}
    }
    tryApplyPayDeepLink();
  }

  function litValuePackRows() {
    var box = $("plansList");
    if (!box) return;
    var rows = box.querySelectorAll('tr[data-plan="token_value_pack"]');
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (row.classList.contains("vp-lit")) continue;
      row.classList.add("vp-lit");
      var nm = row.querySelector(".vp-name-cell");
      if (nm && !nm.querySelector(".vp-lit-badge")) {
        var b = document.createElement("span");
        b.className = "vp-lit-badge";
        b.textContent = tr("✓ 已点亮", "✓ Lit");
        nm.appendChild(b);
      }
    }
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
  function appendCryptoTxidBox(outTradeNo, planId) {
    var resultEl = $("modal-pay-result");
    if (!resultEl) return;
    var oldBox = $("crypto-txid-box");
    if (oldBox) oldBox.remove();
    var box = document.createElement("div");
    box.id = "crypto-txid-box";
    box.style.marginTop = "10px";
    box.innerHTML =
      '<input id="crypto-txid-input" type="text" placeholder="' +
        tr("粘贴 TRC20 txid", "Paste TRC20 txid") +
        '" style="width:100%;padding:8px;box-sizing:border-box;border:1px solid #d1d5db;border-radius:6px;">' +
      '<button id="crypto-txid-btn" class="btn btn-primary" style="margin-top:8px;width:100%;">' +
        tr("提交核验（本地 mock 入账）", "Submit & verify (mock)") +
        "</button>";
    resultEl.appendChild(box);
    var btn = $("crypto-txid-btn");
    btn.addEventListener("click", function () {
      var inputEl = $("crypto-txid-input");
      var txid = (inputEl && inputEl.value || "").trim();
      if (txid.length < 8) {
        showPayResult({
          isError: true,
          hint: tr("请先粘贴有效的 txid（至少 8 位）", "Paste a valid txid (min 8 chars)"),
        });
        return;
      }
      btn.disabled = true;
      btn.textContent = tr("核验中…", "Verifying…");
      AI24X_API.billingCryptoSubmit(outTradeNo, txid)
        .then(function () {
          return AI24X_API.billingCryptoVerify(outTradeNo);
        })
        .then(function () {
          closePayModal();
          showMsg(msgBox(), tr("Crypto 订单已入账 ✅", "Crypto order fulfilled ✅"), true);
          return refreshAll();
        })
        .catch(function (e) {
          btn.disabled = false;
          btn.textContent = tr("提交核验（本地 mock 入账）", "Submit & verify (mock)");
          showPayResult({ isError: true, hint: e.message || tr("核验失败", "Verify failed") });
        });
    });
  }

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
    } else if (channel === "creem") {
      checkoutWin = openCheckoutPlaceholder(
        "正在创建 Creem 订单，请稍候…（勿关闭此窗口）",
        "Creating Creem order… Keep this tab open."
      );
      showMsg(
        msgBox(),
        tr(
          "正在创建 Creem 订单，请稍候…（勿关闭此窗口）",
          "Creating Creem order… Keep this tab open."
        ),
        true
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
          : channel === "creem"
            ? tr(
                "正在创建 Creem 订单，请稍候；若未弹出窗口，用下方按钮打开。",
                "Creating Creem order… If no window opens, use the button below."
              )
          : channel === "paypal"
            ? tr(
                "正在创建 PayPal 订单，请稍候；若未弹出窗口，用下方按钮打开。",
                "Creating PayPal order… If no window opens, use the button below."
              )
          : channel === "crypto"
            ? tr(
                "正在创建 Crypto 订单，请稍候…",
                "Creating Crypto order…")
            : tr("请选择支付方式", "Choose a payment method");
    openPayModal(planTitle + (price ? " · " + price : ""), payBusyHint);

    var req =
      channel === "alipay"
        ? AI24X_API.billingAlipayWap(planId)
        : channel === "creem"
          ? AI24X_API.billingCreemOrder(planId)
          : channel === "paypal"
            ? AI24X_API.billingPaypalOrder(planId)
            : channel === "crypto"
              ? AI24X_API.billingCryptoOrder(planId)
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
        } else if (channel === "creem" && r && r.pay_url) {
          var crOpened = navigateCheckoutWin(checkoutWin, r.pay_url);
          showPayResult({
            hint:
              (crOpened
                ? tr("已打开 Creem，请在新窗口完成付款。", "Creem opened — finish payment there.")
                : tr(
                    "浏览器拦截了新窗口时，请点击下方按钮打开 Creem。",
                    "If the browser blocked the window, open Creem with the button below."
                  )) +
              tr(
                " 付完返回本页会自动确认到账。单号：",
                " After return, this page auto-confirms. Order: "
              ) +
              (r.out_trade_no || "") +
              (r.amount_usd ? " · $" + r.amount_usd : ""),
            openUrl: r.pay_url,
            openLabel: tr("打开 Creem", "Open Creem"),
          });
          startFulfillPoll(r.out_trade_no, "creem", planId);
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
        } else if (channel === "crypto" && r && r.address) {
          closeCheckoutWin(checkoutWin);
          showPayResult({
            hint:
              tr(
                "请向下方 TRC20 地址转入 " +
                  (r.amount_usdt || r.amount_usd || "") +
                  " USDT（单号 " +
                  (r.out_trade_no || "") +
                  "）。转账完成后，在输入框粘贴 txid 并点「提交核验」。",
                "Send " +
                  (r.amount_usdt || r.amount_usd || "") +
                  " USDT to the TRC20 address below (order " +
                  (r.out_trade_no || "") +
                  "). After transfer, paste the txid and tap Verify."
              ),
            qrData: r.address,
            urlText: r.address,
          });
          appendCryptoTxidBox(r.out_trade_no, planId);
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
      // PayPal 单 amount_fen 为 USD 美分；微信/支付宝为 CNY 分
      var moneyLabel =
        o.channel === "paypal" || o.channel === "creem"
          ? "$" + amt
          : AI24X_API.isZhUi()
            ? "¥" + amt
            : "CNY " + amt;
      left.textContent =
        labelPlanForUi(o.plan) +
        " · " +
        moneyLabel +
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

  function fmtMoneyCents(cents, fx) {
    var zh = AI24X_API.isZhUi();
    var v = (Number(cents) || 0) / 100;
    var sign = v < 0 ? "-" : "+";
    var abs = Math.abs(v);
    return zh ? sign + "¥" + (abs * fx).toFixed(2) : sign + "$" + abs.toFixed(2);
  }

  function fmtTokensCount(n) {
    var v = Number(n) || 0;
    if (v >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(1).replace(/\.0$/, "") + "k";
    return String(v);
  }

  var USAGE_RANGE = "month";   // month | 7d | 30d | all
  var USAGE_METRIC = "usd";    // usd | tokens | calls
  var _usageChartCache = null;
  var TX_PAGE_SIZE = 15;
  var txPage = 0;
  var txTotal = 0;
  var txType = "";
  var txBindDone = false;

  function usageRangeParams() {
    var now = new Date();
    function iso(d) { return d.toISOString().slice(0, 10); }
    var y = now.getUTCFullYear(), m = now.getUTCMonth(), d = now.getUTCDate();
    var since = null, days = 30;
    if (USAGE_RANGE === "month") {
      since = iso(new Date(Date.UTC(y, m, 1)));
      days = 31;
    } else if (USAGE_RANGE === "7d") {
      since = iso(new Date(Date.UTC(y, m, d - 6)));
      days = 7;
    } else if (USAGE_RANGE === "30d") {
      since = iso(new Date(Date.UTC(y, m, d - 29)));
      days = 30;
    } else {
      days = 365;
    }
    return { since: since, until: iso(new Date(Date.UTC(y, m, d))), days: days };
  }

  function fmtUsdSpend(usdCents, fx) {
    return fmtMoneyCents(Number(usdCents) || 0, fx);
  }

  function renderUsageChart(data) {
    var wrap = $("usageChart");
    if (!wrap) return;
    var rows = (data && data.rows) || [];
    var fx = (data && data.fx) || 7.2;
    if (!rows.length) {
      wrap.innerHTML = "<div class='usage-empty'>" + tr("暂无消耗数据", "No usage data") + "</div>";
      return;
    }
    var metric = USAGE_METRIC;
    var vals = rows.map(function (r) {
      return metric === "usd"
        ? Number(r.usd_cents) || 0
        : metric === "tokens"
          ? Number(r.tokens) || 0
          : Number(r.calls) || 0;
    });
    var max = Math.max.apply(null, vals.concat([1]));
    var W = 720, H = 172, padT = 10, padB = 24;
    var n = rows.length;
    var slot = W / n;
    var barW = Math.max(2, Math.min(18, slot * 0.62));
    var parts = [];
    parts.push("<svg viewBox='0 0 " + W + " " + H + "' role='img' aria-label='usage trend' xmlns='http://www.w3.org/2000/svg'>");
    for (var g = 0; g <= 3; g++) {
      var gy = padT + ((H - padT - padB) * g) / 3;
      parts.push("<line x1='0' y1='" + gy + "' x2='" + W + "' y2='" + gy + "' stroke='#e5e7eb' stroke-width='1'/>");
    }
    rows.forEach(function (r, i) {
      var v = vals[i];
      var bh = v > 0 ? Math.max(2, ((H - padT - padB) * v) / max) : 1;
      var x = i * slot + (slot - barW) / 2;
      var y = H - padB - bh;
      var dateTxt = (r.date || "").slice(5);
      var tip =
        dateTxt +
        " · " +
        fmtUsdSpend(r.usd_cents, fx) +
        " · " +
        fmtTokensCount(r.tokens || 0) +
        " tok · " +
        (r.calls || 0) +
        " " +
        tr("次", "calls");
      parts.push(
        "<rect x='" + x + "' y='" + y + "' width='" + barW + "' height='" + bh + "' rx='2' fill='#2563eb' opacity='0.85'>" +
        "<title>" + escapeHtml(tip) + "</title></rect>"
      );
    });
    var labelStep = Math.max(1, Math.ceil(n / 12));
    rows.forEach(function (r, i) {
      if (i % labelStep !== 0 && i !== n - 1) return;
      var x = i * slot + slot / 2;
      parts.push(
        "<text x='" + x + "' y='" + (H - 8) + "' text-anchor='middle' font-size='10' fill='#888'>" +
        escapeHtml((r.date || "").slice(5)) +
        "</text>"
      );
    });
    parts.push("</svg>");
    wrap.innerHTML = parts.join("");
  }

  function renderUsageModels(data) {
    var box = $("usageModels");
    if (!box) return;
    var rows = (data && data.rows) || [];
    var fx = (data && data.fx) || 7.2;
    box.innerHTML = "";
    if (!rows.length) {
      box.innerHTML = "<div class='usage-empty'>" + tr("该时段暂无消耗", "No usage in this period") + "</div>";
      return;
    }
    rows.forEach(function (r) {
      var row = document.createElement("div");
      row.className = "usage-model-row";
      var name = document.createElement("div");
      name.className = "usage-model-name";
      name.textContent = brandModelLabel("", "", r.model);
      name.title = r.model;
      var barWrap = document.createElement("div");
      barWrap.className = "usage-model-bar-wrap";
      var bar = document.createElement("div");
      bar.className = "usage-model-bar";
      bar.style.width = Math.max(2, Math.min(100, Number(r.usd_pct) || 0)) + "%";
      barWrap.appendChild(bar);
      var num = document.createElement("div");
      num.className = "usage-model-num";
      num.textContent =
        fmtUsdSpend(r.usd_cents, fx) +
        " · " +
        fmtTokensCount(r.tokens || 0) +
        " tok · " +
        (r.calls || 0) +
        " " +
        tr("次", "calls");
      var pct = document.createElement("div");
      pct.className = "usage-model-pct";
      pct.textContent = (Number(r.usd_pct) || 0).toFixed(1) + "%";
      row.appendChild(name);
      row.appendChild(barWrap);
      row.appendChild(num);
      row.appendChild(pct);
      box.appendChild(row);
    });
  }

  function renderUsageKeys(data) {
    var box = $("usageKeys");
    if (!box) return;
    var rows = (data && data.rows) || [];
    var fx = (data && data.fx) || 7.2;
    box.innerHTML = "";
    if (!rows.length) {
      box.innerHTML = "<div class='usage-empty'>" + tr("该时段暂无 Key 消耗", "No key usage in this period") + "</div>";
      return;
    }
    rows.forEach(function (r) {
      var row = document.createElement("div");
      row.className = "usage-model-row";
      var name = document.createElement("div");
      name.className = "usage-model-name";
      name.textContent = r.name || tr("控制台会话", "Console session");
      name.title = r.name || "";
      var barWrap = document.createElement("div");
      barWrap.className = "usage-model-bar-wrap";
      var bar = document.createElement("div");
      bar.className = "usage-model-bar";
      bar.style.width = Math.max(2, Math.min(100, Number(r.usd_pct) || 0)) + "%";
      barWrap.appendChild(bar);
      var num = document.createElement("div");
      num.className = "usage-model-num";
      num.textContent =
        fmtUsdSpend(r.usd_cents, fx) +
        " · " +
        fmtTokensCount(r.tokens || 0) +
        " tok · " +
        (r.calls || 0) +
        " " +
        tr("次", "calls");
      var pct = document.createElement("div");
      pct.className = "usage-model-pct";
      pct.textContent = (Number(r.usd_pct) || 0).toFixed(1) + "%";
      row.appendChild(name);
      row.appendChild(barWrap);
      row.appendChild(num);
      row.appendChild(pct);
      box.appendChild(row);
    });
  }

  function initUsageStatsLabels() {
    var rangeMap = {
      month: tr("本月", "This month"),
      "7d": tr("近7天", "Last 7 days"),
      "30d": tr("近30天", "Last 30 days"),
      all: tr("全部", "All time"),
    };
    document.querySelectorAll(".usage-range-btn").forEach(function (b) {
      b.textContent = rangeMap[b.getAttribute("data-range")] || b.getAttribute("data-range");
    });
    var metricMap = { usd: tr("费用", "Cost"), tokens: "Tokens", calls: tr("请求数", "Calls") };
    document.querySelectorAll(".usage-metric-btn").forEach(function (b) {
      b.textContent = metricMap[b.getAttribute("data-metric")] || b.getAttribute("data-metric");
    });
    var rl = $("usage-range-label");
    if (rl) rl.textContent = tr("统计范围", "Period");
    var ct = $("usage-chart-title");
    if (ct) ct.textContent = tr("每日消耗趋势", "Daily usage trend");
    var mt = $("usage-models-title");
    if (mt) mt.textContent = tr("模型消耗分布", "Usage by model");
    var kt = $("usage-keys-title");
    if (kt) kt.textContent = tr("按 API Key 消耗", "Usage by API key");
  }

  function loadUsageStats() {
    var card = $("usageStatsCard");
    if (!card) return;
    card.style.display = "";
    var p = usageRangeParams();
    AI24X_API.billingUsageDaily(p.days)
      .then(function (d) {
        _usageChartCache = d;
        renderUsageChart(d);
      })
      .catch(function () {
        var w = $("usageChart");
        if (w) w.innerHTML = "<div class='usage-empty'>" + tr("加载失败，请稍后重试", "Failed to load, try again later") + "</div>";
      });
    AI24X_API.billingUsageModels(p.days, 10)
      .then(renderUsageModels)
      .catch(function () {
        var b = $("usageModels");
        if (b) b.innerHTML = "<div class='usage-empty'>" + tr("加载失败，请稍后重试", "Failed to load, try again later") + "</div>";
      });
    AI24X_API.billingUsageKeys(p.days, 8)
      .then(renderUsageKeys)
      .catch(function () {
        var k = $("usageKeys");
        if (k) k.innerHTML = "<div class='usage-empty'>" + tr("加载失败，请稍后重试", "Failed to load, try again later") + "</div>";
      });
  }

  function fmtUsageTime(iso) {
    if (!iso) return "--";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    function p(n) { return n < 10 ? "0" + n : "" + n; }
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  function exportBillingCsv() {
    var btn = $("usage-export-btn");
    if (btn) { btn.disabled = true; btn.textContent = tr("导出中…", "Exporting…"); }
    var rp = usageRangeParams();
    var baseParams = {};
    if (rp.since) baseParams.since = rp.since;
    if (rp.until) baseParams.until = rp.until;
    if (txType) baseParams.entry_type = txType;
    var all = [];
    var step = 200;
    var off = 0;
    function next() {
      AI24X_API.billingTransactions(Object.assign({ limit: step, offset: off }, baseParams))
        .then(function (u) {
          var rows = (u && u.rows) || [];
          all = all.concat(rows);
          var total = (u && u.total) != null ? Number(u.total) : all.length;
          off += rows.length;
          if (rows.length && off < total) { next(); } else { finish(all); }
        })
        .catch(function () { finish(all); });
    }
    function finish(rows) {
      var esc = function (v) {
        v = String(v == null ? "" : v);
        if (/[",\n\r]/.test(v)) return "\"" + v.replace(/"/g, "\"\"") + "\"";
        return v;
      };
      var head = ["type", "model", "time", "amount_tokens", "amount_usd_cents", "tokens", "balance_tokens", "note", "request_id"].map(esc).join(",");
      var lines = [head];
      rows.forEach(function (r) {
        lines.push([(r.type || r.entry_type), r.model, r.created_at, r.amount != null ? r.amount : "", r.amount_usd != null ? r.amount_usd : "", r.tokens != null ? r.tokens : "", r.balance != null ? r.balance : "", humanizeLedgerNote(r.note) || "", r.request_id || ""].map(esc).join(","));
      });
      var csv = "\ufeff" + lines.join("\r\n");
      var blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "ai24x-billing-" + new Date().toISOString().slice(0, 10) + ".csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
      if (btn) { btn.disabled = false; btn.textContent = tr("导出 CSV", "Export CSV"); }
    }
    next();
  }

  function txAmountText(row, fx) {
    var parts = [];
    if (row.amount != null && Number(row.amount) !== 0) {
      parts.push((Number(row.amount) > 0 ? "+" : "") + fmtTokensCount(row.amount) + " tok");
    }
    if (row.amount_usd != null && Number(row.amount_usd) !== 0) {
      parts.push(fmtMoneyCents(row.amount_usd, fx));
    }
    return parts.join(" · ") || "--";
  }

  function txAmountClass(row) {
    var v = Number(row.amount_usd) || 0;
    if (v !== 0) return v > 0 ? "col-amount-pos" : "col-amount-neg";
    return (Number(row.amount) || 0) >= 0 ? "col-amount-pos" : "col-amount-neg";
  }

  function renderTransactions(d) {
    var rows = (d && d.rows) || [];
    var sm = (d && d.summary) || {};
    var fx = Number(sm.fx) || 7.2;
    var tbody = $("txList");
    if (!tbody) return;
    var sIn = $("tx-total-in");
    var sOut = $("tx-total-out");
    var sBal = $("tx-balance");
    var sInSub = $("tx-total-in-sub");
    var sOutSub = $("tx-total-out-sub");
    var zh = AI24X_API.isZhUi();
    function usdTxt(cents) {
      return zh ? "¥" + ((Number(cents) || 0) / 100 * fx).toFixed(2) : "$" + ((Number(cents) || 0) / 100).toFixed(2);
    }
    if (sIn) sIn.textContent = "+" + fmtTokensCount(sm.token_in) + " tok";
    if (sInSub) sInSub.textContent = usdTxt(sm.usd_in_cents) + (zh ? " 充值/赠送/返利" : " top-ups/bonuses/ref");
    if (sOut) sOut.textContent = "-" + fmtTokensCount(sm.token_out) + " tok";
    if (sOutSub) sOutSub.textContent = usdTxt(sm.usd_out_cents) + (zh ? " 消耗/过期" : " usage/expirations");
    if (sBal) sBal.textContent = fmtTokensCount(sm.current_balance_tokens);
    var pages = Math.max(1, Math.ceil((d.total || 0) / TX_PAGE_SIZE));
    var pi = $("tx-page-info");
    if (pi) pi.textContent = tr("第 " + (txPage + 1) + " / " + pages + " 页", "Page " + (txPage + 1) + " / " + pages);
    var pv = $("tx-prev");
    var nx = $("tx-next");
    if (pv) pv.disabled = txPage <= 0;
    if (nx) nx.disabled = txPage >= pages - 1;

    tbody.innerHTML = "";
    if (!rows.length) {
      var tdE = document.createElement("td");
      tdE.colSpan = 7;
      tdE.className = "usage-empty";
      tdE.textContent = tr("暂无流水", "No transactions");
      var trE = document.createElement("tr");
      trE.appendChild(tdE);
      tbody.appendChild(trE);
      return;
    }
    rows.forEach(function (r) {
      var trEl = document.createElement("tr");
      var tdTime = document.createElement("td");
      tdTime.className = "col-time";
      tdTime.textContent = fmtUsageTime(r.created_at);
      var tdType = document.createElement("td");
      tdType.textContent = labelEntryType(r.type || r.entry_type);
      var tdModel = document.createElement("td");
      tdModel.textContent = r.model ? brandModelLabel("", "", r.model) : "--";
      // 2026-08-15 峰谷：DeepSeek 点名消费标注调用时段（账单透明）
      if (
        r.model &&
        /^vip-ds-(flash|pro)$/.test(r.model) &&
        (r.type === "consume" || r.entry_type === "consume")
      ) {
        var periodEl = document.createElement("span");
        periodEl.className = "usage-tok-sub";
        var pd = new Date(r.created_at);
        var ph = pd.getUTCHours() + 8;
        if (ph >= 24) ph -= 24;
        var isPk = (ph >= 9 && ph < 12) || (ph >= 14 && ph < 18);
        periodEl.textContent = isPk
          ? tr(" · 峰时", " · peak")
          : tr(" · 谷时", " · off-peak");
        tdModel.appendChild(periodEl);
      }
      var tdAmt = document.createElement("td");
      tdAmt.className = "col-amount " + txAmountClass(r);
      tdAmt.textContent = txAmountText(r, fx);
      var tdTok = document.createElement("td");
      tdTok.className = "col-tokens";
      if (r.tokens != null) {
        tdTok.textContent = fmtTokensCount(r.tokens);
        if (r.prompt_tokens != null || r.completion_tokens != null) {
          var ioSub = document.createElement("span");
          ioSub.className = "usage-tok-sub";
          ioSub.textContent = tr(
            "入 " + fmtTokensCount(r.prompt_tokens || 0) + " · 出 " + fmtTokensCount(r.completion_tokens || 0),
            "in " + fmtTokensCount(r.prompt_tokens || 0) + " · out " + fmtTokensCount(r.completion_tokens || 0)
          );
          tdTok.appendChild(ioSub);
        }
      } else {
        tdTok.textContent = "--";
      }
      var tdBal = document.createElement("td");
      tdBal.className = "col-tokens";
      tdBal.textContent = r.balance != null ? fmtTokensCount(r.balance) : "--";
      var tdNote = document.createElement("td");
      tdNote.className = "col-note";
      var noteTxt = humanizeLedgerNote(r.note);
      if (!noteTxt && r.request_id) noteTxt = r.request_id.slice(0, 18);
      tdNote.textContent = noteTxt || "--";
      trEl.appendChild(tdTime);
      trEl.appendChild(tdType);
      trEl.appendChild(tdModel);
      trEl.appendChild(tdAmt);
      trEl.appendChild(tdTok);
      trEl.appendChild(tdBal);
      trEl.appendChild(tdNote);
      tbody.appendChild(trEl);
    });
  }

  function loadTransactionsPage(page) {
    txPage = Math.max(0, page);
    var rp = usageRangeParams();
    var params = { limit: TX_PAGE_SIZE, offset: txPage * TX_PAGE_SIZE };
    if (rp.since) params.since = rp.since;
    if (rp.until) params.until = rp.until;
    if (txType) params.entry_type = txType;
    AI24X_API.billingTransactions(params)
      .then(function (d) {
        txTotal = Number((d && d.total) || 0);
        renderTransactions(d);
      })
      .catch(function () {
        var tbody = $("txList");
        if (tbody) {
          tbody.innerHTML = "<tr><td colspan=\"7\" class=\"usage-empty\">" + escapeHtml(tr("加载失败，请稍后重试", "Failed to load, try again later")) + "</td></tr>";
        }
      });
  }

  function bindTransactionsControls() {
    if (txBindDone) return;
    txBindDone = true;
    var pv = $("tx-prev");
    var nx = $("tx-next");
    var exp = $("usage-export-btn");
    if (pv) pv.addEventListener("click", function () { loadTransactionsPage(txPage - 1); });
    if (nx) nx.addEventListener("click", function () { loadTransactionsPage(txPage + 1); });
    if (exp) exp.addEventListener("click", exportBillingCsv);
    initUsageStatsLabels();
    document.querySelectorAll("#usage-range-group .usage-range-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        USAGE_RANGE = b.getAttribute("data-range");
        document.querySelectorAll("#usage-range-group .usage-range-btn").forEach(function (x) {
          x.classList.toggle("is-active", x === b);
        });
        txPage = 0;
        loadTransactionsPage(0);
        loadUsageStats();
      });
    });
    document.querySelectorAll(".usage-metric-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        USAGE_METRIC = b.getAttribute("data-metric");
        document.querySelectorAll(".usage-metric-btn").forEach(function (x) {
          x.classList.toggle("is-active", x === b);
        });
        renderUsageChart(_usageChartCache);
      });
    });
    document.querySelectorAll("#tx-type-group .tx-type-btn").forEach(function (b) {
      var t = b.getAttribute("data-tx-type") || "";
      b.textContent = t ? labelEntryType(t) : tr("全部", "All");
      b.addEventListener("click", function () {
        txType = b.getAttribute("data-tx-type") || "";
        document.querySelectorAll("#tx-type-group .tx-type-btn").forEach(function (x) {
          x.classList.toggle("is-active", x === b);
        });
        txPage = 0;
        loadTransactionsPage(0);
      });
    });
    loadTransactionsPage(0);
    loadUsageStats();
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

  function tkey(key, fallbackEn) {
    try {
      if (window.AI24X_I18N && typeof window.AI24X_I18N.t === "function") {
        var v = window.AI24X_I18N.t(key);
        if (v && v !== key) return v;
      }
    } catch (e) {}
    return fallbackEn || key;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtDateTime(iso) {
    if (!iso) return "--";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "--";
    var p = function (n) { return n < 10 ? "0" + n : "" + n; };
    return (
      d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
      " " + p(d.getHours()) + ":" + p(d.getMinutes())
    );
  }

  function renderInvitees(containerId, data) {
    var el = document.getElementById(containerId);
    if (!el) return;
    var rows = (data && data.rows) || [];
    var total = data && data.total != null ? Number(data.total) : rows.length;
    var countEl = document.getElementById(containerId.indexOf("overview") === 0 ? "overview-invitees-count" : "panel-invitees-count");
    if (!rows.length) {
      el.innerHTML = '<div class="invite-reward-empty">' + escapeHtml(tkey("page.console.inviteReward.empty", "No invitees yet — share your code to get started.")) + "</div>";
      if (countEl) countEl.textContent = "";
      return;
    }
    var html = '<table class="invite-reward-table"><thead><tr>' +
      "<th>" + escapeHtml(tkey("page.console.inviteReward.colUser", "User")) + "</th>" +
      "<th>" + escapeHtml(tkey("page.console.inviteReward.colTime", "Registered")) + "</th>" +
      "<th>" + escapeHtml(tkey("page.console.inviteReward.colStatus", "Status")) + "</th>" +
      "</tr></thead><tbody>";
    rows.forEach(function (r) {
      var active = !!r.activated;
      var cls = active ? "badge-active" : "badge-pending";
      var label = active
        ? escapeHtml(tkey("page.console.inviteReward.active", "Activated"))
        : escapeHtml(tkey("page.console.inviteReward.inactive", "Not activated"));
      html += "<tr>" +
        "<td>" + escapeHtml(r.username_masked || "--") + "</td>" +
        "<td>" + escapeHtml(fmtDateTime(r.registered_at)) + "</td>" +
        "<td><span class=\"" + cls + "\">" + label + "</span></td>" +
        "</tr>";
    });
    html += "</tbody></table>";
    if (total > rows.length) {
      var moreTpl = tkey("page.console.inviteReward.more", "Showing {shown} of {total}");
      html += '<div class="sub" style="text-align:right;margin-top:6px;">' + escapeHtml(moreTpl.replace("{shown}", rows.length).replace("{total}", total)) + "</div>";
    }
    el.innerHTML = html;
    if (countEl) countEl.textContent = "(" + total + ")";
  }

    async function loadInvitees() {
      var data = await AI24X_API.referralsInvitees(50, 0);
      renderInvitees("overview-invitees-wrap", data);
      renderInvitees("panel-invitees-wrap", data);
    }

    // —— 工单：系统私信（多轮对话，全部留档）——
    var _supportListRows = [];
    var _supportCurrentTicket = null;

    function escHtml(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function supportStatusLabel(st) {
      var map = {
        open: tr("处理中", "Open"),
        replied: tr("已回复", "Replied"),
        closed: tr("已关闭", "Closed"),
      };
      return map[st] || st || "--";
    }

    function supportSenderLabel(sender) {
      if (sender === "admin") return tr("客服", "Support");
      if (sender === "system") return tr("AI 助手", "AI assistant");
      return tr("我", "Me");
    }

    function supportCatLabel(cat) {
      var map = {
        api: tr("API / 调用", "API / Calls"),
        billing: tr("充值 / 账单", "Billing / Orders"),
        account: tr("账号", "Account"),
        suggestion: tr("建议", "Suggestion"),
        complaint: tr("投诉", "Complaint"),
      };
      return map[cat] || cat || "--";
    }

    function supportTime(iso) {
      if (!iso) return "";
      try {
        var d = new Date(iso);
        if (isNaN(d.getTime())) return "";
        var p = function (n) {
          return (n < 10 ? "0" : "") + n;
        };
        return (
          d.getFullYear() +
          "-" + p(d.getMonth() + 1) +
          "-" + p(d.getDate()) +
          " " + p(d.getHours()) +
          ":" + p(d.getMinutes())
        );
      } catch (e) {
        return "";
      }
    }

    function renderSupportList(rows) {
      _supportListRows = rows || [];
      var box = $("support-list");
      if (!box) return;
      if (!_supportListRows.length) {
        box.innerHTML =
          '<p class="sub">' + escHtml(tr("暂无工单，点上方「新建工单」开始。", "No tickets yet — tap New ticket above to start.")) + "</p>";
        return;
      }
      var html = _supportListRows
        .map(function (t) {
          var active =
            _supportCurrentTicket && Number(t.id) === Number(_supportCurrentTicket) ? " is-active" : "";
          var last = t.last_message || t.body || "";
          var senderTag = t.last_sender === "user" ? tr("我", "Me") + ": " : "";
          return (
            '<div class="support-ticket-item' + active + '" data-support-ticket="' + Number(t.id) + '">' +
              '<div class="support-ticket-subj">' + escHtml(t.subject || "#" + t.id) + "</div>" +
              '<div class="support-ticket-last">' + escHtml(senderTag + last) + "</div>" +
              '<div class="support-ticket-meta">' +
                '<span class="support-status ' + escHtml(t.status || "open") + '">' +
                  escHtml(supportStatusLabel(t.status)) +
                "</span>" +
                (t.last_at ? "<span>" + escHtml(supportTime(t.last_at)) + "</span>" : "") +
              "</div>" +
            "</div>"
          );
        })
        .join("");
      box.innerHTML = html;
      box.querySelectorAll("[data-support-ticket]").forEach(function (el) {
        el.addEventListener("click", function () {
          openSupportTicket(Number(el.getAttribute("data-support-ticket")));
        });
      });
    }

    function renderSupportMessages(t) {
      var msgsBox = $("support-conv-msgs");
      if (!msgsBox) return;
      var msgs = (t && t.messages) || [];
      if (!msgs.length) {
        msgs = [{ sender: "user", content: t.body || "", created_at: t.created_at }];
      }
      msgsBox.innerHTML = msgs
        .map(function (m) {
          var isUser = m.sender === "user";
          var cls = isUser ? "support-msg is-user" : "support-msg";
          var bubble = isUser
            ? "user"
            : m.sender === "admin"
            ? "admin"
            : "system";
          return (
            '<div class="' + cls + '">' +
              '<div class="support-bubble support-bubble-' + bubble + '">' +
                escHtml(m.content || "") +
              "</div>" +
              '<div class="support-msg-meta">' +
                escHtml(supportSenderLabel(m.sender)) +
                (m.created_at ? " · " + escHtml(supportTime(m.created_at)) : "") +
              "</div>" +
            "</div>"
          );
        })
        .join("");
      msgsBox.scrollTop = msgsBox.scrollHeight;
    }

    function showSupportConv() {
      var empty = $("support-no-select");
      if (empty) empty.style.display = "none";
      var newBox = $("support-new-box");
      if (newBox) newBox.style.display = "none";
      var conv = $("support-conv-box");
      if (conv) conv.style.display = "flex";
    }

    function showSupportEmpty() {
      var conv = $("support-conv-box");
      if (conv) conv.style.display = "none";
      var newBox = $("support-new-box");
      if (newBox) newBox.style.display = "none";
      var empty = $("support-no-select");
      if (empty) empty.style.display = "flex";
    }

    async function openSupportTicket(ticketId, silent) {
      _supportCurrentTicket = Number(ticketId);
      renderSupportList(_supportListRows);
      showSupportConv();
      var msgsBox = $("support-conv-msgs");
      if (!msgsBox) return;
      if (!silent) {
        msgsBox.innerHTML =
          '<p class="sub">' + escHtml(tr("加载中…", "Loading…")) + "</p>";
      }
      try {
        var r = await AI24X_API.supportTicketDetail(ticketId);
        var t = (r && r.ticket) || {};
        var head = $("support-conv-head");
        if (head) {
          head.innerHTML =
            "<div><strong>" + escHtml(t.subject || "#" + t.id) + "</strong>" +
              '<span class="support-status ' + escHtml(t.status || "open") + '">' +
                escHtml(supportStatusLabel(t.status)) +
              "</span></div>" +
            '<div class="sub">' +
              escHtml(supportCatLabel(t.category)) + " · #" + Number(t.id) +
            "</div>";
        }
        renderSupportMessages(t);
      } catch (e) {
        if (!silent) {
          msgsBox.innerHTML =
            '<p class="sub">' +
            escHtml((e && e.message) || tr("加载失败，请稍后重试", "Failed to load — please retry")) +
            "</p>";
        }
      }
    }

    async function loadSupportTickets() {
      if (!AI24X_API || typeof AI24X_API.supportTicketList !== "function") return;
      try {
        var r = await AI24X_API.supportTicketList(50, 0);
        renderSupportList((r && r.rows) || []);
        if (_supportCurrentTicket) {
          var still = _supportListRows.some(function (t) {
            return Number(t.id) === Number(_supportCurrentTicket);
          });
          if (still) openSupportTicket(_supportCurrentTicket, true);
        }
      } catch (e) {
        var box = $("support-list");
        if (box) {
          box.innerHTML =
            '<p class="sub">' +
            escHtml((e && e.message) || tr("加载失败，请稍后重试", "Failed to load — please retry")) +
            "</p>";
        }
      }
    }

    async function submitSupportNew() {
      var bodyEl = $("support-new-body");
      var msgEl = $("support-new-msg");
      if (!bodyEl || !msgEl) return;
      var body = (bodyEl.value || "").trim();
      if (body.length < 10) {
        msgEl.innerHTML =
          '<div class="alert alert-error">' +
          escHtml(tr("请把问题写清楚一些（至少 10 个字）。", "Please describe the issue in a little more detail (at least 10 characters).")) +
          "</div>";
        return;
      }
      var cat = (($("support-new-cat") && $("support-new-cat").value) || "api").trim();
      var btn = $("support-new-submit");
      if (btn) btn.disabled = true;
      msgEl.innerHTML = '<div class="alert">' + escHtml(tr("提交中…", "Submitting…")) + "</div>";
      try {
        var r = await AI24X_API.supportTicketCreate({ category: cat, body: body });
        if (!r || !r.ok || !r.ticket) {
          throw new Error((r && r.message) || tr("提交失败", "Submit failed"));
        }
        bodyEl.value = "";
        msgEl.innerHTML = "";
        var nb = $("support-new-box");
        if (nb) nb.style.display = "none";
        await loadSupportTickets();
        openSupportTicket(Number(r.ticket.id));
      } catch (e) {
        msgEl.innerHTML =
          '<div class="alert alert-error">' +
          escHtml((e && e.message) || tr("提交失败", "Submit failed")) +
          "</div>";
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function sendSupportReply() {
      if (!_supportCurrentTicket) return;
      var input = $("support-reply-input");
      if (!input) return;
      var text = (input.value || "").trim();
      if (!text) return;
      var btn = $("support-reply-send");
      if (btn) btn.disabled = true;
      try {
        var r = await AI24X_API.supportTicketReply(_supportCurrentTicket, text);
        if (!r || !r.ok || !r.ticket) {
          throw new Error((r && r.message) || tr("发送失败", "Failed to send"));
        }
        input.value = "";
        renderSupportMessages(r.ticket);
        loadSupportTickets().catch(function () {});
      } catch (e) {
        var msgsBox = $("support-conv-msgs");
        if (msgsBox) {
          var div = document.createElement("div");
          div.className = "alert alert-error";
          div.textContent = (e && e.message) || tr("发送失败", "Failed to send");
          msgsBox.appendChild(div);
          msgsBox.scrollTop = msgsBox.scrollHeight;
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function bindSupportPanel() {
      var btnNew = $("btn-support-new");
      if (btnNew) {
        btnNew.addEventListener("click", function () {
          var empty = $("support-no-select");
          if (empty) empty.style.display = "none";
          var conv = $("support-conv-box");
          if (conv) conv.style.display = "none";
          var nb = $("support-new-box");
          if (nb) {
            nb.style.display = "block";
            var bodyEl = $("support-new-body");
            if (bodyEl) bodyEl.focus();
          }
        });
      }
      var btnCancel = $("support-new-cancel");
      if (btnCancel) btnCancel.addEventListener("click", showSupportEmpty);
      var btnSubmit = $("support-new-submit");
      if (btnSubmit) btnSubmit.addEventListener("click", submitSupportNew);
      var btnSend = $("support-reply-send");
      if (btnSend) btnSend.addEventListener("click", sendSupportReply);
      var input = $("support-reply-input");
      if (input) {
        input.addEventListener("keydown", function (ev) {
          if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            sendSupportReply();
          }
        });
      }
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
      // 2026-08-09: 余额按语言展示——中文界面人民币(¥)，英文及其它语言美元($)
      var usd = Number(bal.balance_usd) || 0;
      var fx = Number(bal.usd_cny) || 7.2;
      var usdDisplay = tr(
        bal.balance_cny_display || "¥" + (usd / 100 * fx).toFixed(2),
        "$" + (usd / 100).toFixed(2)
      );
      var planIsFree = String(bal.plan || "").toLowerCase() === "free";
      var isVip = !!bal.is_vip_active;
      var vpLine = $("vp-active-line");
      if (vpLine) vpLine.style.display = bal.is_value_pack_active ? "" : "none";
      window.__isValuePackActive = !!bal.is_value_pack_active;
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
            btnBill.textContent = tr("去选套餐", "Choose a plan");
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
            btnBill.textContent = tr("去选套餐", "Choose a plan");
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
            btnBill.textContent = tr("去选套餐", "Choose a plan");
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
      if ($("overview-invite-code")) $("overview-invite-code").textContent = ref.code || "--";
      if ($("overview-invite-link")) {
        var ovSl =
          window.AI24X_INVITE && ref.code
            ? AI24X_INVITE.shortLink(ref.code)
            : ref.code
              ? location.origin + "/r/" + encodeURIComponent(ref.code)
              : "--";
        $("overview-invite-link").textContent = ovSl || "--";
      }
      if ($("overview-invite-l1")) {
        $("overview-invite-l1").textContent = String(ref.invitees_l1 != null ? ref.invitees_l1 : 0);
      }
      if ($("overview-invite-earned")) {
        var earnedOv = ref.earned_tokens != null ? Number(ref.earned_tokens) : 0;
        $("overview-invite-earned").textContent = earnedOv >= 1000 ? (earnedOv / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(earnedOv);
      }
    } catch (e) {
      $("stat-referrals").textContent = "--";
    }

    try {
      await loadInvitees();
    } catch (e) {}

    try {
      bindTransactionsControls();
    } catch (e) {}

    try {
      var plans = await AI24X_API.billingPlans();
      renderPlans(plans);
    } catch (e) {}

    try {
      var orders = await AI24X_API.billingOrders(20);
      renderOrders((orders && orders.rows) || []);
    } catch (e) {}

    try {
      loadMarketsSub();
    } catch (e) {}
  }

  /** Markets Pro 订阅状态（与 Token 充值是两套体系，独立直连 markets 后端展示） */
  function marketsApiBase() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      if (h === "127.0.0.1" || h === "localhost") return "http://127.0.0.1:18012";
    } catch (e) {}
    return "https://markets.ai24x.com";
  }

  function loadMarketsSub() {
    try {
      var token = "";
      try { token = localStorage.getItem("ai24x_auth_token") || ""; } catch (e) {}
      var lines = document.querySelectorAll(".markets-sub-line");
      var statuses = document.querySelectorAll(".markets-sub-status");
      var ctas = document.querySelectorAll(".markets-sub-cta");
      if (!lines.length || !statuses.length) return;
      if (!token) {
        lines.forEach(function (ln) { ln.style.display = "none"; });
        return;
      }
      lines.forEach(function (ln) { ln.style.display = ""; });
      statuses.forEach(function (st) {
        st.textContent = tr("正在检查 Markets Pro 订阅…", "Checking Markets Pro subscription…");
      });
      fetch(marketsApiBase() + "/api/subscribe/status", {
        headers: { Authorization: "Bearer " + token }
      })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j && j.code === 0 && j.data) {
            var pro = !!j.data.pro;
            var ds = "--";
            if (j.data.expires_at) {
              var d = new Date(j.data.expires_at);
              if (!isNaN(d.getTime())) { try { ds = d.toLocaleDateString(); } catch (e) {} }
            }
            var text = pro
              ? tr("Pro 生效中 — 到期 " + ds, "Pro active — expires " + ds)
              : tr("当前免费版 — 每天 3 次 AI 点评、自选 3 只。", "Free plan — 3 AI briefs/day, 3-symbol watchlist.");
            statuses.forEach(function (st) { st.textContent = text; });
            ctas.forEach(function (cta) {
              cta.textContent = pro ? tr("管理 / 续费订阅", "Manage / renew") : tr("升级 Pro", "Upgrade to Pro");
              cta.setAttribute("data-i18n", pro ? "page.console.markets.manage" : "page.console.markets.upgrade");
            });
          } else {
            statuses.forEach(function (st) {
              st.textContent = tr("订阅状态暂不可用，可直接到 Markets 页面查看。", "Subscription status unavailable — check inside Markets.");
            });
          }
        })
        .catch(function () {
          statuses.forEach(function (st) {
            st.textContent = tr("订阅状态暂不可用，可直接到 Markets 页面查看。", "Subscription status unavailable — check inside Markets.");
          });
        });
    } catch (e) {}
  }

  /** Billing 面板直接开通 Markets Pro（复用 markets checkout → PayPal 跳转） */
  function doMarketsCheckout(plan) {
    try {
      var token = "";
      try { token = localStorage.getItem("ai24x_auth_token") || ""; } catch (e) {}
      var msgs = document.querySelectorAll(".mk-checkout-msg");
      msgs.forEach(function (m) { m.textContent = ""; });
      if (!token) {
        location.href = "login.html?next=" + encodeURIComponent("console.html#billing");
        return;
      }
      msgs.forEach(function (m) { m.textContent = tr("正在跳转 PayPal…", "Redirecting to PayPal…"); });
      fetch(marketsApiBase() + "/api/subscribe/checkout", {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({ plan: plan })
      })
        .then(function (r) { return r.json().then(function (j) { return { status: r.status, j: j }; }); })
        .then(function (res) {
          var j = res.j || {};
          if (res.status === 401) { location.href = "login.html?next=" + encodeURIComponent("console.html#billing"); return; }
          if (res.status !== 200 || j.code !== 0 || !j.data || !j.data.pay_url) {
            msgs.forEach(function (m) { m.textContent = tr("无法发起支付：", "Unable to start checkout: ") + (j.msg || res.status); });
            return;
          }
          location.href = j.data.pay_url;
        })
        .catch(function (e) { msgs.forEach(function (m) { m.textContent = tr("无法发起支付：", "Unable to start checkout: ") + String(e); }); });
    } catch (e) {}
  }

  var CONSOLE_PANELS = [
    "overview",
    "keys",
    "billing",
    "transactions",
    "playground",
    "invite",
    "account",
    "support",
  ];

  function normalizeConsolePanel(name) {
    var n = String(name || "")
      .replace(/^#/, "")
      .trim()
      .toLowerCase();
    if (n === "token-plans" || n === "plans" || n === "orders") return "billing";
    if (n === "usage" || n === "activity" || n === "ledger") return "transactions";
    if (n === "bills" || n === "bill" || n === "tx" || n === "transactions") return "transactions";
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
    if (id === "invite") {
      loadInvitees().catch(function () {});
    }
      if (id === "transactions") {
        try {
          bindTransactionsControls();
        } catch (e) {}
      }
      if (id === "support") {
        try {
          loadSupportTickets();
        } catch (e) {}
      }

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
    var bMkM = $("btn-mk-month");
    if (bMkM) bMkM.addEventListener("click", function () { doMarketsCheckout("monthly"); });
    var bMkW = $("btn-mk-week");
    if (bMkW) bMkW.addEventListener("click", function () { doMarketsCheckout("weekly"); });
    var bMkY = $("btn-mk-year");
    if (bMkY) bMkY.addEventListener("click", function () { doMarketsCheckout("yearly"); });
    var bOvW = $("btn-ov-week");
    if (bOvW) bOvW.addEventListener("click", function () { doMarketsCheckout("weekly"); });
    var bOvM = $("btn-ov-month");
    if (bOvM) bOvM.addEventListener("click", function () { doMarketsCheckout("monthly"); });
    var bOvY = $("btn-ov-year");
    if (bOvY) bOvY.addEventListener("click", function () { doMarketsCheckout("yearly"); });
    try {
      bindSupportPanel();
    } catch (e) {}
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
              var promptText = ($("chat-prompt").value || "").trim();
              var pureHi = /^(hi|hello|hey|你好|您好|哈喽|嗨)[!！?？.。…\s]*$/i.test(
                promptText
              );
              var safe = pureHi
                ? tr(
                    "你好！我是 AI24X 助手，有什么可以帮你的？",
                    "Hello! I'm the AI24X assistant. How can I help you today?"
                  )
                : tr(
                    "免费共享通道暂时繁忙。请稍后再试；产品用法可点右下角即时帮助，或改用 flash / auto（需余额）测质量。",
                    "Free shared is busy. Try again shortly; for product Q&A use Instant Help, or flash/auto when you have balance."
                  );
              r = Object.assign({}, r, { response: safe });
              out.textContent = formatChatOut(r, requested);
              showMsg(
                chatMsg,
                tr(
                  "共享通道已换稳妥提示。产品问题请用右下角即时帮助。",
                  "Shared channel used a safe tip. For product Q&A, use Instant Help."
                ),
                true
              );
            } else {
              out.textContent = formatChatOut(r, requested);
              if (requested === "shared") {
                showMsg(
                  chatMsg,
                  tr(
                    "免费共享连通正常。测质量请改 flash/auto（需余额）；产品对比用右下角即时帮助。",
                    "Shared connectivity OK. Use flash/auto for quality (needs balance); Instant Help for product Q&A."
                  ),
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
    function copyInviteLink() {
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
    }
    function copyInviteCode() {
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
    }
    var btnInv = $("btn-copy-invite-link");
    if (btnInv) btnInv.addEventListener("click", copyInviteLink);
    var btnCode = $("btn-copy-invite-code");
    if (btnCode) btnCode.addEventListener("click", copyInviteCode);
    var btnOvLink = $("btn-copy-invite-link-ov");
    if (btnOvLink) btnOvLink.addEventListener("click", copyInviteLink);
    var btnOvCode = $("btn-copy-invite-code-ov");
    if (btnOvCode) btnOvCode.addEventListener("click", copyInviteCode);
    var btnChangePass = $("btn-change-password");
    if (btnChangePass) {
      btnChangePass.addEventListener("click", function () {
        var box = $("acct-pass-msg");
        if (!box) return;
        var oldP = ($("acct-old-pass") && $("acct-old-pass").value) || "";
        var newP = ($("acct-new-pass") && $("acct-new-pass").value) || "";
        var newP2 = ($("acct-new-pass2") && $("acct-new-pass2").value) || "";
        if (!oldP) {
          box.innerHTML = '<div class="alert alert-error">' + tr("请输入当前密码", "Enter your current password") + "</div>";
          return;
        }
        if (newP.length < 8) {
          box.innerHTML = '<div class="alert alert-error">' + tr("新密码至少 8 位", "New password must be at least 8 characters") + "</div>";
          return;
        }
        if (newP !== newP2) {
          box.innerHTML = '<div class="alert alert-error">' + tr("两次输入的新密码不一致", "Passwords do not match") + "</div>";
          return;
        }
        btnChangePass.disabled = true;
        box.innerHTML = "";
        AI24X_API.authPasswordChange({ old_password: oldP, new_password: newP })
          .then(function () {
            if ($("acct-old-pass")) $("acct-old-pass").value = "";
            if ($("acct-new-pass")) $("acct-new-pass").value = "";
            if ($("acct-new-pass2")) $("acct-new-pass2").value = "";
            box.innerHTML = '<div class="alert alert-success">' + tr("密码已修改", "Password updated") + "</div>";
          })
          .catch(function (e) {
            box.innerHTML = '<div class="alert alert-error">' + (e.message || tr("修改密码失败", "Failed to update password")) + "</div>";
          })
          .finally(function () {
            btnChangePass.disabled = false;
          });
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
      if (qs.get("creem") === "1" && otn) {
        if (_fulfillPollTimer) {
          clearInterval(_fulfillPollTimer);
          _fulfillPollTimer = null;
        }
        showMsg(msgBox(), tr("正在确认 Creem 支付…", "Confirming Creem…"), true);
        AI24X_API.billingQueryFulfill(otn, "creem")
          .then(function (r) {
            showMsg(
              msgBox(),
              r && r.ok
                ? AI24X_API.planFulfillMessage(_lastPayPlanId, null)
                : tr(
                    "Creem 尚未完成，可在「我的订单」点确认到账",
                    "Creem pending — tap Confirm under My orders"
                  ),
              !!(r && r.ok)
            );
            return refreshAll();
          })
          .catch(function (e) {
            var msg = (e && e.message) || "";
            showMsg(
              msgBox(),
              (msg || tr("Creem 确认失败", "Creem confirm failed")) +
                tr(" — 请在「我的订单」点「确认到账」。", " — tap Confirm under My orders"),
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
