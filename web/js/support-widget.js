/**
 * 右侧客服浮钮：即时协助 + 转人工工单（控制台 / 帮助中心共用）
 */
(function (global) {
  "use strict";

  var TIP_KEY = "ai24x_sw_tip_seen_v1";
  var CHAT_SVG =
    '<svg class="sw-fab-ico" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
    '<path fill="currentColor" d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/>' +
    '<circle cx="8.5" cy="10" r="1.2" fill="currentColor"/>' +
    '<circle cx="12" cy="10" r="1.2" fill="currentColor"/>' +
    '<circle cx="15.5" cy="10" r="1.2" fill="currentColor"/>' +
    "</svg>";

  function tr(zh, en) {
    try {
      if (global.AI24X_I18N && typeof global.AI24X_I18N.isZh === "function" && !global.AI24X_I18N.isZh()) {
        return en;
      }
    } catch (e) {}
    return zh;
  }

  function pathPrefix() {
    try {
      var p = String(location.pathname || "");
      if (p.indexOf("/models/") >= 0 || p.indexOf("/guides/") >= 0) return "../";
    } catch (e) {}
    return "";
  }

  function $(id) {
    return document.getElementById(id);
  }

  function applyI18n(root) {
    try {
      if (global.AI24X_I18N && typeof global.AI24X_I18N.apply === "function") {
        global.AI24X_I18N.apply(root || document);
      }
    } catch (e0) {}
  }

  function loggedIn() {
    try {
      return !!(global.AI24X_API && AI24X_API.getAuthToken && AI24X_API.getAuthToken());
    } catch (e) {
      return false;
    }
  }

  function tipSeen() {
    try {
      return localStorage.getItem(TIP_KEY) === "1";
    } catch (e) {
      return true;
    }
  }

  function markTipSeen() {
    try {
      localStorage.setItem(TIP_KEY, "1");
    } catch (e) {}
    hideTip();
  }

  function hideTip() {
    var tip = $("sw-tip");
    if (tip) {
      tip.hidden = true;
      tip.setAttribute("aria-hidden", "true");
    }
  }

  function showTipOnce() {
    if (tipSeen()) return;
    var tip = $("sw-tip");
    if (!tip) return;
    tip.hidden = false;
    tip.setAttribute("aria-hidden", "false");
    setTimeout(function () {
      if (!tipSeen()) hideTip();
    }, 8000);
  }

  function setBackdrop(show) {
    var bd = $("sw-backdrop");
    if (bd) bd.hidden = !show;
  }

  function setKbOffset(px) {
    try {
      document.documentElement.style.setProperty("--sw-kb", Math.max(0, Math.round(px || 0)) + "px");
    } catch (e) {}
  }

  function clearKbOffset() {
    setKbOffset(0);
  }

  function syncKeyboardOffset() {
    var panel = $("sw-panel");
    if (!panel || panel.hidden) {
      clearKbOffset();
      return;
    }
    var vv = global.visualViewport;
    if (!vv) {
      clearKbOffset();
      return;
    }
    // 可视高度变矮 ≈ 软键盘占位；offsetTop 处理 iOS 视口上移
    var covered = Math.max(0, global.innerHeight - vv.height - vv.offsetTop);
    setKbOffset(covered > 48 ? covered : 0);
  }

  function bindViewportWatch() {
    var vv = global.visualViewport;
    if (!vv || vv.__ai24xSwBound) return;
    vv.__ai24xSwBound = true;
    var onChange = function () {
      syncKeyboardOffset();
    };
    vv.addEventListener("resize", onChange);
    vv.addEventListener("scroll", onChange);
    global.addEventListener("orientationchange", function () {
      setTimeout(syncKeyboardOffset, 200);
    });
  }

  function bindFieldFocus(root) {
    if (!root || root.__ai24xSwFocus) return;
    root.__ai24xSwFocus = true;
    root.addEventListener(
      "focusin",
      function (ev) {
        var t = ev.target;
        if (!t || !t.tagName) return;
        var tag = String(t.tagName).toLowerCase();
        if (tag !== "textarea" && tag !== "input" && tag !== "select") return;
        setTimeout(function () {
          syncKeyboardOffset();
          try {
            t.scrollIntoView({ block: "nearest", behavior: "smooth" });
          } catch (e2) {}
        }, 280);
      },
      true
    );
    root.addEventListener(
      "focusout",
      function () {
        setTimeout(syncKeyboardOffset, 180);
      },
      true
    );
  }

  function setMsg(text, ok) {
    var tmsg = $("sw-ticket-msg");
    if (!tmsg) return;
    tmsg.innerHTML =
      '<div class="alert ' +
      (ok ? "alert-success" : "alert-error") +
      '">' +
      String(text || "").replace(/</g, "&lt;") +
      "</div>";
  }

  function renderTickets() {
    var box = $("sw-ticket-list");
    if (!box || !global.AI24X_API || !AI24X_API.supportTicketList) return;
    if (!loggedIn()) {
      box.textContent = tr("登录后可查看工单", "Sign in to see tickets");
      return;
    }
    box.textContent = tr("加载中…", "Loading…");
    AI24X_API.supportTicketList(10, 0)
      .then(function (r) {
        var rows = (r && r.rows) || [];
        if (!rows.length) {
          box.textContent = tr("暂无工单", "No tickets yet");
          return;
        }
        box.innerHTML = rows
          .map(function (t) {
            var reply = t.admin_reply
              ? "<div class='sub' style='margin-top:4px;'>" +
                tr("回复：", "Reply: ") +
                String(t.admin_reply).replace(/</g, "&lt;") +
                "</div>"
              : "";
            return (
              "<div class='sw-ticket-row'>" +
              "<strong>#" +
              t.id +
              "</strong> [" +
              (t.status || "") +
              "] " +
              (t.category || "") +
              " · " +
              String(t.subject || "").replace(/</g, "&lt;") +
              reply +
              "</div>"
            );
          })
          .join("");
      })
      .catch(function (e) {
        box.textContent = (e && e.message) || tr("加载失败，请刷新重试", "Failed to load tickets");
      });
  }

  function openPanel(mode) {
    var panel = $("sw-panel");
    var fab = $("sw-fab");
    if (!panel) return;
    markTipSeen();
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
    if (fab) fab.setAttribute("aria-expanded", "true");
    document.body.classList.add("sw-open");
    setBackdrop(true);
    bindViewportWatch();
    bindFieldFocus(panel);
    if (mode === "ticket") {
      var box = $("sw-ticket-box");
      if (box) box.style.display = "block";
    }
    renderTickets();
    try {
      var q = $("sw-help-q");
      if (q) q.focus();
    } catch (e1) {}
    setTimeout(syncKeyboardOffset, 50);
  }

  function closePanel() {
    var panel = $("sw-panel");
    var fab = $("sw-fab");
    if (!panel) return;
    panel.hidden = true;
    panel.setAttribute("aria-hidden", "true");
    if (fab) fab.setAttribute("aria-expanded", "false");
    document.body.classList.remove("sw-open");
    setBackdrop(false);
    clearKbOffset();
  }

  function togglePanel() {
    var panel = $("sw-panel");
    if (!panel || panel.hidden) openPanel();
    else closePanel();
  }

  function inject() {
    if ($("sw-fab")) return;
    var wrap = document.createElement("div");
    wrap.id = "support-widget";
    wrap.innerHTML =
      '<div class="sw-fab-wrap">' +
      '<div class="sw-tip" id="sw-tip" role="status" hidden aria-hidden="true">' +
      '<span data-i18n="page.console.help.tip">有问题点这里</span>' +
      '<button type="button" class="sw-tip-x" id="sw-tip-x" aria-label="Dismiss">×</button>' +
      "</div>" +
      '<button type="button" class="sw-fab" id="sw-fab" aria-expanded="false" aria-controls="sw-panel" ' +
      'title="' +
      tr("即时协助", "Instant help") +
      '" aria-label="' +
      tr("即时协助", "Instant help") +
      '">' +
      CHAT_SVG +
      '<span class="sw-fab-label" data-i18n="page.console.help.fab">协助</span>' +
      "</button>" +
      "</div>" +
      '<div class="sw-backdrop" id="sw-backdrop" hidden></div>' +
      '<aside class="sw-panel card" id="sw-panel" role="dialog" aria-labelledby="sw-title" aria-hidden="true" hidden>' +
      '<div class="sw-panel-head">' +
      '<h3 class="mt-0" id="sw-title" data-i18n="page.console.help.title">即时协助</h3>' +
      '<button type="button" class="sw-close btn" id="sw-close" aria-label="Close">×</button>' +
      "</div>" +
      '<p class="sub" data-i18n="page.console.help.sub">接入 / 计费常见问题即时答（不扣你的 Token；有日帽）。</p>' +
      '<div class="form-group">' +
      '<textarea class="input" id="sw-help-q" rows="2" placeholder="How do I call flash with PayPal credits?"></textarea>' +
      "</div>" +
      '<div class="card-actions">' +
      '<button type="button" class="btn btn-primary" id="sw-btn-ask" data-i18n="page.console.help.send">提问</button>' +
      '<button type="button" class="btn" id="sw-btn-ticket" data-i18n="page.console.help.toHuman">转人工</button>' +
      '<a class="btn" href="' +
      pathPrefix() +
      'help.html" id="sw-link-faq" data-i18n="page.console.help.faq">帮助中心</a>' +
      "</div>" +
      '<pre id="sw-help-out" class="code-block mt-2" style="white-space:pre-wrap;min-height:60px;">--</pre>' +
      '<div id="sw-ticket-msg" class="mt-2" aria-live="polite"></div>' +
      '<div id="sw-ticket-box" class="mt-2 sw-ticket-box" style="display:none;">' +
      '<p class="sub" data-i18n="page.console.ticket.hint">仍未解决？提交工单，我们按工作日处理（不承诺秒回）。</p>' +
      '<div class="form-group"><label data-i18n="page.console.ticket.cat">分类</label>' +
      '<select class="input" id="sw-ticket-cat">' +
      '<option value="api">API / 调用</option>' +
      '<option value="billing">充值 / 账单</option>' +
      '<option value="account">账号</option>' +
      '<option value="suggestion">建议</option>' +
      '<option value="complaint">投诉</option>' +
      "</select></div>" +
      '<div class="form-group"><label data-i18n="page.console.ticket.body">问题描述</label>' +
      '<textarea class="input" id="sw-ticket-body" rows="3" data-i18n-placeholder="page.console.ticket.bodyPh" placeholder="请说明现象、大致时间与订单号（如有）"></textarea>' +
      "</div>" +
      '<div class="card-actions">' +
      '<button type="button" class="btn btn-primary" id="sw-btn-submit" data-i18n="page.console.ticket.submit">提交工单</button>' +
      "</div></div>" +
      '<div class="mt-2"><h4 class="mt-0" style="font-size:1rem;" data-i18n="page.console.ticket.mine">我的工单</h4>' +
      '<div id="sw-ticket-list" class="sub">--</div></div>' +
      "</aside>";
    document.body.appendChild(wrap);

    try {
      if (document.body && document.body.getAttribute("data-page") === "help") {
        var faq = $("sw-link-faq");
        if (faq) {
          faq.href = "#support";
          faq.textContent = tr("本页 FAQ", "Page FAQ");
        }
      }
    } catch (e2) {}

    applyI18n(wrap);

    $("sw-fab").addEventListener("click", function () {
      togglePanel();
    });
    $("sw-tip-x").addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      markTipSeen();
    });
    $("sw-close").addEventListener("click", closePanel);
    $("sw-backdrop").addEventListener("click", closePanel);

    $("sw-btn-ask").addEventListener("click", function () {
      var q = (($("sw-help-q") && $("sw-help-q").value) || "").trim();
      var out = $("sw-help-out");
      if (!q) {
        setMsg(tr("请输入问题", "Enter a question"), false);
        return;
      }
      if (!loggedIn()) {
        setMsg(tr("请先登录后再提问", "Please sign in to ask"), false);
        return;
      }
      out.textContent = tr("思考中…", "Thinking…");
      AI24X_API.supportAsk(q)
        .then(function (r) {
          out.textContent = (r && r.answer) || JSON.stringify(r);
          if (r && r.remaining_today != null) {
            out.textContent +=
              "\n\n(" +
              tr("今日剩余帮助次数 ", "Help remaining today ") +
              r.remaining_today +
              ")";
          }
        })
        .catch(function (e) {
          out.textContent = e.message || tr("失败", "Failed");
        });
    });

    $("sw-btn-ticket").addEventListener("click", function () {
      var box = $("sw-ticket-box");
      if (!box) return;
      box.style.display = box.style.display === "none" ? "block" : "none";
      var q = (($("sw-help-q") && $("sw-help-q").value) || "").trim();
      var out = (($("sw-help-out") && $("sw-help-out").textContent) || "").trim();
      var body = $("sw-ticket-body");
      if (body && !body.value && q) {
        body.value = q + (out && out !== "--" ? "\n\n---\n" + out.slice(0, 800) : "");
      }
    });

    $("sw-btn-submit").addEventListener("click", function () {
      var cat = (($("sw-ticket-cat") && $("sw-ticket-cat").value) || "api").trim();
      var body = (($("sw-ticket-body") && $("sw-ticket-body").value) || "").trim();
      var btn = $("sw-btn-submit");
      if (body.length < 10) {
        setMsg(tr("请把问题写清楚一些（至少 10 个字）", "Please describe the issue (10+ chars)"), false);
        return;
      }
      if (!loggedIn()) {
        setMsg(tr("请先登录后再提交工单", "Please sign in to submit a ticket"), false);
        return;
      }
      btn.disabled = true;
      setMsg(tr("提交中…", "Submitting…"), true);
      var helpOut = (($("sw-help-out") && $("sw-help-out").textContent) || "").trim();
      AI24X_API.supportTicketCreate({
        category: cat,
        body: body,
        ai_summary: helpOut && helpOut !== "--" ? helpOut.slice(0, 1500) : null,
      })
        .then(function (r) {
          var tid = r && r.ticket && r.ticket.id ? "#" + r.ticket.id : "";
          setMsg(tr("工单已提交 ", "Ticket submitted ") + tid, true);
          if ($("sw-ticket-body")) $("sw-ticket-body").value = "";
          if ($("sw-ticket-box")) $("sw-ticket-box").style.display = "none";
          renderTickets();
        })
        .catch(function (e) {
          setMsg(e.message || tr("提交失败", "Submit failed"), false);
        })
        .finally(function () {
          btn.disabled = false;
        });
    });

    try {
      var h = String(location.hash || "");
      if (h === "#help" || h === "#support") {
        setTimeout(function () {
          openPanel(h === "#support" ? "ticket" : null);
        }, 120);
      } else {
        setTimeout(showTipOnce, 900);
      }
    } catch (e3) {
      setTimeout(showTipOnce, 900);
    }
  }

  function init() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", inject);
    } else {
      inject();
    }
  }

  global.AI24X_SUPPORT_WIDGET = {
    open: openPanel,
    close: closePanel,
    refreshTickets: renderTickets,
  };

  init();
})(typeof window !== "undefined" ? window : this);
