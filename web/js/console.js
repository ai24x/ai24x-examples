/**
 * 控制台：余额 / Keys / 套餐下单(mock) / 用量 / 邀请
 */
(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function tr(zh, en) {
    return AI24X_API.isZhUi() ? zh : en;
  }

  function fmtInt(v) {
    var n = Number(v);
    if (!isFinite(n)) return "--";
    return String(Math.round(n));
  }

  function labelEntryType(t) {
    if (!AI24X_API.isZhUi()) {
      var en = { consume: "Usage", topup: "Top-up", bonus: "Bonus", referral: "Referral" };
      return en[t] || t || "";
    }
    var m = {
      consume: "消耗",
      topup: "充值",
      bonus: "赠送",
      referral: "邀请奖励",
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
      token_vip_month_50w: "Scale 组合包",
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
      var en = { wechat: "WeChat", alipay: "Alipay", mock: "Mock" };
      return en[c] || c || "";
    }
    var m = { wechat: "微信", alipay: "支付宝", mock: "模拟" };
    return m[c] || c || "";
  }

  function humanizeLedgerNote(note) {
    var n = String(note || "");
    if (!n) return "";
    var zh = AI24X_API.isZhUi();
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
    if (/^(wechat|alipay|mock):/i.test(n)) {
      var parts = n.split(":");
      return (
        labelChannel(parts[0]) +
        (zh ? "支付到账" : " payment") +
        (parts[2] ? " · " + labelPlanForUi(parts[2]) : "")
      );
    }
    if (/vip_daily_bonus/i.test(n)) {
      return n.replace(/vip_daily_bonus/gi, zh ? "每日赠送额度" : "daily bonus");
    }
    return n;
  }

  function showMsg(el, text, ok) {
    if (!el) return;
    el.innerHTML =
      '<div class="alert ' +
      (ok ? "alert-success" : "alert-error") +
      '">' +
      String(text || "") +
      "</div>";
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

  function renderKeys(keys) {
    var box = $("keysList");
    var display = $("apiKeyDisplay");
    if (!box) return;
    box.innerHTML = "";
    if (!keys || !keys.length) {
      box.innerHTML =
        '<li class="list-item"><span>' +
        tr("暂无密钥", "No keys yet") +
        "</span><span></span></li>";
      if (display) display.textContent = "--";
      return;
    }
    keys.forEach(function (k) {
      var li = document.createElement("li");
      li.className = "list-item";
      var left = document.createElement("span");
      left.textContent =
        (k.name || tr("密钥", "Key")) + " · " + (k.key_prefix || "") + "…";
      var right = document.createElement("span");
      var btnUse = document.createElement("button");
      btnUse.type = "button";
      btnUse.className = "btn";
      btnUse.textContent = tr("用作调用", "Use for calls");
      btnUse.style.marginRight = "6px";
      btnUse.addEventListener("click", function () {
        showMsg(
          $("consoleMsg"),
          tr(
            "列表只显示前缀。完整 Key 仅创建时返回一次；若已保存可粘贴到上方「API Key」框。",
            "List shows prefixes only. The full key is returned once at creation — paste it into API Key above if you saved it."
          ),
          true
        );
      });
      var btnDel = document.createElement("button");
      btnDel.type = "button";
      btnDel.className = "btn";
      btnDel.textContent = tr("删除", "Delete");
      btnDel.addEventListener("click", function () {
        if (!confirm(tr("确认停用该 Key？", "Disable this key?"))) return;
        AI24X_API.keysDelete(k.id)
          .then(refreshAll)
          .catch(function (e) {
            showMsg($("consoleMsg"), e.message || tr("删除失败", "Delete failed"), false);
          });
      });
      right.appendChild(btnUse);
      right.appendChild(btnDel);
      li.appendChild(left);
      li.appendChild(right);
      box.appendChild(li);
    });
    if (display) {
      display.textContent =
        (keys[0].key_prefix || "") +
        "…" +
        tr("（完整密钥仅创建时可见）", " (full key shown only at creation)");
    }
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
        if (pay.enabled && (pay.wechat_ready || pay.alipay_ready)) {
          hint.textContent =
            "选择套餐后可用微信或支付宝支付。" +
            (pay.mock_allowed ? " 也可使用「模拟到账」。" : "");
        } else if (pay.wechat_configured || pay.alipay_configured) {
          hint.textContent = "在线支付准备中" + (pay.mock_allowed ? "，可用「模拟到账」。" : "。");
        } else if (pay.mock_allowed) {
          hint.textContent = "可用「模拟到账」完成体验充值。";
        } else {
          hint.textContent = "在线支付暂未开放。";
        }
      } else {
        hint.textContent = pay.enabled
          ? "Choose a plan and pay with WeChat or Alipay (CNY) on this site." +
            (pay.mock_allowed ? " Mock top-up is also available." : "")
          : pay.mock_allowed
            ? "Online pay is not open yet. Mock top-up is available."
            : "Online pay is not open yet.";
      }
    }
    if (!plans.length) {
      box.innerHTML = '<p class="sub">' + tr("暂无套餐", "No plans") + "</p>";
      return;
    }
    plans.forEach(function (p) {
      var card = document.createElement("div");
      card.className = "card";
      card.style.marginBottom = "10px";
      var h = document.createElement("h4");
      h.className = "mt-0";
      h.style.marginBottom = "6px";
      h.textContent = AI24X_API.planTitle(p);
      var meta = document.createElement("p");
      meta.className = "sub";
      meta.style.margin = "0";
      var bits = [AI24X_API.planPriceLabel(p)];
      if (p.credit_tokens) {
        bits.push((zh ? "到账 " : "") + p.credit_tokens + " token");
      }
      if (p.set_vip) {
        bits.push(
          zh
            ? "开通 Token VIP" + (p.vip_days ? " " + p.vip_days + " 天" : "")
            : "Token VIP" + (p.vip_days ? " " + p.vip_days + "d" : "")
        );
      }
      meta.textContent = bits.join(" · ");
      var actions = document.createElement("div");
      actions.className = "card-actions";
      actions.style.marginTop = "10px";

      function addBtn(label, cls, channel) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = cls;
        btn.textContent = label;
        btn.addEventListener("click", function () {
          buyPlan(p.plan, channel, p);
        });
        actions.appendChild(btn);
      }

      if (pay.wechat_ready) addBtn(tr("微信", "WeChat"), "btn btn-primary", "wechat");
      if (pay.alipay_ready) addBtn(tr("支付宝", "Alipay"), "btn btn-primary", "alipay");
      if (!pay.wechat_ready && !pay.alipay_ready) {
        addBtn(tr("下单", "Buy"), "btn btn-primary", pay.mock_allowed ? "mock" : "wechat");
      } else if (pay.mock_allowed) {
        addBtn(tr("模拟到账", "Mock pay"), "btn", "mock");
      }

      card.appendChild(h);
      card.appendChild(meta);
      var noteText = AI24X_API.planNote(p);
      if (noteText) {
        var note = document.createElement("p");
        note.className = "sub";
        note.style.marginTop = "6px";
        note.textContent = noteText;
        card.appendChild(note);
      }
      card.appendChild(actions);
      box.appendChild(card);
    });
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
    root.classList.add("is-open");
    root.setAttribute("aria-hidden", "false");
  }

  function showPayResult(opts) {
    opts = opts || {};
    $("modal-pay-result").style.display = "block";
    $("modal-pay-result-hint").textContent = opts.hint || "";
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
  function openAlipayInNewWindow(payUrl) {
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

  function buyPlan(planId, channel, planMeta) {
    var pay = window.__tokenPay || {};
    var price = AI24X_API.planPriceLabel(planMeta) || "";
    var planTitle = AI24X_API.planTitle(planMeta) || planId;

    if (channel === "mock" || (!pay.wechat_ready && !pay.alipay_ready && pay.mock_allowed)) {
      showMsg($("consoleMsg"), tr("正在创建模拟订单…", "Creating mock order…"), true);
      AI24X_API.billingWechatNative(planId)
        .then(function (r) {
          showMsg(
            $("consoleMsg"),
            tr(
              "已创建 " + (r && r.out_trade_no) + "。请在「我的订单」点「模拟到账」。",
              "Created " + (r && r.out_trade_no) + ". Use Mock pay under My orders."
            ),
            true
          );
          return refreshAll();
        })
        .catch(function (e) {
          showMsg($("consoleMsg"), e.message || tr("下单失败", "Order failed"), false);
        });
      return;
    }

    var alipayWin = null;
    if (channel === "alipay") {
      try {
        alipayWin = window.open("about:blank", "_blank");
        if (alipayWin) {
          try {
            alipayWin.document.write(
              "<!doctype html><title>Alipay</title><p style='font:14px sans-serif;padding:24px'>" +
                tr("正在打开支付宝，请稍候…", "Opening Alipay…") +
                "</p>"
            );
          } catch (e) {}
        }
      } catch (e) {
        alipayWin = null;
      }
    }

    openPayModal(
      planTitle + (price ? " · " + price : ""),
      channel === "wechat"
        ? tr("正在拉起微信扫码…", "Preparing WeChat QR…")
        : channel === "alipay"
          ? tr("将在新窗口打开支付宝；本页控制台保留。", "Alipay opens in a new window; this console stays.")
          : tr("请选择支付方式", "Choose a payment method")
    );

    var req =
      channel === "alipay"
        ? AI24X_API.billingAlipayWap(planId)
        : AI24X_API.billingWechatNative(planId);

    req
      .then(function (r) {
        if (r && r.mock) {
          if (alipayWin && !alipayWin.closed) {
            try {
              alipayWin.close();
            } catch (e) {}
          }
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
              "请用微信扫码支付。付完后若余额未更新，可到「我的订单」点「确认到账」。单号：" +
                (r.out_trade_no || ""),
              "Scan with WeChat to pay. If balance does not update, tap Confirm under My orders. Order: " +
                (r.out_trade_no || "")
            ),
            qrData: r.code_url,
          });
        } else if (channel === "alipay" && r && r.pay_url) {
          var opened = false;
          if (alipayWin && !alipayWin.closed) {
            try {
              alipayWin.location.href = r.pay_url;
              opened = true;
            } catch (e) {
              opened = openAlipayInNewWindow(r.pay_url);
            }
          } else {
            opened = openAlipayInNewWindow(r.pay_url);
          }
          showPayResult({
            hint:
              (opened
                ? tr(
                    "已在新窗口打开支付宝，请在新窗口完成付款。",
                    "Alipay opened in a new window — finish payment there."
                  )
                : tr(
                    "若未自动弹出，请点下方按钮打开支付宝。",
                    "If no window opened, use the button below."
                  )) +
              tr(
                " 付完后回到本页，若余额未更新可到「我的订单」点「确认到账」。单号：",
                " Then return here; if balance is stale, tap Confirm under My orders. Order: "
              ) +
              (r.out_trade_no || ""),
            openUrl: r.pay_url,
            openLabel: tr("在新窗口打开支付宝", "Open Alipay in a new window"),
          });
        } else {
          if (alipayWin && !alipayWin.closed) {
            try {
              alipayWin.close();
            } catch (e) {}
          }
          showPayResult({
            hint: tr(
              "下单返回异常，请看控制台消息。单号：" + ((r && r.out_trade_no) || ""),
              "Unexpected order response. Order: " + ((r && r.out_trade_no) || "")
            ),
          });
        }
        return refreshAll();
      })
      .catch(function (e) {
        if (alipayWin && !alipayWin.closed) {
          try {
            alipayWin.close();
          } catch (err) {}
        }
        showPayResult({ hint: e.message || tr("下单失败", "Order failed") });
        showMsg($("consoleMsg"), e.message || tr("下单失败", "Order failed"), false);
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
        (o.channel ? " · " + labelChannel(o.channel) : "");
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
                showMsg($("consoleMsg"), tr("模拟到账成功", "Mock pay OK"), true);
                return refreshAll();
              })
              .catch(function (e) {
                showMsg($("consoleMsg"), e.message || tr("模拟失败", "Mock failed"), false);
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
                $("consoleMsg"),
                r && r.ok
                  ? tr("查单履约成功", "Payment confirmed")
                  : tr("尚未支付成功", "Not paid yet"),
                !!(r && r.ok)
              );
              return refreshAll();
            })
            .catch(function (e) {
              showMsg($("consoleMsg"), e.message || tr("查单失败", "Query failed"), false);
            });
        });
        right.appendChild(btnQ);
      } else {
        right.textContent = o.out_trade_no || "";
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
        (r.model ? " · " + r.model : "") +
        (r.note ? " · " + humanizeLedgerNote(r.note) : "");
      var right = document.createElement("span");
      right.textContent = (r.amount > 0 ? "+" : "") + String(r.amount);
      li.appendChild(left);
      li.appendChild(right);
      box.appendChild(li);
    });
  }

  async function refreshAll() {
    if (!requireLogin()) return;
    var user = AI24X_API.getAuthUser() || {};
    $("acct-user").textContent = user.email || user.phone || user.id || "--";
    var phoneUnset =
      (window.AI24X_I18N && AI24X_I18N.t && AI24X_I18N.t("page.console.phoneUnset")) ||
      tr("未绑定", "Not bound");
    $("acct-phone").textContent = user.phone || phoneUnset;

    try {
      var bal = await AI24X_API.billingBalance();
      $("stat-balance").textContent = fmtInt(bal.balance_tokens);
      var planLabel = labelPlanForUi(bal.plan);
      if (bal.is_vip_active && bal.vip_expires_at) {
        planLabel +=
          tr(" · 到期 ", " · expires ") + String(bal.vip_expires_at).slice(0, 10);
      } else if (String(bal.plan || "").toLowerCase() === "vip" && !bal.is_vip_active) {
        planLabel = tr("免费档（Token VIP 已过期）", "Free (Token VIP expired)");
      }
      $("acct-plan").textContent = planLabel;
    } catch (e) {
      if (e && e.status === 401) {
        AI24X_API.clearAuth();
        requireLogin();
        return;
      }
      showMsg($("consoleMsg"), e.message || tr("余额加载失败", "Failed to load balance"), false);
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
    } catch (e) {
      $("stat-referrals").textContent = "--";
    }

    try {
      var usage = await AI24X_API.billingUsage({ limit: 30 });
      var rows = (usage && usage.rows) || [];
      var consumes = rows.filter(function (r) {
        return r.entry_type === "consume";
      }).length;
      $("stat-calls").textContent = String(consumes);
      renderUsage(rows);
    } catch (e) {
      $("stat-calls").textContent = "--";
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

  function bind() {
    var btnLogout = $("btn-logout");
    if (btnLogout) {
      btnLogout.addEventListener("click", function () {
        AI24X_API.clearAuth();
        location.href = "login.html";
      });
    }
    $("btn-save-api").addEventListener("click", function () {
      var b = $("api-base").value.trim();
      var k = $("api-key").value.trim();
      if (b) AI24X_API.setBase(b);
      else AI24X_API.setBase("");
      if (k) AI24X_API.setApiKey(k);
      else AI24X_API.setApiKey("");
      showMsg($("consoleMsg"), tr("已保存 API 设置", "API settings saved"), true);
    });
    $("btn-refresh").addEventListener("click", function () {
      refreshAll();
    });
    function openModal(id) {
      var el = $(id);
      if (!el) return;
      el.classList.add("is-open");
      el.setAttribute("aria-hidden", "false");
    }
    function closeModal(id) {
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
    $("btn-create-key").addEventListener("click", function () {
      var inp = $("create-key-name");
      if (inp && !(inp.value || "").trim()) inp.value = defaultKeyName();
      openModal("modal-create-key");
      if (inp) {
        setTimeout(function () {
          inp.focus();
          inp.select();
        }, 0);
      }
    });
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
              if ($("apiKeyDisplay")) $("apiKeyDisplay").textContent = r.api_key;
              if ($("modal-show-key-value")) $("modal-show-key-value").textContent = r.api_key;
              openModal("modal-show-key");
              showMsg(
                $("consoleMsg"),
                tr("密钥已创建，请复制保存。", "Key created — copy and save it."),
                true
              );
            }
            return refreshAll();
          })
          .catch(function (e) {
            showMsg($("consoleMsg"), e.message || tr("创建失败", "Create failed"), false);
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
              showMsg($("consoleMsg"), tr("已复制到剪贴板", "Copied to clipboard"), true);
            },
            function () {
              showMsg(
                $("consoleMsg"),
                tr("复制失败，请手动选择下方密钥", "Copy failed — select the key manually"),
                false
              );
            }
          );
        }
      });
    }
    $("btn-copy-key").addEventListener("click", function () {
      var t = ($("api-key").value || $("apiKeyDisplay").textContent || "").trim();
      if (!t || t === "--" || t.indexOf("…") >= 0) {
        showMsg(
          $("consoleMsg"),
          tr(
            "没有可复制的完整 Key（创建后会出现在输入框）",
            "No full key to copy (it appears in the input after creation)"
          ),
          false
        );
        return;
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(t).then(
          function () {
            showMsg($("consoleMsg"), tr("已复制", "Copied"), true);
          },
          function () {
            showMsg($("consoleMsg"), tr("复制失败，请手动选择", "Copy failed — select manually"), false);
          }
        );
      }
    });
    var btnChat = $("btn-chat-run");
    if (btnChat) {
      btnChat.addEventListener("click", function () {
        var out = $("chat-out");
        var key = ($("api-key").value || AI24X_API.getApiKey() || "").trim();
        if (!key) {
          showMsg(
            $("consoleMsg"),
            tr("请先创建并保存 API Key", "Create and save an API key first"),
            false
          );
          return;
        }
        AI24X_API.setApiKey(key);
        out.textContent = tr("请求中…", "Requesting…");
        AI24X_API.chatRun({
          prompt: ($("chat-prompt").value || "").trim() || tr("你好", "Hello"),
          model: ($("chat-model").value || "auto").trim() || "auto",
        })
          .then(function (r) {
            out.textContent = JSON.stringify(r, null, 2);
            return refreshAll();
          })
          .catch(function (e) {
            out.textContent = e.message || tr("失败", "Failed");
            showMsg($("consoleMsg"), e.message || tr("chat 失败", "chat failed"), false);
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
    var langSel = document.getElementById("lang-select");
    if (langSel) {
      langSel.addEventListener("change", function () {
        refreshAll();
      });
    }
  });
})();
