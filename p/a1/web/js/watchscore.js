/* AI24X Watch Score shared module (used by watchscore.html and account.html) */
window.AI24X_WatchScore = (function () {
      var TOKEN_KEY = "ai24x_a_token";
      function apiBase() {
        try {
          var q = "";
          try { q = String(location.search || ""); } catch (eQ) { q = ""; }
          if (q && q.indexOf("api_base=") >= 0) {
            var m = q.match(/[?&]api_base=([^&]+)/);
            if (m && m[1]) {
              var u = decodeURIComponent(m[1]);
              u = String(u || "").trim().replace(/\/$/, "");
              if (u) {
                try { localStorage.setItem("ai24x_a_api_base", u); } catch (eS) {}
                return u;
              }
            }
          }
        } catch (e0) {}
        try {
          var saved = "";
          try { saved = String(localStorage.getItem("ai24x_a_api_base") || ""); } catch (e1) { saved = ""; }
          saved = saved.trim().replace(/\/$/, "");
          if (saved) return saved;
        } catch (e2) {}
        try {
          var host = String(location.hostname || "");
          var port = String(location.port || "");
          if ((host === "127.0.0.1" || host === "localhost") && port === "18001") return "http://127.0.0.1:18011";
        } catch (e3) {}
        return "";
      }
      var base = apiBase();
      function tokenGet() {
        try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
      }
      function $(id) { return document.getElementById(id); }
      function apiFetch(path, opt) {
        opt = opt || {};
        opt.headers = opt.headers || {};
        var t = tokenGet();
        if (t) opt.headers.Authorization = "Bearer " + t;
        return fetch((base || "") + path, opt).then(function (r) {
          return r.text().then(function (txt) {
            var j = null;
            try { j = txt ? JSON.parse(txt) : null; } catch (e0) { j = null; }
            if (!r.ok) {
              var detail = "";
              if (j && j.detail != null) {
                detail = typeof j.detail === "string" ? j.detail : (function () {
                  try { return JSON.stringify(j.detail); } catch (e1) { return ""; }
                })();
              }
              var err = new Error(detail || txt || ("HTTP " + r.status));
              try { err.status = r.status; } catch (e2) {}
              throw err;
            }
            return j;
          });
        });
      }

      var wlItems = [];
      var wlState = { filter: "all", search: "", sortKey: "score", sortDir: "desc", weakOpen: false, expanded: {} };
      function wlStatus(s, isErr) {
        var el = $("wl-status");
        if (!el) return;
        el.textContent = s || "";
        el.style.color = isErr ? "#f87171" : "";
      }
      function escWl(s) {
        if (!s) return "";
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
      }
      function maskAcctPhone(p) {
        p = String(p != null ? p : "").trim();
        if (p.length >= 7 && /^\d+$/.test(p)) return p.slice(0, 3) + "****" + p.slice(-4);
        return "";
      }
      function maskAcctEmail(e) {
        e = String(e != null ? e : "").trim();
        var at = e.indexOf("@");
        if (at <= 1) return "";
        var local = e.slice(0, at);
        var dom = e.slice(at);
        var ml = local.length > 3 ? local.slice(0, 3) + "***" : local.slice(0, 1) + "***";
        return ml + dom;
      }
      function loadAccountLine() {
        var el = $("wl-account");
        if (!el) return;
        apiFetch("/api/me").then(function (d) {
          var u = (d && d.user) || {};
          var idv = maskAcctPhone(u.phone) || maskAcctEmail(u.email) || ("#" + (u.id != null ? u.id : "?"));
          el.textContent = "当前账号：" + idv;
        }).catch(function () {
          el.textContent = "当前账号读取失败，请确认已登录";
        });
      }
      function loadWlScores() {
        var wrap = $("wl-score-wrap");
        var hint = $("wl-score-hint");
        if (!wrap) return;
        if (!wlItems.length) { wlStatus("请先添加自选股", true); return; }
        wrap.innerHTML = '<div class="muted small">评分计算中…（约几秒，最多 12 秒）</div>';
        apiFetch("/api/watchlist/scores").then(function (d) {
          var items = (d && d.items) || [];
          if (hint) {
            hint.style.display = "";
            hint.textContent = "共 " + items.length + " 只标的参与技术指标统计；点名称可新窗口查看 K 线，点「更多」可展开全部信号与风险。个别标的获取超时显示 —，可点「刷新评分」重试。统计按自然日同票去重扣次，仅为技术规则量化结果，不构成投资建议。";
          }
          renderMarket(d.market);
          renderWlTier(d);
          renderWlScores(items);
        }).catch(function (e) {
          wrap.innerHTML = "";
          wlStatus("评分失败：" + (e && e.message || "网络错误"), true);
        });
      }
      function renderMarket(m) {
        var el = $("wl-market");
        if (!el) return;
        if (!m || !m.name) { el.style.display = "none"; return; }
        var pts = Number(m.pts || 0);
        var cls = pts >= 2 ? "mkt-up" : (pts <= -2 ? "mkt-down" : "mkt-flat");
        var lbl = pts >= 2 ? "顺风" : (pts <= -2 ? "逆风" : "中性");
        el.style.display = "";
        el.innerHTML = '<span class="mkt-label">大盘环境</span>：<span class="mkt-state ' + cls + '">' + escWl(lbl) + '</span>（' + escWl(m.name) + '：' + escWl((m.tags || []).join(" / ")) + '）';
      }
            function renderWlTier(d) {
        var el = $("wl-tier");
        if (!el) return;
        if (!d || !d.truncated) { el.style.display = "none"; return; }
        el.style.display = "";
        var maxN = Number(d.score_max || 0);
        var total = Number(d.watchlist_total || 0);
        var vipCap = Number(d.vip_cap || 0);
        if (d.is_vip) {
          el.innerHTML = "已统计前 <b>" + maxN + "</b> 只（共 " + total + " 只自选），建议精简自选以完整统计。";
        } else {
          el.innerHTML = "已统计前 <b>" + maxN + "</b> 只（共 " + total + " 只自选）· <a class=\"wl-tier-link\" href=\"./account.html#vip\" target=\"_top\">开通 VIP 可统计 " + vipCap + " 只</a>";
        }
      }
      function renderWlScores(items) {
        wlItems = items || [];
        renderWlBoard();
      }
      function wlGroupOf(sc, err) {
        if (err) return "weak";
        return sc >= 70 ? "strong" : (sc >= 45 ? "mid" : "weak");
      }
      function wlSortCmp(a, b) {
        var k = wlState.sortKey, dir = wlState.sortDir === "asc" ? 1 : -1;
        if (k === "score") {
          var sa = a.error ? -1 : Number(a.score || 0);
          var sb = b.error ? -1 : Number(b.score || 0);
          return (sa - sb) * dir;
        }
        if (k === "code") return String(a.code || "").localeCompare(String(b.code || "")) * dir;
        return String(a.name || "").localeCompare(String(b.name || ""), "zh") * dir;
      }
      function renderWlControls() {
        var btns = [["all", "全部"], ["strong", "强势 ≥70"], ["mid", "中性 45-69"], ["weak", "弱势 <45"], ["risk", "有风险提示"]];
        var h = '<div class="wl-controls"><span class="wl-filters">';
        for (var i = 0; i < btns.length; i++) {
          var on = wlState.filter === btns[i][0];
          h += '<button type="button" class="wl-fbtn' + (on ? " on" : "") + '" data-wl-act="filter" data-k="' + btns[i][0] + '">' + escWl(btns[i][1]) + '</button>';
        }
        h += '</span><input id="wl-search" class="wl-search" type="search" placeholder="搜索代码/名称" value="' + escWl(wlState.search) + '" data-wl-act="search" />';
        h += '</div>';
        return h;
      }
      function wlSortMark(k) {
        if (wlState.sortKey !== k) return "";
        return wlState.sortDir === "asc" ? " ↑" : " ↓";
      }
      function renderWlTable() {
        var items = wlItems || [];
        var q = String(wlState.search || "").trim().toLowerCase();
        var list = [];
        for (var i = 0; i < items.length; i++) {
          var it = items[i];
          if (q && String(it.code || "").toLowerCase().indexOf(q) < 0 && String(it.name || "").toLowerCase().indexOf(q) < 0) continue;
          var sc = Number(it.score || 0);
          var f = wlState.filter;
          if (f === "strong" && (it.error || sc < 70)) continue;
          if (f === "mid" && (it.error || sc < 45 || sc >= 70)) continue;
          if (f === "weak" && !it.error && sc >= 45) continue;
          if (f === "risk" && !(it.risks && it.risks.length)) continue;
          list.push(it);
        }
        list.sort(wlSortCmp);
        var html = '<div class="wl-table-scroll"><table class="wl-score-table"><thead><tr>'
          + '<th class="wl-rank">#</th>'
          + '<th class="wl-sort" data-wl-act="sort" data-k="code" title="点击排序">代码' + wlSortMark("code") + '</th>'
          + '<th class="wl-sort" data-wl-act="sort" data-k="name" title="点击排序">名称' + wlSortMark("name") + '</th>'
          + '<th class="wl-sort" data-wl-act="sort" data-k="score" title="点击排序">综合分' + wlSortMark("score") + '</th>'
          + '<th>技术信号</th><th>风险提示</th></tr></thead><tbody>';
        var groups = [["strong", "强势（≥70）"], ["mid", "中性（45-69）"], ["weak", "弱势（<45 / 超时）"]];
        if (wlState.sortKey === "score" && wlState.sortDir === "asc") groups = groups.slice().reverse();
        var idx = 0, shown = 0;
        for (var g = 0; g < groups.length; g++) {
          var gname = groups[g][0];
          var gitems = [];
          for (var i = 0; i < list.length; i++) {
            if (wlGroupOf(Number(list[i].score || 0), !!list[i].error) === gname) gitems.push(list[i]);
          }
          if (!gitems.length) continue;
          var collapsed = gname === "weak" && !wlState.weakOpen;
          html += '<tr class="wl-group-row"><td colspan="6"><span class="wl-group-title" data-wl-act="group" data-k="' + gname + '">' + escWl(groups[g][1]) + ' · ' + gitems.length + ' 只' + (gname === "weak" ? (collapsed ? "　▶ 展开" : "　▼ 收起") : "") + '</span></td></tr>';
          if (collapsed) continue;
          for (var i = 0; i < gitems.length; i++) { idx++; shown++; html += wlRowHtml(gitems[i], idx); }
        }
        html += '</tbody></table></div>';
        if (!shown) html = '<div class="wl-empty">无匹配标的，试试调整筛选或搜索。</div>';
        return html;
      }
      function wlRowHtml(it, idx) {
        var err = String(it.error || "");
        var sc = Number(it.score || 0);
        var cls = err ? "wl-score-low" : (sc >= 70 ? "wl-score-high" : (sc >= 45 ? "wl-score-mid" : "wl-score-low"));
        var nameCls = err ? "wk-low" : (sc >= 70 ? "wk-high" : (sc >= 45 ? "wk-mid" : "wk-low"));
        var arrow = err ? "" : (sc >= 70 ? " ↗" : (sc >= 45 ? " →" : " ↘"));
        var tagsArr = it.tags || [];
        var risksArr = it.risks || [];
        var tagsFull = escWl(tagsArr.join(" / "));
        var risksFull = escWl(risksArr.join(" / "));
        var secKey = String(it.secid || "");
        var isExp = !!(wlState.expanded && wlState.expanded[secKey]);
        var moreBtn = "";
        if (!err && tagsArr.length > 5) {
          moreBtn = ' <button type="button" class="wl-more" data-wl-act="expand" data-k="' + escWl(secKey) + '">' + (isExp ? "收起▴" : "更多▾") + '</button>';
        }
        var tagsShow = tagsArr.length ? escWl(tagsArr.slice(0, 5).join(" / ")) + (tagsArr.length > 5 ? " …" : "") + moreBtn : "—";
        var risksShow = risksArr.length ? escWl(risksArr.slice(0, 2).join(" / ")) + (risksArr.length > 2 ? " …" : "") : (err ? "数据获取超时，点「刷新评分」重试" : "—");
        var link = './demo.html?secid=' + encodeURIComponent(it.secid || '') + '&period=day';
        var html = '<tr><td class="wl-rank">' + idx + '</td>'
          + '<td class="wl-code">' + escWl(it.code || "") + '</td>'
          + '<td class="wl-name"><a class="wl-kline ' + nameCls + '" href="' + link + '" target="_blank" rel="noopener" title="新窗口查看 K 线">' + escWl(it.name || "") + arrow + '</a></td>'
          + '<td class="wl-score-col"><span class="' + cls + '">' + (err ? "—" : sc.toFixed(0)) + '</span></td>'
          + '<td class="wl-tags" title="' + tagsFull + '">' + tagsShow + '</td>'
          + '<td class="wl-risk" title="' + risksFull + '">' + risksShow + '</td></tr>';
        if (isExp && !err) {
          html += '<tr class="wl-detail-row"><td colspan="6"><div class="wl-detail-grid">'
            + '<div class="wl-detail-col wl-detail-col-tags">技术信号：<span class="wl-detail-tags">' + tagsFull + '</span></div>'
            + '<div class="wl-detail-col wl-detail-col-risks">风险提示：<span class="wl-detail-risks">' + (risksArr.length ? risksFull : "—") + '</span></div>'
            + '</div></td></tr>';
        }
        return html;
      }
      function renderWlBoard() {
        var wrap = $("wl-score-wrap");
        if (!wrap) return;
        var items = wlItems || [];
        if (!items.length) {
          wrap.innerHTML = '<div class="muted small">暂无评分结果（标的可能缺少足够 K 线历史）。</div>';
          return;
        }
        var ok = 0, sum = 0, high = 0;
        for (var i = 0; i < items.length; i++) {
          if (items[i].error) continue;
          ok++; sum += Number(items[i].score || 0);
          if (Number(items[i].score || 0) >= 70) high++;
        }
        var avg = ok ? (sum / ok).toFixed(1) : "—";
        var html = '<div class="wl-score-head"><span>共 <b>' + items.length + '</b> 只 · 有效 <b>' + ok + '</b> 只 · 平均分 <b>' + avg + '</b> · 高分(≥70) <b>' + high + '</b> 只</span></div>';
        html += renderWlControls();
        html += '<div id="wl-table-region">' + renderWlTable() + '</div>';
        wrap.innerHTML = html;
      }
      function wlSort(k) {
        if (wlState.sortKey === k) { wlState.sortDir = wlState.sortDir === "asc" ? "desc" : "asc"; }
        else { wlState.sortKey = k; wlState.sortDir = k === "score" ? "desc" : "asc"; }
        var region = $("wl-table-region");
        if (region) region.innerHTML = renderWlTable();
      }
      function wlFilter(k) { wlState.filter = k; renderWlBoard(); }
      function wlSearch(v) { wlState.search = String(v || ""); var region = $("wl-table-region"); if (region) region.innerHTML = renderWlTable(); }
      function wlToggleGroup(g) { if (g === "weak") wlState.weakOpen = !wlState.weakOpen; var region = $("wl-table-region"); if (region) region.innerHTML = renderWlTable(); }
      function wlToggleExpand(secid) {
        if (!wlState.expanded) wlState.expanded = {};
        if (secid) wlState.expanded[secid] = !wlState.expanded[secid];
        var region = $("wl-table-region");
        if (region) region.innerHTML = renderWlTable();
      }
      function loadWatchlist(force) {
        if (!tokenGet()) return;
        var now = Date.now();
        if (!force && now - wlLastLoad < 4000) return;
        wlLastLoad = now;
        apiFetch("/api/watchlist").then(function (d) {
          wlItems = (d && d.items) || [];
          if (wlItems.length) loadWlScores();
          else {
            var wrap = $("wl-score-wrap");
            if (wrap) wrap.innerHTML = '<div class="muted small">暂无自选。到 <a href="./demo.html">行情页</a> 查询并点「加自选」后，自动生成技术指标统计。</div>';
            var mEl = $("wl-market"); if (mEl) mEl.style.display = "none";
          }
        }).catch(function (e) {
          wlStatus("自选加载失败：" + (e && e.message ? e.message : "网络错误"), true);
        });
      }
      var wlLastLoad = 0;
      var booted = false;
      function boot() {
        if (!booted) { booted = true; bindWlEvents(); }
        try {
          if (/[?&]embed=1/.test(String(location.search || ""))) {
            document.body.classList.add("embed");
            var hd = document.getElementById("site-header");
            var ft = document.getElementById("site-footer");
            if (hd) hd.style.display = "none";
            if (ft) ft.style.display = "none";
          }
        } catch (eE) {}
        var logged = !!tokenGet();
        var guest = $("auth-guest");
        var user = $("auth-user");
        if (!logged) {
          if (guest) guest.hidden = false;
          if (user) user.hidden = true;
          return;
        }
        if (guest) guest.hidden = true;
        if (user) user.hidden = false;
        loadAccountLine();
        loadWatchlist(true);
      }
      function bindWlEvents() {
        var wlBoard = $("wl-score-wrap");
        if (wlBoard) {
          wlBoard.addEventListener("click", function (ev) {
            var t = ev.target;
            while (t && t !== wlBoard) {
              var act = t.getAttribute && t.getAttribute("data-wl-act");
              if (act === "sort") { wlSort(String(t.getAttribute("data-k") || "score")); return; }
              if (act === "filter") { wlFilter(String(t.getAttribute("data-k") || "all")); return; }
              if (act === "group") { wlToggleGroup(String(t.getAttribute("data-k") || "")); return; }
              if (act === "expand") { wlToggleExpand(String(t.getAttribute("data-k") || "")); return; }
              t = t.parentNode;
            }
          });
          wlBoard.addEventListener("input", function (ev) {
            if (ev.target && ev.target.getAttribute && ev.target.getAttribute("data-wl-act") === "search") {
              wlSearch(ev.target.value);
            }
          });
        }
        var btn = $("btn-wl-scores");
        if (btn) btn.addEventListener("click", loadWlScores);
      }
      function refresh(force) {
        if (!tokenGet()) return;
        if (!booted) { booted = true; bindWlEvents(); }
        loadAccountLine();
        loadWatchlist(!!force);
      }
      return { boot: boot, refresh: refresh };
  })();
