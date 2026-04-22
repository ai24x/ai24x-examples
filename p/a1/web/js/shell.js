/**
 * AI 行情官（p/a/web）统一页眉 / 页脚（轻量版，无 i18n 依赖）
 */
(function (global) {
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function headerHtml(active) {
    function nav(href, label, id) {
      var cls = active === id ? "is-active" : "";
      return '<a href="' + esc(href) + '" class="' + cls + '">' + esc(label) + "</a>";
    }

    return (
      '<div class="container header-inner">' +
      '<a class="brand" href="index.html" aria-label="AI24X">' +
      '<span class="brand-mark">AI</span>' +
      "<span>AI 行情官｜灯塔版</span>" +
      "</a>" +
      '<button type="button" class="menu-toggle" id="menu-toggle" aria-label="Menu" aria-expanded="false"><span></span></button>' +
      '<nav class="nav-main" id="nav-main" aria-label="Main">' +
      nav("index.html", "首页", "index") +
      nav("demo.html", "行情", "demo") +
      nav("partner.html", "代理", "partner") +
      nav("account.html", "我的", "account") +
      nav("feedback.html", "反馈", "feedback") +
      "</nav>" +
      '<div class="header-actions">' +
      '<select id="theme-select" class="select-mini" aria-label="Theme">' +
      '<option value="calm">深蓝（默认）</option>' +
      '<option value="dark">深黑</option>' +
      '<option value="light">蓝白</option>' +
      "</select>" +
      '<a class="btn btn-ghost" href="account.html">登录/续期</a>' +
      '<a class="btn btn-primary" href="account.html#vip">开通 VIP</a>' +
      "</div>" +
      "</div>"
    );
  }

  function footerHtml() {
    return (
      '<div class="container">' +
      '<div class="footer-grid">' +
      '<div class="footer-col">' +
      '<div class="footer-title">AI24X · AI 行情官｜灯塔版（V1.01）</div>' +
      '<div class="mt-2">行情与指标，一目了然</div>' +
      '<div class="mt-2" style="font-size:12px; opacity:.85">仅供学习研究，不构成投资建议；投资有风险，决策需谨慎。</div>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title">产品</div>' +
      '<a href="demo.html">行情与信号</a>' +
      '<a href="account.html">用户中心</a>' +
      '<a href="feedback.html">意见反馈</a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title">服务</div>' +
      '<a href="account.html#vip">开通 VIP</a>' +
      '<a href="account.html#invite">邀请奖励</a>' +
      '<a href="partner.html">代理合作</a>' +
      "</div>" +
      '<div class="footer-col">' +
      '<div class="footer-title">合规</div>' +
      '<a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">浙ICP备10040624号-7</a>' +
      "</div>" +
      "</div>" +
      '<div class="footer-bottom">© 2026 AI24X</div>' +
      "</div>"
    );
  }

  function bindChrome() {
    var toggle = document.getElementById("menu-toggle");
    var nav = document.getElementById("nav-main");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    // Theme (shared with demo.html data-theme variables)
    try {
      var sel = document.getElementById("theme-select");
      if (sel) {
        var k = "ai24x_a_theme";
        var cur = "";
        try { cur = localStorage.getItem(k) || ""; } catch (e0) {}
        cur = String(cur || "").trim() || "calm";
        sel.value = cur;
        applyTheme(cur);
        sel.addEventListener("change", function () {
          var v = String(sel.value || "calm").trim() || "calm";
          try { localStorage.setItem(k, v); } catch (e1) {}
          applyTheme(v);
        });
      }
    } catch (e) {}

    // Service Worker update (avoid "Ctrl+F5 looks different" after deployments)
    try {
      if (!global.__AI24X_A_SW_INSTALLED && "serviceWorker" in navigator && String(location.protocol || "") !== "file:") {
        global.__AI24X_A_SW_INSTALLED = true;
        navigator.serviceWorker.register("./sw.js", { scope: "./", updateViaCache: "none" }).then(function (reg) {
          try {
            reg.update && reg.update();
            if (reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" });
          } catch (e0) {}
        }).catch(function () {});
        navigator.serviceWorker.addEventListener("controllerchange", function () {
          try { location.reload(); } catch (e1) {}
        });
      }
    } catch (e) {}
  }

  function applyTheme(t) {
    try {
      t = String(t || "").trim() || "calm";
      document.documentElement.setAttribute("data-theme", t);
    } catch (e) {}
  }

  function mount(activePage) {
    var h = document.getElementById("site-header");
    var f = document.getElementById("site-footer");
    if (h) h.innerHTML = headerHtml(activePage);
    if (f) f.innerHTML = footerHtml();
    bindChrome();
  }

  global.AI24X_A_SHELL = { mount: mount, applyTheme: applyTheme };
})(typeof window !== "undefined" ? window : this);

