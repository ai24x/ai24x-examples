/**
 * 控制台：余额 / Keys / 套餐下单(mock) / 用量 / 邀请
 */
(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function fmtInt(v) {
    var n = Number(v);
    if (!isFinite(n)) return "--";
    return String(Math.round(n));
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

  function renderKeys(keys) {
    var box = $("keysList");
    var display = $("apiKeyDisplay");
    if (!box) return;
    box.innerHTML = "";
    if (!keys || !keys.length) {
      box.innerHTML = '<li class="list-item"><span>暂无密钥</span><span></span></li>';
      if (display) display.textContent = "--";
      return;
    }
    keys.forEach(function (k) {
      var li = document.createElement("li");
      li.className = "list-item";
      var left = document.createElement("span");
      left.textContent = (k.name || "密钥") + " · " + (k.key_prefix || "") + "…";
      var right = document.createElement("span");
      var btnUse = document.createElement("button");
      btnUse.type = "button";
      btnUse.className = "btn";
      btnUse.textContent = "用作调用";
      btnUse.style.marginRight = "6px";
      btnUse.addEventListener("click", function () {
        showMsg(
          $("consoleMsg"),
          "列表只显示前缀。完整 Key 仅创建时返回一次；若已保存可粘贴到上方「API Key」框。",
          true
        );
      });
      var btnDel = document.createElement("button");
      btnDel.type = "button";
      btnDel.className = "btn";
      btnDel.textContent = "删除";
      btnDel.addEventListener("click", function () {
        if (!confirm("确认停用该 Key？")) return;
        AI24X_API.keysDelete(k.id)
          .then(refreshAll)
          .catch(function (e) {
            showMsg($("consoleMsg"), e.message || "删除失败", false);
          });
      });
      right.appendChild(btnUse);
      right.appendChild(btnDel);
      li.appendChild(left);
      li.appendChild(right);
      box.appendChild(li);
    });
    if (display) {
      display.textContent = (keys[0].key_prefix || "") + "…（完整密钥仅创建时可见）";
    }
  }

  function renderPlans(data) {
    var box = $("plansList");
    if (!box) return;
    box.innerHTML = "";
    var plans = (data && data.plans) || [];
    var pay = (data && data.pay) || {};
    window.__tokenPay = pay;
    var hint = $("payHint");
    if (hint) {
      if (pay.enabled && (pay.wechat_ready || pay.alipay_ready)) {
        hint.textContent =
          "真支付已开启：点套餐可选微信 / 支付宝。" +
          (pay.mock_allowed ? " 本机仍保留「模拟到账」兜底。" : "");
      } else if (pay.wechat_configured || pay.alipay_configured) {
        hint.textContent =
          "商户已配置，但 TOKEN_PAY_ENABLED 未开——目前只能模拟到账。请开启真支付后刷新。";
      } else if (pay.mock_allowed) {
        hint.textContent = "本地模式：仅「模拟到账」（商户未就绪或未开真支付）。";
      } else {
        hint.textContent = "在线支付未开启。";
      }
    }
    if (!plans.length) {
      box.innerHTML = '<p class="sub">暂无套餐</p>';
      return;
    }
    plans.forEach(function (p) {
      var card = document.createElement("div");
      card.className = "card";
      card.style.marginBottom = "10px";
      var h = document.createElement("h4");
      h.className = "mt-0";
      h.style.marginBottom = "6px";
      h.textContent = p.title || p.plan;
      var meta = document.createElement("p");
      meta.className = "sub";
      meta.style.margin = "0";
      var bits = ["¥" + (p.price_yuan || "?")];
      if (p.credit_tokens) bits.push("到账 " + p.credit_tokens + " token");
      if (p.set_vip) bits.push("开通 Token VIP");
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

      if (pay.wechat_ready) addBtn("微信", "btn btn-primary", "wechat");
      if (pay.alipay_ready) addBtn("支付宝", "btn btn-primary", "alipay");
      if (!pay.wechat_ready && !pay.alipay_ready) {
        addBtn("下单", "btn btn-primary", pay.mock_allowed ? "mock" : "wechat");
      } else if (pay.mock_allowed) {
        addBtn("模拟到账", "btn", "mock");
      }

      card.appendChild(h);
      card.appendChild(meta);
      if (p.note) {
        var note = document.createElement("p");
        note.className = "sub";
        note.style.marginTop = "6px";
        note.textContent = p.note;
        card.appendChild(note);
      }
      card.appendChild(actions);
      box.appendChild(card);
    });
  }

  function openPayModal(title, sub) {
    var root = $("modal-pay");
    if (!root) return;
    $("modal-pay-title").textContent = title || "支付";
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
    if (opts.urlText) {
      urlBox.style.display = "block";
      urlBox.textContent = opts.urlText;
    } else {
      urlBox.style.display = "none";
    }
    if (openLink) {
      if (opts.openUrl) {
        openLink.href = opts.openUrl;
        openLink.style.display = "inline-block";
        openLink.textContent = opts.openLabel || "在新窗口打开";
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
    var title = (planMeta && planMeta.title) || planId;
    var price = (planMeta && planMeta.price_yuan) || "";

    if (channel === "mock" || (!pay.wechat_ready && !pay.alipay_ready && pay.mock_allowed)) {
      showMsg($("consoleMsg"), "正在创建模拟订单…", true);
      AI24X_API.billingWechatNative(planId)
        .then(function (r) {
          showMsg(
            $("consoleMsg"),
            "已创建 " + (r && r.out_trade_no) + "。请在「我的订单」点「模拟到账」。",
            true
          );
          return refreshAll();
        })
        .catch(function (e) {
          showMsg($("consoleMsg"), e.message || "下单失败", false);
        });
      return;
    }

    // 支付宝：点击瞬间先占住新窗口，URL 回来再导航（防弹窗拦截 / 防本页被顶掉）
    var alipayWin = null;
    if (channel === "alipay") {
      try {
        alipayWin = window.open("about:blank", "_blank");
        if (alipayWin) {
          try {
            alipayWin.document.write(
              "<!doctype html><title>正在打开支付宝…</title><p style='font:14px sans-serif;padding:24px'>正在打开支付宝，请稍候…</p>"
            );
          } catch (e) {}
        }
      } catch (e) {
        alipayWin = null;
      }
    }

    openPayModal(
      title + (price ? " · ¥" + price : ""),
      channel === "wechat"
        ? "正在拉起微信扫码…"
        : channel === "alipay"
          ? "将在新窗口打开支付宝；本页控制台保留。"
          : "请选择支付方式"
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
            hint:
              "当前仍为模拟单（" +
              (r.out_trade_no || "") +
              "）。请关闭后在订单列表点「模拟到账」，或确认已开启 TOKEN_PAY_ENABLED。",
          });
          return refreshAll();
        }
        if (channel === "wechat" && r && r.code_url) {
          showPayResult({
            hint:
              "请用微信扫码支付。本机回调可能收不到，付完后到「我的订单」点「查单补履约」。单号：" +
              (r.out_trade_no || ""),
            qrData: r.code_url,
            urlText: r.code_url,
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
                ? "已在新窗口打开支付宝。"
                : "若未自动弹出，请点下方「在新窗口打开支付宝」。") +
              " 付完后回到本页控制台，在「我的订单」点「查单补履约」。单号：" +
              (r.out_trade_no || ""),
            urlText: r.pay_url,
            openUrl: r.pay_url,
            openLabel: "在新窗口打开支付宝",
          });
        } else {
          if (alipayWin && !alipayWin.closed) {
            try {
              alipayWin.close();
            } catch (e) {}
          }
          showPayResult({
            hint: "下单返回异常，请看控制台消息。单号：" + ((r && r.out_trade_no) || ""),
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
        showPayResult({ hint: e.message || "下单失败" });
        showMsg($("consoleMsg"), e.message || "下单失败", false);
      });
  }

  function renderOrders(rows) {
    var box = $("ordersList");
    if (!box) return;
    box.innerHTML = "";
    if (!rows || !rows.length) {
      box.innerHTML = '<li class="list-item"><span>暂无订单</span><span></span></li>';
      return;
    }
    rows.forEach(function (o) {
      var li = document.createElement("li");
      li.className = "list-item";
      var left = document.createElement("span");
      left.textContent =
        (o.plan || "") +
        " · ¥" +
        ((Number(o.amount_fen) || 0) / 100).toFixed(2) +
        " · " +
        (o.status || "");
      var right = document.createElement("span");
      if (o.status === "pending") {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-primary";
        btn.textContent = "模拟到账";
        btn.addEventListener("click", function () {
          AI24X_API.billingMockFulfill(o.out_trade_no)
            .then(function () {
              showMsg($("consoleMsg"), "模拟到账成功", true);
              return refreshAll();
            })
            .catch(function (e) {
              showMsg($("consoleMsg"), e.message || "模拟失败", false);
            });
        });
        right.appendChild(btn);
        var btnQ = document.createElement("button");
        btnQ.type = "button";
        btnQ.className = "btn";
        btnQ.style.marginLeft = "6px";
        btnQ.textContent = "查单补履约";
        btnQ.addEventListener("click", function () {
          AI24X_API.billingQueryFulfill(o.out_trade_no, o.channel || "wechat")
            .then(function (r) {
              showMsg(
                $("consoleMsg"),
                r && r.ok ? "查单履约成功" : "尚未支付成功",
                !!(r && r.ok)
              );
              return refreshAll();
            })
            .catch(function (e) {
              showMsg($("consoleMsg"), e.message || "查单失败", false);
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
      box.innerHTML = '<li class="list-item"><span>暂无流水</span><span></span></li>';
      return;
    }
    rows.slice(0, 12).forEach(function (r) {
      var li = document.createElement("li");
      li.className = "list-item";
      var left = document.createElement("span");
      left.textContent =
        (r.entry_type || "") +
        (r.model ? " · " + r.model : "") +
        (r.note ? " · " + r.note : "");
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
    $("acct-phone").textContent = user.phone || "未绑定";

    try {
      var bal = await AI24X_API.billingBalance();
      $("stat-balance").textContent = fmtInt(bal.balance_tokens);
      var planLabel = bal.plan || "--";
      if (bal.is_vip_active && bal.vip_expires_at) {
        planLabel += " · 到期 " + String(bal.vip_expires_at).slice(0, 10);
      } else if (bal.plan === "vip" && !bal.is_vip_active) {
        planLabel = "free（VIP已过期）";
      }
      $("acct-plan").textContent = planLabel;
    } catch (e) {
      if (e && e.status === 401) {
        AI24X_API.clearAuth();
        requireLogin();
        return;
      }
      showMsg($("consoleMsg"), e.message || "余额加载失败", false);
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
      showMsg($("consoleMsg"), "已保存 API 设置", true);
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
      if (inp && !(inp.value || "").trim()) inp.value = "默认密钥";
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
        var name = (($("create-key-name") && $("create-key-name").value) || "").trim() || "默认密钥";
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
              showMsg($("consoleMsg"), "密钥已创建，请复制保存。", true);
            }
            return refreshAll();
          })
          .catch(function (e) {
            showMsg($("consoleMsg"), e.message || "创建失败", false);
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
              showMsg($("consoleMsg"), "已复制到剪贴板", true);
            },
            function () {
              showMsg($("consoleMsg"), "复制失败，请手动选择下方密钥", false);
            }
          );
        }
      });
    }
    $("btn-copy-key").addEventListener("click", function () {
      var t = ($("api-key").value || $("apiKeyDisplay").textContent || "").trim();
      if (!t || t === "--" || t.indexOf("…") >= 0) {
        showMsg($("consoleMsg"), "没有可复制的完整 Key（创建后会出现在输入框）", false);
        return;
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(t).then(
          function () {
            showMsg($("consoleMsg"), "已复制", true);
          },
          function () {
            showMsg($("consoleMsg"), "复制失败，请手动选择", false);
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
          showMsg($("consoleMsg"), "请先创建并保存 API Key", false);
          return;
        }
        AI24X_API.setApiKey(key);
        out.textContent = "请求中…";
        AI24X_API.chatRun({
          prompt: ($("chat-prompt").value || "").trim() || "你好",
          model: ($("chat-model").value || "auto").trim() || "auto",
        })
          .then(function (r) {
            out.textContent = JSON.stringify(r, null, 2);
            return refreshAll();
          })
          .catch(function (e) {
            out.textContent = e.message || "失败";
            showMsg($("consoleMsg"), e.message || "chat 失败", false);
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
  });
})();
