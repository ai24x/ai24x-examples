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

    function navHidden(href, label, id) {
      var cls = active === id ? "is-active" : "";
      // Default-hide gated entries to avoid "flash then disappear".
      return '<a href="' + esc(href) + '" class="' + cls + '" style="display:none">' + esc(label) + "</a>";
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
      nav("account.html", "我的", "account") +
      navHidden("partner.html", "伙伴", "partner") +
      nav("feedback.html", "反馈", "feedback") +
      "</nav>" +
      '<div class="header-actions">' +
      '<select id="theme-select" class="select-mini" aria-label="Theme">' +
      '<option value="calm">深蓝</option>' +
      '<option value="dark">深黑</option>' +
      '<option value="light">蓝白（默认）</option>' +
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
      '<a href="partner.html">伙伴合作</a>' +
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
        cur = String(cur || "").trim() || "light";
        sel.value = cur;
        applyTheme(cur);
        sel.addEventListener("change", function () {
          var v = String(sel.value || "light").trim() || "light";
          try { localStorage.setItem(k, v); } catch (e1) {}
          applyTheme(v);
        });
      }
    } catch (e) {}

    // Service Worker update (avoid "Ctrl+F5 looks different" after deployments)
    try {
      if (!global.__AI24X_A_SW_INSTALLED && "serviceWorker" in navigator && String(location.protocol || "") !== "file:") {
        global.__AI24X_A_SW_INSTALLED = true;
        // Cache-bust SW URL so deployments don't require Ctrl+F5.
        // Use absolute paths so pages still work under subpaths like /i/{code}.
        navigator.serviceWorker.register("/sw.js?v=17", { scope: "/", updateViaCache: "none" }).then(function (reg) {
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
      t = String(t || "").trim() || "light";
      document.documentElement.setAttribute("data-theme", t);
    } catch (e) {}
  }

  function _el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null) return;
      if (k === "class") node.className = String(v);
      else if (k === "text") node.textContent = String(v);
      else if (k === "html") node.innerHTML = String(v);
      else node.setAttribute(k, String(v));
    });
    (children || []).forEach(function (c) {
      if (c == null) return;
      if (typeof c === "string") node.appendChild(document.createTextNode(c));
      else node.appendChild(c);
    });
    return node;
  }

  function headerDom(active) {
    function nav(href, label, id) {
      return _el(
        "a",
        { href: href, class: active === id ? "is-active" : "" },
        [String(label)]
      );
    }

    var wrap = _el("div", { class: "container header-inner" }, []);
    var brand = _el("a", { class: "brand", href: "index.html", "aria-label": "AI24X" }, [
      _el("span", { class: "brand-mark", text: "AI" }),
      _el("span", { text: "AI 行情官｜灯塔版" }),
    ]);
    var toggle = _el(
      "button",
      { type: "button", class: "menu-toggle", id: "menu-toggle", "aria-label": "Menu", "aria-expanded": "false" },
      [_el("span", {}, [])]
    );
    var navMain = _el("nav", { class: "nav-main", id: "nav-main", "aria-label": "Main" }, [
      nav("index.html", "首页", "index"),
      nav("demo.html", "行情", "demo"),
      nav("account.html", "我的", "account"),
      // Default-hide gated entries to avoid "flash then disappear".
      _el("a", { href: "partner.html", class: (active === "partner" ? "is-active" : ""), style: "display:none" }, ["伙伴"]),
      nav("feedback.html", "反馈", "feedback"),
    ]);
    var actions = _el("div", { class: "header-actions" }, []);
    var sel = _el("select", { id: "theme-select", class: "select-mini", "aria-label": "Theme" }, [
      _el("option", { value: "calm", text: "深蓝" }),
      _el("option", { value: "dark", text: "深黑" }),
      _el("option", { value: "light", text: "蓝白（默认）" }),
    ]);
    actions.appendChild(sel);
    actions.appendChild(_el("a", { class: "btn btn-ghost", href: "account.html" }, ["登录/续期"]));
    actions.appendChild(_el("a", { class: "btn btn-primary", href: "account.html#vip" }, ["开通 VIP"]));

    wrap.appendChild(brand);
    wrap.appendChild(toggle);
    wrap.appendChild(navMain);
    wrap.appendChild(actions);
    return wrap;
  }

  function footerDom() {
    var wrap = _el("div", { class: "container" }, []);
    var grid = _el("div", { class: "footer-grid" }, []);

    var c1 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "AI24X · AI 行情官｜灯塔版（V1.01）" }),
      _el("div", { class: "mt-2", text: "行情与指标，一目了然" }),
    ]);
    var c2 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "产品" }),
      _el("a", { href: "demo.html", text: "行情与信号" }),
      _el("a", { href: "account.html", text: "用户中心" }),
      _el("a", { href: "feedback.html", text: "意见反馈" }),
    ]);
    var c3 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "服务" }),
      _el("a", { href: "account.html#vip", text: "开通 VIP" }),
      _el("a", { href: "account.html#invite", text: "邀请奖励" }),
      _el("a", { href: "partner.html", text: "伙伴合作" }),
    ]);
    var c4 = _el("div", { class: "footer-col" }, [
      _el("div", { class: "footer-title", text: "合规" }),
      _el("a", { href: "https://beian.miit.gov.cn/", target: "_blank", rel: "noopener", text: "浙ICP备10040624号-7" }),
    ]);

    grid.appendChild(c1);
    grid.appendChild(c2);
    grid.appendChild(c3);
    grid.appendChild(c4);
    wrap.appendChild(grid);
    wrap.appendChild(_el("div", { class: "footer-bottom", text: "© 2026 AI24X" }));
    return wrap;
  }

  function mount(activePage) {
    var h = document.getElementById("site-header");
    var f = document.getElementById("site-footer");
    if (h) {
      try { h.textContent = ""; } catch (e0) {}
      h.appendChild(headerDom(activePage));
    }
    if (f) {
      try { f.textContent = ""; } catch (e1) {}
      f.appendChild(footerDom());
    }
    bindChrome();
    // Nav gate: show "伙伴" only for logged-in VIP users (reduce noise & improve conversion).
    try{
      var TOKEN_KEY = "ai24x_a_token";
      var tok = "";
      try{ tok = localStorage.getItem(TOKEN_KEY) || ""; }catch(e0){ tok = ""; }
      var nav = document.getElementById("nav-main");
      function hidePartner(){
        if(!nav) return;
        var links = nav.querySelectorAll('a[href$="partner.html"]');
        for(var i=0;i<links.length;i++){
          try{ links[i].style.display = "none"; }catch(e1){}
        }
      }
      function showPartner(){
        if(!nav) return;
        var links = nav.querySelectorAll('a[href$="partner.html"]');
        for(var i=0;i<links.length;i++){
          try{ links[i].style.display = ""; }catch(e1){}
        }
      }
      // Always hide first to avoid flash; then show only when confirmed VIP.
      hidePartner();
      if(!tok){
        // keep hidden
      }else{
        // Best-effort: if /api/me fails, keep partner hidden.
        try{
          fetch("/api/me", { cache: "no-store", headers: { "Authorization": "Bearer " + String(tok) } })
            .then(function(r){ return r && r.ok ? r.json() : null; })
            .then(function(d){
              try{
                var q = d && d.quota ? d.quota : null;
                var plan = q && q.plan ? String(q.plan) : "";
                var isVip = plan.indexOf("vip_") === 0;
                if(isVip) showPartner();
              }catch(e2){ /* keep hidden */ }
            })
            .catch(function(){ /* keep hidden */ });
        }catch(e3){ /* keep hidden */ }
      }
    }catch(eG){}
  }

  global.AI24X_A_SHELL = { mount: mount, applyTheme: applyTheme };
})(typeof window !== "undefined" ? window : this);

