/* AI24X 掘金 VIP 页（gd.html）—— 前端只负责展示，算法全部在服务端 /api/bj/screener */
window.AI24X_BJScreener = (function () {
  "use strict";
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
          if (u) { try { localStorage.setItem("ai24x_a_api_base", u); } catch (eS) {} return u; }
        }
      }
    } catch (e0) {}
    try {
      var saved = String(localStorage.getItem("ai24x_a_api_base") || "").trim().replace(/\/$/, "");
      if (saved) return saved;
    } catch (e1) {}
    try {
      var host = String(location.hostname || "");
      var port = String(location.port || "");
      if ((host === "127.0.0.1" || host === "localhost") && (port === "18001" || port === "18003")) return "http://127.0.0.1:18011";
    } catch (e2) {}
    return "";
  }
  var base = apiBase();
  function tokenGet() { try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; } }
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
          if (j && j.detail != null) detail = typeof j.detail === "string" ? j.detail : "";
          var err = new Error(detail || txt || ("HTTP " + r.status));
          try { err.status = r.status; } catch (e1) {}
          throw err;
        }
        return j;
      });
    });
  }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function num(v, d) { var n = Number(v); return isFinite(n) ? n.toFixed(d == null ? 2 : d) : "—"; }
  function money(v) { if (v == null || !isFinite(v)) return "—"; if (v >= 1e8) return (v / 1e8).toFixed(1) + "亿"; if (v >= 1e4) return (v / 1e4).toFixed(0) + "万"; return v.toFixed(0); }
  function pct(v) { if (v == null || !isFinite(v)) return "—"; return (v >= 0 ? "+" : "") + v.toFixed(2) + "%"; }
  function cls(v) { return v > 0 ? "up" : (v < 0 ? "down" : ""); }
  function fmtDate() { var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function marketLabel(m) { return m === "all" ? "沪深京全市场" : "北证全市场"; }
  function marketScope(d) { return ((d && d.market_code) || state.market) === "all" ? "沪深京·板块成分池" : "北证全市场"; }

  var state = { loading: false, data: null, market: "all" };
  var reqSeq = 0;

  function setStatus(s, isErr, isWarn) {
    var el = $("bj-status");
    if (!el) return;
    el.innerHTML = s || "";
    el.style.color = isErr ? "var(--rise)" : (isWarn ? "var(--warn)" : "");
    el.style.fontWeight = isWarn ? "800" : "";
  }
  function statusLoading() {
    setStatus('<span class="spin"></span> 正在扫描' + marketLabel(state.market) + '…（北证约 20~40 秒，沪深京约 30~60 秒）');
  }
  var progTimer = null;
  var waitDeadline = 0;
  function stopProgress() {
    if (progTimer) { clearInterval(progTimer); progTimer = null; }
    var w = $("bj-progress");
    if (w) w.hidden = true;
  }
  function startProgress(market, seq) {
    var w = $("bj-progress");
    if (!w) return;
    var shown = false;
    var fill = $("bj-progress-fill"), txt = $("bj-progress-text");
    function showBar() {
      if (shown) return;
      shown = true;
      w.hidden = false;
    }
    function tick() {
      if (seq !== reqSeq) { stopProgress(); return; }
      apiFetch("/api/bj/screener/progress?market=" + encodeURIComponent(market)).then(function (p) {
        if (seq !== reqSeq) return;
        if (p && p.running === true) { showBar(); }
        if (p && p.running === false && p.phase === "done" && Number(p.pct) >= 100) { stopProgress(); return; }
        if (fill) fill.style.width = Math.max(2, Math.min(100, Number(p && p.pct) || 0)) + "%";
        if (txt) txt.textContent = (p && p.msg) || "正在扫描…";
      }).catch(function () {});
    }
    tick();
    progTimer = setInterval(tick, 1200);
  }

  function secidForCode(code) {
    var c = String(code || "").replace(/[^\d]/g, "");
    if (c === "000001") return "0.000001"; // stock context: Ping An Bank (SZ), not SH index
    if (c.charAt(0) === "9" && c.charAt(1) === "2") return "0." + c; // BSE 92xxxx
    if (/^89\d{4}$/.test(c)) return "0." + c; // BSE 89xxxx
    if (/^(?:43|83|87|88)\d{4}$/.test(c)) return "0." + c; // BSE legacy codes
    if (c.charAt(0) === "6") return "1." + c; // Shanghai
    return "0." + c; // Shenzhen / ChiNext
  }
  function quoteHref(p) {
    return "demo.html?secid=" + encodeURIComponent(secidForCode(p.code)) + "&period=day";
  }
  function tierBadge(p) {
    if (p.tier === "king") return '<span class="tier-badge tier-king">⭐ 王者</span>';
    if (p.tier === "key") return '<span class="tier-badge tier-key">重点</span>';
    return "";
  }
  function roleBadge(p) {
    if (p.pickRole === "leader") return '<span class="tier-badge tier-leader">主线龙头</span>';
    if (p.pickRole === "catchup") return '<span class="tier-badge tier-catchup">补涨卡位</span>';
    return "";
  }
  function mainBadge(p) {
    if (p.mainHit) return '<span class="tier-badge tier-main">主线·' + esc(p.mainName || "") + '</span>';
    return '<span class="tier-badge tier-offmain">非主线</span>';
  }
  function indBadge(p) {
    if (p.ind && p.ind !== "-") return '<span class="tier-badge tier-ind">' + esc(p.ind) + '</span>';
    return "";
  }
  function coreTags(p) {
    var a = p.patterns || {}, h = [];
    if (a.surgeStart) h.push('<span class="tag ok">底部异动·' + (p.surgeDaysAgo || 0) + '天前</span>');
    if (a.ztPullback) h.push('<span class="tag ok strong">涨停级回踩</span>');
    else if (a.pullback) h.push('<span class="tag ok">异动回踩企稳</span>');
    // 主线已在头部徽章显示，标签区不再重复
    if (a.baseUp) h.push('<span class="tag ok">底部走多</span>');
    if (a.smallYang) h.push('<span class="tag ok">一路小阳</span>');
    if (a.tightBurst) h.push('<span class="tag ok">均线发散</span>');
    if (p.boardLeader) h.push('<span class="tag ok strong">板块龙头</span>');
    if (p.hotName) h.push('<span class="tag warn">共振:' + esc(p.hotName) + '</span>');
    var f2 = p.fund || {};
    if (f2.earnPos && f2.earnPos.length) h.push('<span class="tag ok strong">业绩预增</span>');
    if (f2.earnNeg && f2.earnNeg.length) h.push('<span class="tag risk">业绩预亏</span>');
    if (p.fundIn > 0) h.push('<span class="tag info">主力+' + money(p.fundIn) + '</span>');
    var tl = p.tail || {};
    if (tl.tailPct != null && tl.tailPct >= 0.5) h.push('<span class="tag ok strong">尾盘强承接</span>');
    if (p.lhb && p.lhb.net >= 0) h.push('<span class="tag ok">龙虎榜净买</span>');
    if (h.length > 5) h = h.slice(0, 5);
    return '<div class="pick-tags">' + h.join('') + '</div>';
  }
  function reasonOf(p) {
    var a = p.patterns || {}, r = [];
    if (a.surgeStart) r.push("底部放量异动" + (p.surgeDaysAgo || 0) + "天前启动");
    if (a.pullback) r.push("异动拉升后缩量回踩企稳");
    if (a.ztPullback) r.push("涨停级回踩·强势低吸");
    if (a.smallYang) r.push("连续小阳趋势上拐");
    if (a.baseUp) r.push("站上MA20且均线上拐");
    if (a.tightBurst) r.push("均线粘合后发散");
    if (p.mainHit && p.mainName) r.push("复盘主线板块:" + p.mainName);
    if (p.revHit && p.revName) r.push("主线反推共振:" + p.revName);
    if (p.boardLeader) r.push("板块龙头");
    if (p.hotName) r.push("板块共振:" + p.hotName);
    if (p.snap && p.snap.score != null) r.push("AI综合分" + num(p.snap.score, 0));
    if (r.length > 3) r = r.slice(0, 3);
    return r.join("、") || "形态健康";
  }
  function bearishHtml(p) {
    var b = p.bearish || { level: "pass", items: [] };
    var fund = p.fund || {};
    var fwarn = [];
    if (fund.flags && fund.flags.length) fwarn = fwarn.concat(fund.flags.map(function (t) { return "业绩红旗:" + t; }));
    if (fund.newsHard && fund.newsHard.length) fwarn = fwarn.concat(fund.newsHard.map(function (t) { return "消息硬伤:" + t; }));
    if (fund.newsWarn && fund.newsWarn.length) fwarn = fwarn.concat(fund.newsWarn.slice(0, 2).map(function (t) { return "消息警示:" + t; }));
    var isHard = b.level === "hard" || fund.level === "hard";
    var isWarn = b.level === "warn" || fund.level === "warn" || fwarn.length > 0;
    var txt = [];
    (b.items || []).forEach(function (it) { txt.push(it.text); });
    fwarn.forEach(function (t) { txt.push(t); });
    if (isHard) return '<div class="bearish">↓ 利空排查：<b>硬伤</b> ' + esc(txt.slice(0, 2).join('；')) + '</div>';
    if (isWarn) return '<div class="bearish warn">↓ 利空排查：<b>警示</b> ' + esc(txt.slice(0, 2).join('；') || '含警示标签') + '</div>';
    return '<div class="bearish pass">✓ 利空排查：通过</div>';
  }

  function fundHtml(p) {
    var f = (p.fund || {}).fin;
    if (!f) return "";
    var np = (f.npYoy == null) ? "—" : num(f.npYoy, 1) + "%";
    var rv = (f.revYoy == null) ? "—" : num(f.revYoy, 1) + "%";
    var npCls = (f.npYoy == null) ? "" : (f.npYoy >= 0 ? "up" : "down");
    var rvCls = (f.revYoy == null) ? "" : (f.revYoy >= 0 ? "up" : "down");
    var roe = (f.roe == null) ? "—" : num(f.roe, 1) + "%";
    var gm = (f.gross == null) ? "—" : num(f.gross, 1) + "%";
    return '<div class="pick-fund">业绩（' + esc(f.report || "最新") + '）：净利 <b class="' + npCls + '">' + np + '</b> ｜ 营收 <b class="' + rvCls + '">' + rv + '</b> ｜ ROE ' + roe + ' ｜ 毛利率 ' + gm + '</div>';
  }

  function renderMeta(d) {
    var el = $("bj-meta");
    if (!el) return;
    var line = "数据截至 <b>" + esc(d.asof || d.date || "") + "</b> 收盘 ｜ " + marketScope(d) + " <b>" + d.total + "</b> 只 ｜ 精筛候选 <b>" + d.scanned + "</b> 只 ｜ 合格 <b>" + d.fine + "</b> 只";
    if (d.hard_rejected) line += " ｜ 利空硬伤排除 <b style='color:var(--rise)'>" + d.hard_rejected + "</b> 只";
    var mkt = d.market;
    if (mkt && mkt.tags && mkt.tags.length) {
      line += "<br/>大盘：" + mkt.tags.map(function (t) { return '<span class="tag ' + (mkt.weak ? "risk" : "ok") + '">' + esc(t) + '</span>'; }).join("");
    }
    line += "<br/>耗时 " + num(d.elapsed_s, 0) + "s";
    if (d.regime) {
      var regMap = {
        attack: { txt: '强攻模式', cls: 'attack', note: '大盘底+金确认、小盘转强：可积极，主线龙头 + 补涨卡位双线推进。' },
        stable: { txt: '稳健模式', cls: 'stable', note: '大盘中性：以主线双确认 + 零风险标的为主，控制单票仓位。' },
        defensive: { txt: '防守模式', cls: 'defensive', note: '大盘走弱（上证或中证1000破位）：仅主线双确认 + 零风险标的，最多 2 只，宁可空仓不勉强。' }
      };
      var rm = regMap[d.regime] || null;
      if (rm) line += '<br/><div class="bj-regime ' + rm.cls + '" style="margin:6px 0 0"><b>' + rm.txt + '</b><span>' + rm.note + '</span></div>';
      if (d.style && d.style.mode && d.style.mode !== "defensive") {
        line += '<br/><div class="bj-style ' + d.style.mode + '"><b>' + esc(d.style.label || "") + '</b><span>' + esc(d.style.note || "") + '</span></div>';
      }
    }
    if (d.off_market) line += "<br/><span style='color:var(--warn)'>⏸ 非交易日：以下为最近交易日（" + esc(d.stale_from || "") + "）归档结果</span>"; else if (d.stale) line += "<br/><span class='bj-empty-flag'>⚠ 今日无合格标的</span>，以下展示上一交易日（" + esc(d.stale_from || "") + "）结果";
    if (d.cached && !d.vip_required) line += ' <span class="bj-cached">（今日结果已缓存，点「重新扫描」刷新）</span>';
    el.innerHTML = line;
    el.hidden = false;
  }
  function renderMainlines(d) {
    var box = $("bj-mainlines");
    if (!box) return;
    var ml = (d.mainlines || []).filter(function (m) { return m && m.src === "daily"; });
    var mld = d.mainline_date ? ' · ' + esc(d.mainline_date) : '';
    if (!ml.length) {
      var emptyMl = d.archive
        ? '该日未锁定主线（复盘未生成或板块未达标）。'
        : '今日主线尚未生成（15:03 收盘后复盘自动锁定），可<a href="/daily/" target="_blank" rel="noopener">查看最近一期复盘 ↗</a>。';
      box.innerHTML = '<div class="bj-note">主攻主线与复盘同步锁定：' + emptyMl + '</div>';
      return;
    }
    var h = '<div class="bj-section">主攻主线（同步复盘' + mld + '）</div>' +
      '<div class="chips">' +
      '<a class="chip chip-mainline" href="/daily/" target="_blank" rel="noopener" title="主线以复盘页为准（资金+技术双确认）· 新窗口打开复盘">' +
      ml.map(function (m) { return '<b>' + esc(m.name || "") + '</b>'; }).join(' <span class="ml-sep">·</span> ') + '↗</a>' +
      '</div>';
    box.innerHTML = h;
  }
    function renderBoardRank(d) {
    var box = $("bj-boardrank");
    if (!box) return;
    var rank = d.board_rank || [];
    if (!rank.length) { box.innerHTML = ""; return; }
    var isAll = (d.market_code || state.market) === "all";
    var showMain = !d.vip_required;
    var mains = (showMain ? (d.mainlines || []) : []).filter(function (m) { return m && m.src === "daily"; })
      .map(function (m) { return String(m.name || "").replace(/\s+/g, ""); }).filter(Boolean);
    function hitMainline(name) {
      var n = String(name || "").replace(/\s+/g, "");
      if (!n) return false;
      for (var i = 0; i < mains.length; i++) {
        if (n === mains[i]) return true;
        if (mains[i].length >= 2 && (n.indexOf(mains[i]) >= 0 || mains[i].indexOf(n) >= 0)) return true;
      }
      return false;
    }
    var h = '<div class="bj-section">板块排行</div>' +
      (isAll
        ? '<div class="bj-note">💡 主线优先；热度≠能追，破位勿左侧。</div>'
        : '<div class="bj-note">💡 底部异动观察，回踩企稳再介入。</div>') +
      '<div class="br-list">';
    rank.forEach(function (b, idx) {
      var t = (hitMainline(b.name) ? '<span class="tag ok">主线 ✓</span>' : "") + (b.tier === "king" ? '<span class="tier-badge tier-king">⭐ 王者</span>'
        : (b.tier === "key" ? '<span class="tier-badge tier-key">重点</span>'
          : '<span class="tier-badge tier-normal">备选</span>'));
      var secid = String(b.secid || "").trim();
      var code = secid.replace(/^\d+\./, "");
      var href = secid ? ("demo.html?secid=" + encodeURIComponent(secid) + "&period=day" + (b.name ? "&name=" + encodeURIComponent(b.name) : "")) : "#";
      var nm = '<a class="n" href="' + href + '" target="_blank" rel="noopener" title="在AI行情官中查看 ' + esc(b.name) + (code ? ' (' + esc(code) + ')' : '') + '">' +
        esc(b.name) + (code ? ' <span class="br-code">' + esc(code) + '</span>' : '') + ' ↗</a>';
      var st = "";
      if (isAll) {
        if (b.mainline && !b.f164) {
          st = '复盘主线 · 资金+技术双确认';
        } else {
          st = '5日主力 <b>' + money(b.f164) + '</b> ｜ 今日主力 <b>' + money(b.f62) + '</b>' + (b.p5 != null ? ' ｜ 5日 ' + pct(b.p5) : '');
        }
      } else {
        if (b.count != null) st += b.count + ' 只异动';
        if (b.amount != null) st += (st ? ' ｜ ' : '') + '成交 ' + money(b.amount);
        if (b.p5 != null) st += (st ? ' ｜ ' : '') + '5日 ' + pct(b.p5);
        if (b.hot) st += ' ｜ ✓板块榜';
      }
      if (b.streak >= 2) st += (st ? ' ｜ ' : '') + '🔥 连续 ' + b.streak + ' 日上榜';
      var lds = (b.leaders || []).slice(0, 3).map(function (ld) {
        return '<a href="demo.html?secid=' + encodeURIComponent(secidForCode(ld.code)) + '&period=day" target="_blank" rel="noopener" title="在AI行情官中查看 ' + esc(ld.name) + '">' +
          esc(ld.name) + ' <span class="' + cls(ld.pct) + '">' + pct(ld.pct) + '</span></a>';
      }).join("");
      h += '<div class="br-item ' + (b.tier || "") + '">' +
        '<span class="br-idx">' + (idx + 1) + '</span>' + t + nm +
        (st ? '<span class="st">' + st + '</span>' : '') +
        (lds ? '<span class="br-leaders">龙头：' + lds + '</span>' : '') +
        '</div>';
    });
    h = '<details class="bj-fold" open><summary>板块排行 · 点击收起</summary>' + h + '</details>';
    box.innerHTML = h;
  }
  // ---------- 同花顺情绪卡片（交叉验证，独立加载，不依赖扫描） ----------
  function thsBoardLab(k) {
    return { "two_board": "2连板", "three_board": "3连板", "four_board": "4连板",
             "five_board": "5连板", "six_board": "6连板", "seven_over": "7板+" }[k] || k;
  }
  function renderThsSentiment(d) {
    var box = $("bj-ths-sentiment");
    if (!box) return;
    if (!d || d.ok === false) { box.innerHTML = ""; return; }
    var h = '<div class="bj-section">情绪面 · 交叉验证</div>';
    var lu = d.limit_up || {};
    var chips = [];
    if (lu.count != null) chips.push('涨停 <b>' + esc(lu.count) + '</b> 家');
    if (lu.max_lianban) chips.push('最高 <b>' + esc(lu.max_lianban) + ' 连板</b>' + (lu.max_name ? ' · ' + esc(lu.max_name) : ''));
    var an = d.anomaly || {};
    var tags = an.tags || {};
    var tagArr = Object.keys(tags).sort(function (a, b) { return (tags[b] - tags[a]); }).slice(0, 4);
    if (tagArr.length) chips.push('异动 ' + tagArr.map(function (k) { return esc(k) + ' ' + tags[k]; }).join('、'));
    if (chips.length) h += '<div class="bj-note">' + chips.join(' ｜ ') + '</div>';
    function chipsRow(title, items, fn) {
      if (!items || !items.length) return "";
      return '<div class="ths-sub">' + title + '</div><div class="ths-inline">' + items.map(fn).join('') + '</div>';
    }
    var hot = d.hot || [];
    h += chipsRow('🔥 热股榜 TOP5', hot, function (it, i) {
      var arrow = it.rank_trend === "up" ? '<span class="up">↑</span>' : (it.rank_trend === "down" ? '<span class="down">↓</span>' : '→');
      return '<a class="chip" href="demo.html?secid=' + encodeURIComponent(secidForCode(it.ticker)) + '&period=day" target="_blank" rel="noopener" title="在AI行情官中查看 ' + esc(it.name) + '">' + (i + 1) + '. ' + esc(it.name) + ' ' + arrow + '</a>';
    });
    var sky = d.skyrocket || [];
    h += chipsRow('🚀 飙升榜 TOP5', sky, function (it, i) {
      return '<a class="chip" href="demo.html?secid=' + encodeURIComponent(secidForCode(it.ticker)) + '&period=day" target="_blank" rel="noopener" title="在AI行情官中查看 ' + esc(it.name) + '">' + (i + 1) + '. ' + esc(it.name) + '</a>';
    });
    var hm = d.hot_money || [];
    h += chipsRow('💰 龙虎榜游资净买入 TOP5', hm, function (it, i) {
      return '<span class="chip" title="' + esc((it.stocks || []).slice(0, 3).join('、')) + '">' + (i + 1) + '. ' + esc(it.name) + ' <span class="up">+' + money(it.buying) + '</span>' + (it.stocks && it.stocks.length ? ' · ' + esc(it.stocks.slice(0, 2).join('、')) : '') + '</span>';
    });
    var ld = d.ladder || {};
    var lrows = (ld.rows || []).filter(function (r) { return r.count > 0; });
    if (lrows.length) {
      h += '<div class="ths-sub">📈 连板梯队</div><div class="ths-inline">' + lrows.map(function (r) {
        return '<span class="chip">' + esc(thsBoardLab(r.board)) + ' ' + r.count + ' 家' + (r.names && r.names.length ? ' · ' + esc(r.names.slice(0, 2).join('、')) : '') + '</span>';
      }).join('') + '</div>';
    }
    h += '<div class="ths-foot">同花顺金融数据API · 仅做热点交叉验证，不构成投资建议；数据截至 ' + esc(d.date || '-') + '</div>';
    h = '<details class="bj-fold"><summary>市场情绪 · 交叉验证（进阶数据 · 点击展开）</summary>' + h + '</details>';
    box.innerHTML = h;
  }
  function loadThsSentiment() {
    apiFetch("/api/ths/sentiment").then(function (d) {
      renderThsSentiment(d);
    }).catch(function () {
      var box = $("bj-ths-sentiment");
      if (box) box.innerHTML = "";
    });
  }
  var historyState = { loaded: false };
  function loadHistory() {
    if (historyState.loaded) return;
    historyState.loaded = true;
    Promise.all([
      apiFetch("/api/bj/history?market=all").then(function (d) {
        return { market: "all", list: (d && d.list) || [] };
      }).catch(function () { return { market: "all", list: [] }; }),
      apiFetch("/api/bj/history?market=bj").then(function (d) {
        return { market: "bj", list: (d && d.list) || [] };
      }).catch(function () { return { market: "bj", list: [] }; })
    ]).then(function (groups) {
      renderHistory(groups);
    });
  }
  function dedupByDay(list) {
    // 每天只保留 1 条（后端已按天去重，前端再兜底一次，避免同日多版本重复显示）
    var seen = {}, out = [];
    (list || []).forEach(function (it) {
      var day = String(it.date || "").split(" (")[0];
      if (!day || seen[day]) return;
      seen[day] = true;
      out.push(it);
    });
    return out;
  }
  function historyRow(it, market) {
    var picks = (it.picks || []).map(function (p, pi) {
      var t = p.tier === "king" ? '<span class="t-king">\u2b50</span>' : (p.tier === "key" ? '<span class="t-key">\u2b50</span>' : "");
      return (p.rank || pi + 1) + '. ' + t + '<b>' + esc(p.name) + '</b>' +
        '<span class="hr-code">' + esc(p.code || "") + '</span>' +
        (p.final != null ? '<span class="hr-score">' + esc(p.final) + '</span>' : "");
    }).join('<span class="hr-sep"> \u00b7 </span>');
    var asofTxt = (it.asof && it.asof !== it.date) ? ('<span class="chip-sub">\u622a\u81f3' + esc(it.asof) + '\u6536\u76d8</span>') : "";
    return '<a class="hist-row" href="gd.html?date=' + encodeURIComponent(it.date) + '&market=' + encodeURIComponent(market) + '" target="_blank" rel="noopener" title="\u626b\u63cf\u65e5 ' + esc(it.date) + '\uff08\u6570\u636e\u622a\u81f3 ' + esc(it.asof || it.date) + ' \u6536\u76d8\uff09\u00b7 \u65b0\u7a97\u53e3\u6253\u5f00\u5f52\u6863">' +
      '<span class="hr-date">' + esc(it.date) + asofTxt + '</span>' +
      '<span class="hr-picks">' + (picks || "\u2014") + '</span>' +
      '<span class="hr-go">\u2197</span></a>';
  }
  function renderHistory(groups) {
    var box = $("bj-history");
    if (!box) return;
    groups = groups || [];
    var allList = [], bjList = [];
    groups.forEach(function (g) {
      if (g.market === "all") allList = g.list || [];
      else if (g.market === "bj") bjList = g.list || [];
    });
    allList = dedupByDay(allList);
    bjList = dedupByDay(bjList);
    if (!allList.length && !bjList.length) { box.innerHTML = ""; return; }
    var h = '<div class="hist-card">' +
      '<div class="bj-section hist-title">\u5386\u53f2\u5f52\u6863 \u00b7 \u5f80\u671f\u4e3b\u63a8</div>' +
      '<p class="hist-desc">\u6bcf\u65e5\u4e00\u4efd\uff08\u6309\u6700\u65b0\u7b97\u6cd5\u53e3\u5f84\u00b7\u6700\u7ec8\u7248\uff09\uff0c\u65b0\u7a97\u53e3\u6253\u5f00\u67e5\u770b\u8be5\u65e5\u7ed3\u679c\uff1b\u5386\u53f2\u591a\u7248\u672c\u4ec5\u5b58\u6863\uff0c\u4e0d\u53c2\u4e0e\u9875\u9762\u5c55\u793a</p>';
    h += '<div class="hist-cols">';
    if (allList.length) {
      h += '<div class="hist-col"><div class="bj-section hist-group">\u6caa\u6df1\u4eac\u5168\u5e02\u573a</div><div class="hist-grid">';
      allList.forEach(function (it) { h += historyRow(it, "all"); });
      h += '</div></div>';
    }
    if (bjList.length) {
      h += '<div class="hist-col"><div class="bj-section hist-group">\u5317\u8bc1\u5168\u5e02\u573a</div><div class="hist-grid">';
      bjList.forEach(function (it) { h += historyRow(it, "bj"); });
      h += '</div></div>';
    }
    h += '</div></div>';
    box.innerHTML = h;
  }
  function openArchive(dateKey) {
    if (!dateKey) return;
    setStatus("正在载入历史归档 " + dateKey + " …");
    apiFetch("/api/bj/history?date=" + encodeURIComponent(dateKey) + "&market=" + encodeURIComponent(state.market)).then(function (d) {
      if (!d || d.ok === false) {
        setStatus("归档加载失败：" + esc((d && d.message) || "未知错误"), true);
        return;
      }
      d.archive = true;
      state.data = d;
      var gMain = $("bj-main"); if (gMain) gMain.hidden = false;
      var gGate = $("bj-vipgate"); if (gGate) gGate.hidden = true;
      renderMeta(d);
      renderMainlines(d);
      renderBoardRank(d);
      renderPicks(d);
      setStatus("历史归档 · " + dateKey);
    }).catch(function (e) {
      if (e && e.status === 403) {
        var gMain = $("bj-main"); if (gMain) gMain.hidden = true;
        var gGate = $("bj-vipgate"); if (gGate) gGate.hidden = false;
        setStatus("当前账号未开通 VIP");
        return;
      }
      setStatus("归档加载失败：" + esc((e && e.message) || "网络错误"), true);
    });
  }
  function renderPicks(d) {
    var box = $("bj-result");
    if (!box) return;
    var picks = d.picks || [];
    if (!picks.length) {
      var emptyTitle = d.archive ? '该日期无归档主推记录' : '今日无合格标的';
      var emptySub = d.archive ? '可查看其它日期的历史归档。' : '行情整体偏弱或筛选条件过严，宁缺毋滥；可稍后重扫或放宽参数观察。';
      box.innerHTML = '<div class="bj-empty-alert"><div class="ico">\ud83d\udca1</div><div class="bd"><b>' + esc(emptyTitle) + '</b><span>' + emptySub + '</span></div></div>';
      return;
    }
    var html;
    if (d.archive) {
      html = '<div class="bj-section">历史归档主推（数据日期 ' + esc(d.asof || d.date || "") + '）</div>';
      html += '<div class="notice stale">📂 以下为历史归档结果，仅供研究参考，不构成投资建议；最新结果请回到页面顶部查看。</div>';
    } else if (d.stale) {
      var _tf = d.today_fine || {};
      var _tfTxt = '';
      if (_tf.fine != null) {
        _tfTxt = '今日扫描：达标 ' + _tf.fine + ' 只';
        if (_tf.top && _tf.top.name) {
          _tfTxt += '（最接近：' + esc(_tf.top.name) + ' ' + esc(_tf.top.code || '') + (_tf.top.final != null ? ' · ' + _tf.top.final + ' 分' : '') + (_tf.top.risks && _tf.top.risks.length ? ' · ' + esc(_tf.top.risks.join('；')) : '') + '）';
        }
        _tfTxt += '，均未达主推线（宁缺毋滥）。';
      }
      var _staleNote = d.intraday
        ? '未到收盘（15:03 后自动更新今日）：当前展示上一交易日（' + esc(d.stale_from || "") + '）收盘结果，仅供研究参考，不构成投资建议。'
        : '⚠ 今日（' + esc(d.date || "") + '）扫描无合格标的' + (_tfTxt ? '：' + _tfTxt : '（可能为盘前或数据未更新）') + '，以下为上一交易日（' + esc(d.stale_from || "") + '）收盘结果，仅供研究参考，不构成投资建议。'
      html = '<div class="bj-section">上一交易日主推（数据日期 ' + esc(d.stale_from || d.asof || "") + ' · ' + (d.intraday ? '未到收盘' : '<span class="bj-empty-flag">今日无合格标的</span>') + '）</div>';
      html += '<div class="notice stale">' + _staleNote + '</div>';
    } else {
      var trk = d.prev_track || [];
      if (d.prev_date && trk.length) {
        html = '<div class="bj-section">昨日主推 · 今日跟踪（' + esc(d.prev_date) + '）</div>' +
          '<div class="pt-list">';
        trk.forEach(function (t) {
          var tagCls = t.tag === "ok" ? "st-ok" : (t.tag === "warn" ? "st-warn" : (t.tag === "bad" ? "st-bad" : "st-muted"));
          html += '<div class="pt-item">' +
            '<a class="n" href="' + quoteHref(t) + '" target="_blank" rel="noopener" title="在AI行情官中查看 ' + esc(t.name) + '">' + esc(t.name) + ' <span class="br-code">' + esc(t.code) + '</span> ↗</a>' +
            (t.star ? '<span class="tier-badge tier-king" style="margin-left:4px">⭐</span>' : '') +
            '<span class="pt-status ' + tagCls + '">' + esc(t.status) + '</span>'
            + '</div>';
        });
        html += '</div>' +
          '<div class="pt-note">未破位继续跟踪；破止损 / 放量长阴 -8% 离场；不因新面孔频繁换股。</div>';
      }
      var nPicks = picks.length;
      html = '<div class="bj-section">今日主推（王者⭐ + 重点 · ' + nPicks + ' 只）</div>';
      if (d.mainline_gap) {
        var _mln = (d.mainlines || []).filter(function (m) { return m && m.src === "daily"; })
          .map(function (m) { return esc(m.name || ""); }).filter(Boolean);
        html += '<div class="bj-gap-alert">⚠️ 主线（' + (_mln.length ? _mln.join('、') : '复盘主线') + '）今日暂无低风险合格标的；以下为资金热度龙头/备选，仅作技术面跟踪，<b>不构成主线推荐</b>。</div>';
      }
      if (d.relaxed) {
        html += '<div class="notice">今日严格档无合格标的，采用放宽兜底档（位置/换手/启动门槛小幅放宽，利空硬伤与主线约束不变）。</div>';
      }
      if (nPicks && nPicks < 3) {
        html += '<div class="notice">今日仅 ' + nPicks + ' 只合格：少而精，不强行凑满。</div>';
      }
    }
    html += '<div class="notice">仅供研究整理，不构成投资建议；30CM 波动大，破止损 / 放量长阴 -8% 无条件离场。</div>';
    html += '<div class="pick-grid">';
    picks.forEach(function (p) {
      var chgCls = cls(p.pct);
      var isKing = p.tier === "king";
      var lv = p.levels || {};
      var st = p.strategy || {};
      var _posM = st.position ? String(st.position).match(/\d+(?:\.\d+)?%|\d+(?:\.\d+)?成/) : null;
      var posSpan = st.position ? '<span class="pos">仓位 ' + esc(_posM ? _posM[0] : st.position) + '</span>' : '';
      var stLine = '';
      if (st && (st.entry || st.period)) {
        var stPeriod = String(st.period || '').trim();
        var stEntry = String(st.entry || '').replace(/（现价[^）]*）/g, '').replace(/分批建仓/g, '分批').replace(/，[^，。]*追突破/g, '').trim();
        stLine = '<div class="pick-strategy"><span class="st-tag">波段策略</span>' +
          '<b>' + esc(stPeriod) + '</b> ｜ ' + esc(stEntry) +
          ' ｜ <span class="st-disc">不追高·缩量回踩·破位/长阴-8%离场</span></div>';
      }
      html +=
        '<div class="pick-card' + (isKing ? " king" : (p.tier === "key" ? " key" : "")) + '">' +
        '<div class="pick-head">' +
          '<div class="ph-l"><span class="pick-num">' + (p.rank || 1) + '</span> ' +
            '<a class="pick-name" href="' + quoteHref(p) + '" target="_blank" rel="noopener">' + esc(p.name) + '</a> ' +
            '<span class="pick-code">' + esc(p.code) + '</span>' +
            tierBadge(p) + roleBadge(p) + mainBadge(p) + indBadge(p) +
            (p.relaxed ? '<span class="tier-badge tier-key">放宽档</span>' : '') +
            (p.cont ? '<span class="tier-badge tier-cont">延续⭐</span>' : '') +
          '</div>' +
          '<div class="ph-r"><span class="pick-price ' + chgCls + '">' + num(p.price, 2) + '</span> <span class="' + chgCls + '">' + pct(p.pct) + '</span>' +
            '<a class="view-link" href="' + quoteHref(p) + '" target="_blank" rel="noopener">查看行情 ↗</a></div>' +
        '</div>' +
        coreTags(p) +
        '<div class="pick-sub">最终分 <b>' + (p.final != null ? p.final : "—") + '</b> ｜ 位置 <b>' + num((p.pos != null ? p.pos * 100 : 0), 0) + '%</b> ｜ 市值 ' + money(p.mcap) +
        ' ｜ 成交 ' + money(p.amount) + ' ｜ 5日 ' + pct(p.chg5) + ' ｜ 换手 ' + num(p.turnover, 1) + '%' + '</div>' +
        '<div class="kbox"><canvas data-bj-code="' + esc(p.code) + '"></canvas></div>' +
        '<div class="levels">' +
          '<span class="s">支撑 ' + num(lv.s1, 2) + ' / ' + num(lv.s2, 2) + '</span>' +
          '<span class="p">压力 ' + num(lv.p1, 2) + ' / ' + num(lv.p2, 2) + '</span>' +
          '<span class="stop">止损 ' + num(lv.stop, 2) + '</span>' + posSpan +
        '</div>' +
        stLine +
        fundHtml(p) +
        '<div class="pick-reason">入选逻辑：' + esc(reasonOf(p)) + '</div>' +
        bearishHtml(p) +
        '</div>';
    });
    html += '</div>';
    // runners
    var runners = d.runners || [];
    if (runners.length) {
      html += '<div class="bj-section">备选池（落选原因）</div>';
      html += '<div class="table-scroll"><table class="bj-table"><tr><th>#</th><th>代码</th><th>名称</th><th>现价</th><th>涨跌</th><th>最终分</th><th>位置</th><th>市值</th><th>5日</th><th>20日</th><th>落选原因</th></tr>';
      runners.forEach(function (r, ri) {
        var blBadge = r.bearish_level === "hard" ? "<span style='color:var(--rise)'>硬伤</span>" : (r.bearish_level === "warn" ? "<span style='color:var(--warn)'>警示</span>" : "");
        html += '<tr><td style="color:var(--muted)">' + (ri + 1) + '</td><td style="color:var(--muted)">' + esc(r.code) + '</td><td><a href="demo.html?secid=' + encodeURIComponent(secidForCode(r.code)) + '&period=day" target="_blank" rel="noopener" style="color:var(--bj-acc)">' + esc(r.name) + '</a></td><td class="' + cls(r.pct) + '">' + num(r.price, 2) + '</td><td class="' + cls(r.pct) + '">' + pct(r.pct) + '</td><td>' + (r.final != null ? r.final : "—") + '</td><td>' + num((r.pos != null ? r.pos * 100 : 0), 0) + '%</td><td>' + money(r.mcap) + '</td><td class="' + cls(r.chg5) + '">' + pct(r.chg5) + '</td><td class="' + cls(r.chg20) + '">' + pct(r.chg20) + '</td><td>' + blBadge + ' ' + esc((r.risks || []).join("；") || "排名靠后") + '</td></tr>';
      });
      html += '</table></div>';
    }
    box.innerHTML = html;
    requestAnimationFrame(function () {
      picks.forEach(function (p) {
        var cv = document.querySelector('canvas[data-bj-code="' + p.code + '"]');
        if (cv && p.chart) drawChart(cv, p.chart);
      });
    });
  }
  function drawChart(cv, ch) {
    var cs = ch.closes || [], os = ch.opens || [], hs = ch.highs || [], ls = ch.lows || [], vs = ch.vols || [];
    var N = cs.length;
    if (!N) return;
    var dpr = window.devicePixelRatio || 1;
    var w = cv.clientWidth || 640, h = cv.clientHeight || 340;
    cv.width = w * dpr; cv.height = h * dpr; cv.style.height = h + "px";
    var ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    // 与行情查询页一致的配色（实色，去半透明雾感）
    var UP = "#f03a52", DOWN = "#00b578";
    var MA1 = "#ff8000", MA2 = "#0080ff", MA3 = "#00c853", GRID = "#252b36";
    var padL = 10, padR = 12, padT = 16;
    var macdH = 96, gap = 8, padB = 12;
    var mainH = h - padT - macdH - gap - padB;
    var macdY = padT + mainH + gap;
    ctx.fillStyle = "#0a0c10"; ctx.fillRect(0, 0, w, h);
    function sma(arr, n) {
      var out = [], i, j, s;
      for (i = 0; i < arr.length; i++) {
        if (i < n - 1) { out.push(null); continue; }
        s = 0;
        for (j = i - n + 1; j <= i; j++) s += arr[j];
        out.push(s / n);
      }
      return out;
    }
    function ema(arr, n) {
      var out = [], k = 2 / (n + 1), prev = arr[0], i;
      for (i = 0; i < arr.length; i++) { prev = (i === 0) ? arr[0] : arr[i] * k + prev * (1 - k); out.push(prev); }
      return out;
    }
    var ma1 = ch.ma14 || sma(cs, 14);
    var ma2 = ch.ma28 || sma(cs, 28);
    var ma3 = ch.ma57 || sma(cs, 57);
    var e12 = ema(cs, 12), e26 = ema(cs, 26), dif = [], dea, hist = [], i;
    for (i = 0; i < N; i++) dif.push(e12[i] - e26[i]);
    dea = ema(dif, 9);
    for (i = 0; i < N; i++) hist.push((dif[i] - dea[i]) * 2);
    var crosses = [];
    for (i = 1; i < N; i++) {
      if (dif[i - 1] < dea[i - 1] && dif[i] >= dea[i]) crosses.push({ i: i, gold: true });
      else if (dif[i - 1] > dea[i - 1] && dif[i] <= dea[i]) crosses.push({ i: i, gold: false });
    }
    var hi = Math.max.apply(null, hs), lo = Math.min.apply(null, ls);
    var span = hi - lo || 1, padSpan = span * 0.08;
    hi += padSpan; lo -= padSpan;
    var step = (w - padL - padR) / N;
    function X(i) { return padL + (i + 0.5) * step; }
    function Y(v) { return padT + (hi - v) / (hi - lo) * mainH; }
    // 网格（原版 #252b36）
    ctx.strokeStyle = GRID; ctx.lineWidth = 1;
    for (var g = 0; g <= 4; g++) { var yy = padT + mainH * g / 4; ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(w - padR, yy); ctx.stroke(); }
    var bw = Math.max(1, step * 0.68);
    // 蜡烛
    for (i = 0; i < N; i++) {
      var up = cs[i] >= os[i], col = up ? UP : DOWN;
      ctx.strokeStyle = col; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(X(i), Y(hs[i])); ctx.lineTo(X(i), Y(ls[i])); ctx.stroke();
      ctx.fillStyle = col;
      ctx.fillRect(X(i) - bw / 2, Y(Math.max(os[i], cs[i])), bw, Math.max(1, Math.abs(Y(os[i]) - Y(cs[i]))));
    }
    // 均线（最细 1px，原版三色）
    function line(arr, color) {
      ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath(); var st = false;
      for (var j = 0; j < N; j++) {
        var v = arr[j]; if (v == null || isNaN(v)) continue;
        var px = X(j), py = Y(v);
        if (!st) { ctx.moveTo(px, py); st = true; } else ctx.lineTo(px, py);
      }
      if (st) ctx.stroke();
    }
    line(ma1, MA1); line(ma2, MA2); line(ma3, MA3);
    // 原版信号 markers：小圆点/小箭头/文字全部渲染，同 bar 同向垂直堆叠防覆盖
    var sigs = ch.signals || [];
    var dateIdx = {}, dates = ch.dates || [];
    for (i = 0; i < dates.length; i++) dateIdx[String(dates[i])] = i;
    var usedAbove = {}, usedBelow = {};
    ctx.textAlign = "left";
    for (var mi = 0; mi < sigs.length; mi++) {
      var mk = sigs[mi], t = String(mk.time || "");
      var bi = dateIdx[t];
      if (bi == null || bi < 0 || bi >= N) continue;
      var txt = String(mk.text || "").trim();
      var mcol = mk.color || "#fbbf24";
      var xi = X(bi), yb = Y(hs[bi]), yl = Y(ls[bi]);
      var pos = mk.position || "belowBar";
      var offKey = String(bi) + ":" + pos;
      var off = 0;
      if (pos === "aboveBar") { off = usedAbove[offKey] || 0; usedAbove[offKey] = off + 1; }
      else if (pos === "belowBar") { off = usedBelow[offKey] || 0; usedBelow[offKey] = off + 1; }
      var ay;
      if (pos === "aboveBar") ay = Math.max(yb - 8, padT + 8) - off * 14;
      else if (pos === "belowBar") ay = Math.min(yl + 8, padT + mainH - 8) + off * 14;
      else ay = (yb + yl) / 2;
      var shape = mk.shape || "arrowUp";
      ctx.fillStyle = mcol; ctx.beginPath();
      if (shape === "arrowDown") { ctx.moveTo(xi, ay + 5); ctx.lineTo(xi - 4, ay - 5); ctx.lineTo(xi + 4, ay - 5); }
      else if (shape === "circle") { ctx.arc(xi, ay, 3.5, 0, Math.PI * 2); }
      else if (shape === "square") { ctx.fillRect(xi - 3.5, ay - 3.5, 7, 7); }
      else { ctx.moveTo(xi, ay - 5); ctx.lineTo(xi - 4, ay + 5); ctx.lineTo(xi + 4, ay + 5); }
      ctx.closePath(); ctx.fill();
      if (txt && txt !== "​") {
        ctx.font = "bold 12px Microsoft YaHei";
        ctx.fillStyle = mcol;
        ctx.fillText(txt, xi + 8, ay + 4);
      }
    }
    // 量能（实色高对比）// MACD 副图：柱 + DIF/DEA + 首根红/绿加亮 + 金叉/死叉箭头
    var mLo = Infinity, mHi = -Infinity;
    hist.forEach(function (v) { if (v < mLo) mLo = v; if (v > mHi) mHi = v; });
    dif.forEach(function (v) { if (v < mLo) mLo = v; if (v > mHi) mHi = v; });
    dea.forEach(function (v) { if (v < mLo) mLo = v; if (v > mHi) mHi = v; });
    var mRng = (mHi - mLo) || 1;
    var mPadT = 10, mPadB = 12, mPlotH = macdH - mPadT - mPadB;
    function MY(v) { return macdY + mPadT + (mHi - v) / mRng * mPlotH; }
    var zero = MY(0);
    ctx.strokeStyle = GRID; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, zero); ctx.lineTo(w - padR, zero); ctx.stroke();
    var firstRed = -1, firstGreen = -1;
    for (i = 0; i < N; i++) {
      var hv = hist[i];
      if (hv > 0 && firstRed < 0 && (i === 0 || hist[i - 1] <= 0)) firstRed = i;
      if (hv < 0 && firstGreen < 0 && (i === 0 || hist[i - 1] >= 0)) firstGreen = i;
    }
    var mcw = Math.max(1, step * 0.68);
    for (i = 0; i < N; i++) {
      var hv2 = hist[i];
      if (hv2 == null) continue;
      var hl = (i === firstRed || i === firstGreen);
      var bx0 = X(i) - mcw / 2, bwid = mcw, btop = Math.min(zero, MY(hv2)), bhei = Math.max(1, Math.abs(zero - MY(hv2)));
      if (hl) {
        ctx.fillStyle = hv2 >= 0 ? "#ff5c72" : "#00e68a";
        ctx.fillRect(bx0 - 1, btop - 1, bwid + 2, bhei + 2);
        ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1;
        ctx.strokeRect(bx0 - 1.5, btop - 1.5, bwid + 3, bhei + 3);
      } else {
        ctx.fillStyle = hv2 >= 0 ? "rgba(240,58,82,.8)" : "rgba(0,181,120,.8)";
        ctx.fillRect(bx0, btop, bwid, bhei);
      }
    }
    function mline(arr, color) {
      ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath(); var st = false;
      for (i = 0; i < N; i++) {
        var v = arr[i]; if (v == null) continue;
        var px = X(i), py = MY(v);
        if (!st) { ctx.moveTo(px, py); st = true; } else ctx.lineTo(px, py);
      }
      if (st) ctx.stroke();
    }
    mline(dif, "#e2e8f0"); mline(dea, "#f59e0b");
    for (var ci = 0; ci < crosses.length; ci++) {
      var cx = crosses[ci], cxi = X(cx.i), cyy = MY((dif[cx.i] + dea[cx.i]) / 2);
      ctx.fillStyle = cx.gold ? "#ff1744" : "#00e676";
      ctx.beginPath();
      if (cx.gold) { ctx.moveTo(cxi, cyy - 6); ctx.lineTo(cxi - 5, cyy + 4); ctx.lineTo(cxi + 5, cyy + 4); }
      else { ctx.moveTo(cxi, cyy + 6); ctx.lineTo(cxi - 5, cyy - 4); ctx.lineTo(cxi + 5, cyy - 4); }
      ctx.closePath(); ctx.fill();
    }
  }

  function load(force) {
    if (state.loading) return;
    state.loading = true;
    var seq = ++reqSeq;
    var btn = $("btn-bj-refresh");
    if (btn) { btn.disabled = true; btn.textContent = "扫描中…"; }
    statusLoading();
    waitDeadline = 0;
    if (force) {
      // 异步重扫：先启动后台任务，轮询进度，避免长请求触发 nginx 60s 网关超时（504）
      apiFetch("/api/bj/screener/start?market=" + encodeURIComponent(state.market)).then(function (st) {
        if (seq !== reqSeq) return;
        if (!st || st.ok !== true) {
          state.loading = false;
          stopProgress();
          if (btn) { btn.disabled = false; btn.textContent = "重新扫描"; }
          setStatus("扫描启动失败：" + esc((st && st.message) || "未知错误"), true);
          return;
        }
        waitScanDone(seq, btn);
      }).catch(function (e) { loadFail(e, seq, btn); });
      return;
    }
    // 非强制：若已有扫描在跑则轮询等待，否则直接拉取（命中缓存秒回）
    apiFetch("/api/bj/screener/progress?market=" + encodeURIComponent(state.market)).then(function (p) {
      if (seq !== reqSeq) return;
      if (p && p.running === true) { waitScanDone(seq, btn); return; }
      startProgress(state.market, seq);
      apiFetch("/api/bj/screener?market=" + encodeURIComponent(state.market)).then(function (d) {
        finishLoad(d, seq, btn);
      }).catch(function (e) { loadFail(e, seq, btn); });
    }).catch(function () {
      if (seq !== reqSeq) return;
      startProgress(state.market, seq);
      apiFetch("/api/bj/screener?market=" + encodeURIComponent(state.market)).then(function (d) {
        finishLoad(d, seq, btn);
      }).catch(function (e) { loadFail(e, seq, btn); });
    });
  }

  function waitScanDone(seq, btn) {
    var fill = $("bj-progress-fill"), txt = $("bj-progress-text");
    if (!waitDeadline) waitDeadline = Date.now() + 12 * 60 * 1000;
    apiFetch("/api/bj/screener/progress?market=" + encodeURIComponent(state.market)).then(function (p) {
      if (seq !== reqSeq) return;
      if (Date.now() > waitDeadline) {
        waitDeadline = 0;
        state.loading = false;
        stopProgress();
        if (btn) { btn.disabled = false; btn.textContent = "重新扫描"; }
        setStatus("扫描耗时较长（上游数据源限流），请稍后刷新查看或重新扫描", true);
        return;
      }
      var w = $("bj-progress");
      if (w && p && p.running === true) w.hidden = false;
      if (fill && p) fill.style.width = Math.max(2, Math.min(100, Number(p.pct) || 0)) + "%";
      if (txt && p) txt.textContent = (p && p.msg) || "正在扫描…";
      if (p && p.running === true) {
        progTimer = setTimeout(function () { waitScanDone(seq, btn); }, 1500);
        return;
      }
      // 扫描完成：重置 loading 后拉最新结果（命中缓存）
      waitDeadline = 0;
      state.loading = false;
      load(false);
    }).catch(function () {
      if (seq !== reqSeq) return;
      if (Date.now() > waitDeadline) {
        waitDeadline = 0;
        state.loading = false;
        stopProgress();
        if (btn) { btn.disabled = false; btn.textContent = "重新扫描"; }
        setStatus("扫描耗时较长（上游数据源限流），请稍后刷新查看或重新扫描", true);
        return;
      }
      progTimer = setTimeout(function () { waitScanDone(seq, btn); }, 2000);
    });
  }

  function finishLoad(d, seq, btn) {
    if (seq !== reqSeq) return;
    if (d && d.scanning === true) {
      // 后端已启动后台扫描（无缓存时绝不长时间同步等待，防 504）：转轮询进度
      waitScanDone(seq, btn);
      return;
    }
    applyScanResult(d, seq, btn);
  }
  function applyScanResult(d, seq, btn) {
    if (seq !== reqSeq) return;
    state.loading = false;
    stopProgress();
    if (btn) {
      btn.disabled = false;
      var fresh = d && d.cached && !d.refresh_locked && !d.intraday;
      btn.textContent = fresh ? "已是最新" : "重新扫描";
      btn.title = fresh ? "今日结果已生成，点击可强制重新扫描" : "重新扫描全部标的（120 秒限一次）";
    }
    if (!d || d.ok === false) {
      setStatus("扫描失败：" + esc((d && d.message) || (d && d.error) || "未知错误"), true);
      return;
    }
    state.data = d;
    $("bj-vipgate").hidden = true;
    $("bj-main").hidden = false;
    renderMeta(d);
    renderMainlines(d);
    renderBoardRank(d);
    if (d.vip_required) {
      var pg = $("bj-picksgate");
      if (pg) pg.hidden = false;
      var res = $("bj-result");
      if (res) res.innerHTML = "";
      var hb = $("bj-history");
      if (hb) hb.innerHTML = "";
      var btn2 = $("btn-bj-refresh");
      if (btn2) btn2.style.display = "none";
    } else {
      var pg2 = $("bj-picksgate");
      if (pg2) pg2.hidden = true;
      var btn3 = $("btn-bj-refresh");
      if (btn3) btn3.style.display = "";
      renderPicks(d);
      loadHistory();
    }
    if (d.stale) {
      setStatus("\ud83d\udca1 今日无合格标的（" + fmtDate() + "），展示上一交易日结果", false, true);
    } else if (d.vip_required) {
      setStatus(marketLabel(state.market) + "板块视图已解锁（" + fmtDate() + "）" + (d.cached ? " · 已加载今日缓存" : ""));
    } else {
      setStatus(marketLabel(state.market) + "扫描完成（" + fmtDate() + "）" + (d.cached ? " · 已加载今日缓存" : ""));
    }
  }

  function loadFail(e, seq, btn) {
    if (seq !== reqSeq) return;
    state.loading = false;
    stopProgress();
    if (btn) {
      btn.disabled = false;
      btn.textContent = "重新扫描";
      btn.title = "重新扫描全部标的（120 秒限一次）";
    }
    if (e && e.status === 403) {
      $("bj-main").hidden = true;
      $("bj-vipgate").hidden = false;
      setStatus("当前账号未开通 VIP");
      return;
    }
    if (e && e.status === 401) {
      setStatus("登录已失效，请重新登录后使用", true);
      return;
    }
    setStatus("加载失败：" + esc(e && e.message ? e.message : "网络错误"), true);
  }

  function bindTabs() {
    var tabs = document.querySelectorAll("#bj-tabs .bj-tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener("click", function () {
        if (state.loading) return;
        var m = String(this.getAttribute("data-market") || "bj");
        if (m === state.market) return;
        state.market = m;
        state.data = null;
        historyState = { loaded: false, list: [] };
        var all = document.querySelectorAll("#bj-tabs .bj-tab");
        for (var j = 0; j < all.length; j++) all[j].classList.toggle("active", all[j] === this);
        ["bj-result", "bj-history", "bj-boardrank"].forEach(function (id) {
          var el = $(id); if (el) el.innerHTML = "";
        });
        var meta = $("bj-meta"); if (meta) meta.hidden = true;
        load(false);
      });
    }
  }
  function archiveParams() {
    var out = { date: "", market: "" };
    try {
      var q = location.search || "";
      var m1 = q.match(/[?&]date=([^&]+)/);
      if (m1 && m1[1]) out.date = decodeURIComponent(m1[1]).trim();
      var m2 = q.match(/[?&]market=([^&]+)/);
      if (m2 && m2[1]) out.market = decodeURIComponent(m2[1]).trim();
    } catch (eA) {}
    return out;
  }

  /* —— 大盘环境 + 今日策略（同步「复盘」页 /api/report/*，免费大盘可见，策略/板块/个股 VIP） —— */
  function stripMdLink(t) {
    return String(t || "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*/g, "").replace(/\*\*/g, "").trim();
  }
  function loadMarket() {
    var box = $("bj-market");
    if (!box) return;
    function fill(d, label) {
      if (!d || !d.ok || !d.md) { box.hidden = true; return; }
      renderMarket(d.md, !!d.vip, d.asof || d.date || "", label || "");
    }
    apiFetch("/api/report/today").then(function (d) {
      if (d && d.ok) { fill(d, "今日复盘"); return; }
      apiFetch("/api/report/history").then(function (h) {
        var items = (h && h.items) || [];
        if (!items.length) { box.hidden = true; return; }
        var latest = items[0].date;
        apiFetch("/api/report/" + encodeURIComponent(latest)).then(function (d2) { fill(d2, "最近复盘 " + latest); })
          .catch(function () { box.hidden = true; });
      }).catch(function () { box.hidden = true; });
    }).catch(function () { box.hidden = true; });
  }
  function renderMarket(md, vip, asof, label) {
    var box = $("bj-market");
    if (!box || !md) return;
    var pts = null, pm = md.match(/pts\s*=\s*([\d.]+)/);
    if (pm && pm[1]) pts = Number(pm[1]);
    var env = "warn";
    if (/顺风|金叉确认|空转多/.test(md)) env = "ok";
    else if (/警示/.test(md)) env = "risk";
    else if (pts != null && pts >= 3) env = "ok";
    else if (pts != null && pts <= 0) env = "risk";
    var envTxt = env === "ok" ? "顺风" : (env === "risk" ? "警示" : "中性");
    var envCls = env === "ok" ? "ok" : (env === "risk" ? "risk" : "warn");

    // 指数信号表（前 4）
    var idxRows = [];
    var lines = String(md).split("\n");
    for (var i = 0; i < lines.length && idxRows.length < 4; i++) {
      var L = lines[i].trim();
      var m = L.match(/^\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([\d.]+)\s*\|/);
      if (m) {
        var rest = L.split("|");
        var st = rest.length > 6 ? stripMdLink(rest[6]) : (rest.length > 5 ? "MACD " + stripMdLink(rest[5]) : "");
        idxRows.push({ name: stripMdLink(m[1]), sig: stripMdLink(m[2]).replace(/　/g, " "), score: m[3], st: st });
      }
    }
    var envLine = "";
    var em = md.match(/大盘环境[：:]\s*([^\n]+)/);
    if (em && em[1]) envLine = stripMdLink(em[1]);

    // VIP 策略（full md 才有）
    var mainlines = "", observe = "", avoid = "", ops = "";
    if (vip) {
      var mm = md.match(/主攻主线[：:]\s*\*\*([^*]+)\*\*/) || md.match(/主攻[^：:\n]*[：:]\s*\*\*([^*]+)\*\*/);
      if (mm && mm[1]) mainlines = stripMdLink(mm[1]);
      var om = md.match(/\*{0,2}观察\*{0,2}[：:]\s*([^\n；;]+)/);
      if (om && om[1]) observe = stripMdLink(om[1]);
      var av = md.match(/回避[^：:\n]*[：:]\s*([^\n；;]+)/);
      if (av && av[1]) avoid = stripMdLink(av[1]);
      var op = md.match(/操作原则[：:]\s*([^\n]+)/);
      if (op && op[1]) ops = stripMdLink(op[1]);
    }

    var h = '<div class="bj-section">今日大盘</div><div class="bj-market">';
    h += '<div class="bj-mkt-head"><span class="bj-mkt-badge ' + envCls + '">' + envTxt + '</span>';
    if (pts != null) h += '<span class="bj-mkt-pts">pts=' + pts.toFixed(1) + '</span>';
    if (envLine) h += '<span style="font-size:12px;color:var(--muted);">' + esc(envLine) + '</span>';
    if (label) h += '<span class="bj-mkt-asof">' + esc(label) + (asof ? ' · 数据截至 ' + esc(asof) : '') + '</span>';
    h += '</div>';
    if (idxRows.length) {
      h += '<div class="bj-mkt-idx">';
      for (var j = 0; j < idxRows.length; j++) {
        h += '<div class="bj-mkt-idx-item"><div class="nm">' + esc(idxRows[j].name) + '</div>' +
          '<div class="sg">' + esc(idxRows[j].sig) + '</div>' +
          '<div>评分 <span class="sc">' + esc(idxRows[j].score) + '</span>' + (idxRows[j].st ? ' ｜ ' + esc(idxRows[j].st) : '') + '</div></div>';
      }
      h += '</div>';
    }
    if (vip && (mainlines || observe || avoid || ops)) {
      h += '<div class="bj-mkt-strategy">';
      if (mainlines) h += '<div class="row"><span class="lb">🎯 主攻主线：</span><strong style="color:var(--rise);">' + esc(mainlines) + '</strong></div>';
      if (observe) h += '<div class="row"><span class="lb">👀 观察：</span>' + esc(observe) + '</div>';
      if (avoid) h += '<div class="row"><span class="lb">🚫 回避/等修复：</span><span style="color:var(--muted);">' + esc(avoid) + '</span></div>';
      if (ops) h += '<div class="ops"><span class="lb">📐 操作原则：</span>' + esc(ops) + '</div>';
      h += '</div>';
    } else if (!vip) {
      h += '<div class="bj-mkt-gate">🔒 今日策略（板块选择与潜力个股）为 <b>VIP 专属</b>，开通后自动解锁。<a href="./account.html#vip" rel="noopener">去开通 VIP →</a></div>';
    }
    h += '</div>';
    box.innerHTML = h;
    box.hidden = false;
  }

  function loadWinrate() {
    var box = $("bj-winrate");
    if (!box) return;
    apiFetch("/api/bj/winrate?days=14").then(function (d) {
      if (!d || d.ok === false) return;
      var rate = (d.hit5_rate == null) ? "—" : num(d.hit5_rate, 1) + "%";
      var posRate = (d.pos5_rate == null) ? "—" : num(d.pos5_rate, 1) + "%";
      var stop = (d.stop_rate == null) ? "—" : num(d.stop_rate, 1) + "%";
      var tierTxt = "";
      if (d.by_tier) {
        Object.keys(d.by_tier).forEach(function (k) {
          var b = d.by_tier[k];
          if (b.n) tierTxt += ' ｜ ' + (k === "king" ? "王者" : k === "key" ? "重点" : "其他") + ' ' + b.n + '只·达标' + num(b.n ? b.hit / b.n * 100 : 0, 0) + '%';
        });
      }
      box.innerHTML =
        '<div class="bj-section">系统实测战绩（近 ' + d.n + ' 只 · ' + esc(d.asof) + '）</div>' +
        '<div class="winrate-strip"><span>5日达标率 <b class="up">' + rate + '</b></span>' +
        '<span>5日收正率 <b class="up">' + posRate + '</b></span>' +
        '<span>10日止损率 <b class="down">' + stop + '</b></span>' +
        '<span>跟踪中 ' + d.tracking + ' 只</span>' + tierTxt + '</div>' +
        '<div class="winrate-note">口径：回踩分批入场、破止损离场；5日内最高涨幅≥+5% 计达标。仅系统自我检验，不构成投资建议。</div>';
      box.hidden = false;
    }).catch(function () {});
  }

  function boot() {
    var logged = !!tokenGet();
    var guest = $("auth-guest");
    var user = $("auth-user");
    if (!logged) {
      if (guest) guest.hidden = false;
      if (user) user.hidden = true;
      var gate = $("bj-vipgate"), main = $("bj-main");
      if (gate) gate.hidden = true;
      if (main) main.hidden = true;
      return;
    }
    if (guest) guest.hidden = true;
    if (user) user.hidden = false;
    var btn = $("btn-bj-refresh");
    if (btn) btn.addEventListener("click", function () { load(true); });
    bindTabs();
    var ap = archiveParams();
    if (ap.date) {
      // 历史归档模式：新窗口直达该日结果（不触发扫描）
      if (ap.market === "bj" || ap.market === "all") {
        state.market = ap.market;
        var tabsAll = document.querySelectorAll("#bj-tabs .bj-tab");
        for (var tJ = 0; tJ < tabsAll.length; tJ++) {
          tabsAll[tJ].classList.toggle("active", tabsAll[tJ].getAttribute("data-market") === state.market);
        }
      }
      if (btn) btn.style.display = "none";
      openArchive(ap.date);
      return;
    }
    loadMarket();
    load(false);
    loadThsSentiment();
    loadWinrate();
  }

  return { boot: boot };
})();

