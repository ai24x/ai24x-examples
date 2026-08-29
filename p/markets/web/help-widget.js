/**
 * AI24X Markets · lightweight help widget (self-contained, no external deps)
 * Bottom-right floating button → help card with FAQ + quick links.
 * Language follows localStorage.markets_lang (same key as app.html).
 */
(function () {
  "use strict";

  var LS_KEY = "markets_lang";
  var OPEN_KEY = "mk_hw_open";
  var TIP_KEY = "mk_hw_tip_seen";

  var TEXTS = {
    en: {
      label: "Help",
      title: "How can we help?",
      lead: "Quick answers, help center and human tickets.",
      faqTitle: "Quick answers",
      linksTitle: "Useful links",
      faq: [
        {
          q: "What's included in the free plan?",
          a: "Charts, technical indicators, a limited number of AI briefs per day and a small watchlist. See the Help Center for the full Free vs Pro comparison."
        },
        {
          q: "How do I subscribe to Pro?",
          a: "Open the Pro panel in the app or the Pricing page, pick a plan (weekly / monthly / yearly), choose a payment method and Pro activates instantly."
        },
        {
          q: "Why is market data delayed?",
          a: "Market data is delayed at least 15 minutes. It is provided for educational purposes only and is not investment advice."
        },
        {
          q: "Something is not working. What now?",
          a: "Check the Help Center, open a ticket from your account, or email support@ai24x.com — we usually reply within one business day."
        }
      ],
      links: [
        { label: "Help Center & FAQ", href: "help" },
        { label: "Account & Billing", href: "billing" },
        { label: "Tickets", href: "support" },
        { label: "Pricing", href: "pricing" }
      ],
      ai: "Ask AI for instant help",
      contact: "Email us",
      tip: "Need help? Tap here.",
      close: "Close help",
      footer: "15-minute delayed market data · educational purposes only"
    },
    zh: {
      label: "帮助",
      title: "需要帮忙吗？",
      lead: "常见问题、帮助中心和人工工单。",
      faqTitle: "快速解答",
      linksTitle: "常用入口",
      faq: [
        {
          q: "免费版包含什么？",
          a: "K 线图表、技术指标、每日有限的 AI 技术简报和少量自选。完整 Free vs Pro 对比请看帮助中心。"
        },
        {
          q: "怎么订阅 Pro？",
          a: "在行情 App 的 Pro 面板或 Pricing 页面选择套餐（周 / 月 / 年），选好支付方式后立即生效。"
        },
        {
          q: "行情数据为什么有延迟？",
          a: "行情数据至少延迟 15 分钟，仅供教育用途，不构成投资建议。"
        },
        {
          q: "遇到问题怎么办？",
          a: "先看帮助中心；也可以从账户页提交工单，或发邮件到 support@ai24x.com，一般一个工作日内回复。"
        }
      ],
      links: [
        { label: "帮助中心与 FAQ", href: "help" },
        { label: "账户与套餐", href: "billing" },
        { label: "工单", href: "support" },
        { label: "定价", href: "pricing" }
      ],
      ai: "找 AI 即时帮助",
      contact: "发邮件给我们",
      tip: "需要帮助？点这里。",
      close: "关闭帮助",
      footer: "行情延迟 15 分钟 · 仅供教育用途"
    }
  };

  var HELP_SVG =
    '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
    '<path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16zm1-11.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm-1 3c.55 0 1 .45 1 1v3a1 1 0 1 1-2 0v-3c0-.55.45-1 1-1z"/>' +
    "</svg>";

  function lang() {
    try {
      return localStorage.getItem(LS_KEY) === "zh" ? "zh" : "en";
    } catch (e) {
      return "en";
    }
  }

  function t(k) {
    return (TEXTS[lang()] && TEXTS[lang()][k]) || TEXTS.en[k] || k;
  }

  function wwwBase() {
    if (typeof AI24X_WWW_BASE === "function") return AI24X_WWW_BASE();
    try {
      if (localStorage.getItem("ai24x_local_products") === "0") return "https://www.ai24x.com";
    } catch (e) {}
    var h = location.hostname || "";
    if (h === "localhost" || h === "127.0.0.1") return "http://127.0.0.1:8000";
    return "https://www.ai24x.com";
  }

  function hrefFor(key) {
    if (key === "pricing") return "/pricing.html";
    if (key === "billing") return wwwBase() + "/console.html#billing";
    if (key === "support") return wwwBase() + "/console.html#support";
    return "/help.html";
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function build() {
    var x = TEXTS[lang()];
    var faqHtml = x.faq
      .map(function (f, i) {
        return (
          '<div class="mk-hw-faq-item">' +
          '<button type="button" class="mk-hw-faq-q" data-faq="' + i + '" aria-expanded="false">' +
          esc(f.q) +
          '<span class="mk-hw-caret" aria-hidden="true"></span></button>' +
          '<div class="mk-hw-faq-a" hidden>' + esc(f.a) + "</div>" +
          "</div>"
        );
      })
      .join("");

    var linksHtml = x.links
      .map(function (l) {
        return (
          '<a class="mk-hw-link" href="' + hrefFor(l.href) + '"' +
          (l.href === "pricing" || l.href === "help" ? "" : ' target="_blank" rel="noopener"') +
          ">" + esc(l.label) + "</a>"
        );
      })
      .join("");

    var css =
      ".mk-hw-fab{position:fixed;right:16px;bottom:24px;z-index:400;width:52px;height:52px;border-radius:50%;border:1px solid var(--border,#2a3342);" +
      "background:var(--accent,#4f8cff);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;" +
      "box-shadow:0 6px 22px rgba(0,0,0,.45);transition:transform .15s ease,background .15s ease;}" +
      ".mk-hw-fab:hover{transform:translateY(-2px);filter:brightness(1.08);}" +
      ".mk-hw-panel{position:fixed;right:16px;bottom:88px;z-index:460;width:330px;max-width:calc(100vw - 24px);" +
      "max-height:min(74vh,600px);overflow:auto;background:var(--panel,#12161d);border:1px solid var(--border,#252b36);" +
      "border-radius:16px;box-shadow:0 18px 48px rgba(0,0,0,.55);color:var(--text,#d8dee9);font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;" +
      "font-size:13px;line-height:1.55;}" +
      ".mk-hw-panel[hidden]{display:none!important;}" +
      ".mk-hw-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:14px 16px 10px;border-bottom:1px solid var(--border,#252b36);}" +
      ".mk-hw-head h4{margin:0;font-size:15px;font-weight:700;}" +
      ".mk-hw-head p{margin:2px 0 0;color:var(--muted,#8b949e);font-size:12px;}" +
      ".mk-hw-close{flex:none;width:28px;height:28px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--muted,#8b949e);" +
      "cursor:pointer;font-size:16px;line-height:1;}" +
      ".mk-hw-close:hover{border-color:var(--border,#252b36);color:var(--text,#d8dee9);}" +
      ".mk-hw-body{padding:8px 16px 14px;}" +
      ".mk-hw-sec-title{margin:12px 0 6px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted,#8b949e);}" +
      ".mk-hw-faq-item{border:1px solid var(--border,#252b36);border-radius:10px;margin-bottom:7px;overflow:hidden;background:rgba(255,255,255,.02);}" +
      ".mk-hw-faq-q{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;padding:9px 11px;border:0;background:transparent;" +
      "color:var(--text,#d8dee9);font:inherit;font-weight:600;text-align:left;cursor:pointer;}" +
      ".mk-hw-faq-q:hover{background:rgba(255,255,255,.04);}" +
      ".mk-hw-caret{flex:none;width:7px;height:7px;border-right:1.5px solid var(--muted,#8b949e);border-bottom:1.5px solid var(--muted,#8b949e);" +
      "transform:rotate(45deg);transition:transform .15s ease;}" +
      ".mk-hw-faq-item.is-open .mk-hw-caret{transform:rotate(-135deg);}" +
      ".mk-hw-faq-a{padding:2px 11px 10px;color:var(--muted,#8b949e);font-size:12px;}" +
      ".mk-hw-links{display:flex;flex-direction:column;gap:6px;}" +
      ".mk-hw-link{display:block;padding:8px 11px;border:1px solid var(--border,#252b36);border-radius:10px;color:var(--accent,#4f8cff);" +
      "font-weight:600;text-decoration:none;background:rgba(255,255,255,.02);}" +
      ".mk-hw-link:hover{border-color:var(--accent,#4f8cff);text-decoration:none;background:rgba(79,140,255,.08);}" +
      ".mk-hw-ai{display:flex;align-items:center;gap:8px;margin-top:10px;padding:9px 11px;border-radius:10px;background:rgba(79,140,255,.12);" +
      "color:var(--text,#d8dee9);font-weight:600;text-decoration:none;}" +
      ".mk-hw-ai:hover{background:rgba(79,140,255,.2);text-decoration:none;}" +
      ".mk-hw-contact{display:inline-flex;align-items:center;gap:6px;margin-top:10px;color:var(--muted,#8b949e);font-size:12px;text-decoration:none;}" +
      ".mk-hw-contact:hover{color:var(--accent,#4f8cff);text-decoration:none;}" +
      ".mk-hw-foot{margin-top:12px;padding-top:10px;border-top:1px solid var(--border,#252b36);color:var(--muted,#8b949e);font-size:11px;}" +
      ".mk-hw-tip{position:fixed;right:72px;bottom:34px;z-index:390;max-width:210px;padding:8px 12px;border-radius:12px;background:var(--panel2,#181d26);" +
      "border:1px solid var(--border,#252b36);color:var(--text,#d8dee9);font-family:system-ui,sans-serif;font-size:12px;line-height:1.4;" +
      "box-shadow:0 8px 24px rgba(0,0,0,.4);}" +
      "@media(max-width:760px){.mk-hw-panel{right:12px;left:12px;margin:0 auto;bottom:84px;width:auto;}}" +
      ".mk-hw-ai svg,.mk-hw-contact svg{flex:none;}";

    var el = document.createElement("div");
    el.id = "mk-help-widget";
    el.innerHTML =
      "<style>" + css + "</style>" +
      '<button type="button" class="mk-hw-fab" id="mk-hw-fab" aria-label="' + esc(t("label")) + '" title="' + esc(t("label")) + '">' +
      HELP_SVG + "</button>" +
      '<div class="mk-hw-tip" id="mk-hw-tip" hidden>' + esc(t("tip")) + "</div>" +
      '<div class="mk-hw-panel" id="mk-hw-panel" role="dialog" aria-label="' + esc(t("title")) + '" hidden>' +
      '<div class="mk-hw-head">' +
      "<div><h4>" + esc(x.title) + "</h4><p>" + esc(x.lead) + "</p></div>" +
      '<button type="button" class="mk-hw-close" id="mk-hw-close" aria-label="' + esc(x.close) + '">×</button>' +
      "</div>" +
      '<div class="mk-hw-body">' +
      '<div class="mk-hw-sec-title">' + esc(x.faqTitle) + "</div>" + faqHtml +
      '<div class="mk-hw-sec-title">' + esc(x.linksTitle) + "</div>" +
      '<div class="mk-hw-links">' + linksHtml + "</div>" +
      '<a class="mk-hw-ai" href="/help.html#faq" rel="noopener">' +
      '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5.1-1.3A10 10 0 1 0 12 2zm0 18a8 8 0 0 1-4.1-1.1l-.3-.2-3 .8.8-3-.2-.3A8 8 0 1 1 12 20z"/></svg>' +
      esc(x.ai) + "</a>" +
      '<a class="mk-hw-contact" href="mailto:support@ai24x.com">' +
      '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"/></svg>' +
      esc(x.contact) + " · support@ai24x.com</a>" +
      '<div class="mk-hw-foot">' + esc(x.footer) + "</div>" +
      "</div>" +
      "</div>";
    document.body.appendChild(el);
    return el;
  }

  function bind(root) {
    var fab = root.querySelector("#mk-hw-fab");
    var panel = root.querySelector("#mk-hw-panel");
    var tip = root.querySelector("#mk-hw-tip");
    var close = root.querySelector("#mk-hw-close");
    var isOpen = false;
    try {
      isOpen = localStorage.getItem(OPEN_KEY) === "1";
    } catch (e) {}
    if (isOpen) openPanel();
    else if (!tipSeen()) showTip();

    fab.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (panel.hidden) openPanel();
      else closePanel();
    });
    close.addEventListener("click", closePanel);
    root.querySelectorAll(".mk-hw-faq-q").forEach(function (b) {
      b.addEventListener("click", function () {
        var item = b.closest(".mk-hw-faq-item");
        var a = item.querySelector(".mk-hw-faq-a");
        var open = a.hidden;
        a.hidden = !open;
        item.classList.toggle("is-open", open);
        b.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });
    document.addEventListener("click", function (ev) {
      if (!panel.hidden && !root.contains(ev.target)) closePanel();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !panel.hidden) closePanel();
    });
    var lift = function () {
      if (document.querySelector(".mb-bar")) {
        fab.style.bottom = "calc(78px + env(safe-area-inset-bottom))";
        tip.style.bottom = "calc(88px + env(safe-area-inset-bottom))";
      }
    };
    if (document.readyState !== "loading") lift();
    else document.addEventListener("DOMContentLoaded", lift);

    function tipSeen() {
      try {
        return localStorage.getItem(TIP_KEY) === "1";
      } catch (e) {
        return true;
      }
    }
    function showTip() {
      tip.hidden = false;
      setTimeout(function () {
        try {
          localStorage.setItem(TIP_KEY, "1");
        } catch (e) {}
        tip.hidden = true;
      }, 6000);
    }
    function openPanel() {
      panel.hidden = false;
      tip.hidden = true;
      isOpen = true;
      try {
        localStorage.setItem(OPEN_KEY, "1");
      } catch (e) {}
    }
    function closePanel() {
      panel.hidden = true;
      isOpen = false;
      try {
        localStorage.setItem(OPEN_KEY, "0");
      } catch (e) {}
    }
  }

  function init() {
    if (document.getElementById("mk-help-widget")) return;
    var root = build();
    bind(root);
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
