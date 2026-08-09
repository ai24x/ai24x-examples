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

  function setStatus(s, isErr) {
    var el = $("bj-status");
    if (!el) return;
    el.innerHTML = s || "";
    el.style.color = isErr ? "var(--rise)" : "";
  }
  function statusLoading() {
    setStatus('<span class="spin"></span> 正在扫描' + marketLabel(state.market) + '…（北证约 20~40 秒，沪深京约 30~60 秒）');
  }
  var progTimer = null;
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
  function tagHtml(p) {
    var a = p.patterns || {};
    var h = "";
    if (a.surgeStart) h += '<span class="tag ok">底部放量异动·' + (p.surgeDaysAgo || 0) + '天前启动</span>';
    if (a.pullback) h += '<span class="tag ok">异动拉升→回踩企稳</span>';
    if (a.ztPullback) h += '<span class="tag ok strong">涨停级回踩·强势低吸</span>';
    if (a.smallYang) h += '<span class="tag ok">一路小阳</span>';
    if (a.baseUp) h += '<span class="tag ok">底部走多·均线上拐</span>';
    if (a.tightBurst) h += '<span class="tag ok">均线粘合发散</span>';
    if (a.notHot && p.pickRole !== "leader") h += '<span class="tag info">未大幅拉升</span>';
    if (p.pickRole === "leader") h += '<span class="tag warn">主线龙头·资金确认</span>';
    if (p.pickRole === "catchup") h += '<span class="tag ok">板块内补涨卡位</span>';
    if (p.mainHit && p.mainName) h += '<span class="tag ok strong">主线·' + esc(p.mainName) + '</span>';
    if (p.revHit && p.revName) h += '<span class="tag warn">主线反推:' + esc(p.revName) + '</span>';
    if (p.hotName) h += '<span class="tag warn">板块共振:' + esc(p.hotName) + '</span>';
    if (p.kwHits && p.kwHits.length) h += '<span class="tag warn">题材:' + esc(p.kwHits.join("/")) + '</span>';
    if (p.fundIn > 0) h += '<span class="tag info">主力净流入 +' + money(p.fundIn) + '</span>';
    if (p.boardLeader) h += '<span class="tag ok strong">板块龙头</span>';
    if (p.volHealth === 1) h += '<span class="tag ok">涨放量跌缩量</span>';
    if (p.volHealth === -1) h += '<span class="tag risk">跌放量出货</span>';
    if (p.fundStreak) h += '<span class="tag ok">资金连续流入</span>';
    if (p.plateauDays >= 20) h += '<span class="tag ok">平台蓄势' + p.plateauDays + '日</span>';
    if (p.biasOver) h += '<span class="tag warn">乖离偏大</span>';
    var snap = p.snap;
    if (snap && snap.tags) snap.tags.slice(0, 6).forEach(function (t) { h += '<span class="tag info">' + esc(t) + '</span>'; });
    return h;
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
    return r.join("、") || "形态健康";
  }
  function bearishHtml(p) {
    var b = p.bearish || { level: "pass", items: [] };
    var items = b.items || [];
    var fund = p.fund || {};
    var fwarn = [];
    if (fund.flags && fund.flags.length) fwarn = fwarn.concat(fund.flags.map(function (t) { return "业绩红旗：" + t; }));
    if (fund.newsHard && fund.newsHard.length) fwarn = fwarn.concat(fund.newsHard.map(function (t) { return "消息硬伤：" + t; }));
    if (fund.newsWarn && fund.newsWarn.length) fwarn = fwarn.concat(fund.newsWarn.slice(0, 3).map(function (t) { return "消息警示：" + t; }));
    var isHard = b.level === "hard" || fund.level === "hard";
    var isWarn = b.level === "warn" || fund.level === "warn" || fwarn.length > 0;
    var h = "";
    if (isHard) h = '<div class="bearish"><span class="t">↓ 利空排查：硬伤（不应进入）</span>';
    else if (isWarn) h = '<div class="bearish warn"><span class="t">↓ 利空排查：警示</span>';
    else h = '<div class="bearish pass"><span class="t">✓ 利空排查：通过</span><span class="it">无硬伤/无警示</span>';
    h += items.map(function (it) { return '<span class="it">' + esc(it.text) + '</span>'; }).join("");
    h += fwarn.map(function (t) { return '<span class="it">' + esc(t) + '</span>'; }).join("");
    h += '</div>';
    return h;
  }
  function strategyHtml(p) {
    var st = p.strategy;
    if (!st) return "";
    return '<div class="strategy"><span class="t">☆ 中线波段策略</span> ' + esc(st.period) + '<br/>' +
      '入场：<b>' + esc(st.entry) + '</b><br/>' +
      '止损：<b>' + esc(st.stop) + '</b><br/>' +
      '目标：<b>' + esc(st.target1) + '</b> ～ <b>' + esc(st.target2) + '</b><br/>' +
      '仓位：<b>' + esc(st.position) + '</b><br/>' +
      '条件：' + esc(st.conditions) + '</div>';
  }
  function scarcityHtml(p) {
    var sc = p.scarcity || {};
    var tags = sc.tags || [];
    if (!tags.length) return '<div class="pick-scarcity">稀缺性：一般（行业/流通盘无稀缺加成）</div>';
    return '<div class="pick-scarcity">稀缺性：' + tags.map(esc).join(' ｜ ') + '（+' + num(sc.score, 0) + '）</div>';
  }
  function fundHtml(p) {
    var f = (p.fund || {}).fin;
    if (!f) return '<div class="pick-fund">业绩成长：数据暂缺</div>';
    var g = p.fund || {};
    var np = (f.npYoy == null) ? "—" : num(f.npYoy, 1) + "%";
    var rv = (f.revYoy == null) ? "—" : num(f.revYoy, 1) + "%";
    var npCls = (f.npYoy == null) ? "" : (f.npYoy >= 0 ? "up" : "down");
    var rvCls = (f.revYoy == null) ? "" : (f.revYoy >= 0 ? "up" : "down");
    var roe = (f.roe == null) ? "—" : num(f.roe, 1) + "%";
    var gm = (f.gross == null) ? "—" : num(f.gross, 1) + "%";
    return '<div class="pick-fund">业绩成长（' + esc(f.report || "最新报告期") + '）：净利 <b class="' + npCls + '">' + np + '</b> ｜ 营收 <b class="' + rvCls + '">' + rv + '</b> ｜ ROE ' + roe + ' ｜ 毛利率 ' + gm + ' ｜ 成长分 <b>' + num(g.growth, 0) + '</b></div>';
  }
  function factorsHtml(p) {
    var f = p.factors || {};
    if (!f.rsi14 && f.rsi14 !== 0) return "";
    var rsiTxt = f.rsi14 >= 80 ? "超买" : (f.rsi14 >= 55 ? "强势" : "中性");
    return '<div class="pick-factors">多因子：RSI(14) <b>' + num(f.rsi14, 1) + '</b>(' + rsiTxt + ') ｜ 布林位置 <b>' + num(f.boll_pos, 2) + '</b> ｜ 波动幅 <b>' + num(f.atr_pct, 1) + '%</b> ｜ 6日乖离 <b>' + num(f.bias6, 1) + '%</b> ｜ MACD红柱 <b>' + f.gc_days + '</b>天 ｜ PE <b>' + num(f.pe, 1) + '</b> ｜ PB <b>' + num(f.pb, 1) + '</b> ｜ 市值 <b>' + num(f.mcap_yi, 1) + '亿</b></div>';
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
    if (d.off_market) line += "<br/><span style='color:var(--warn)'>⏸ 非交易日：以下为最近交易日（" + esc(d.stale_from || "") + "）归档结果</span>"; else if (d.stale) line += "<br/><span style='color:var(--warn)'>⚠ 今日无合格标的，以下展示上一交易日（" + esc(d.stale_from || "") + "）结果</span>";
    if (d.cached && !d.vip_required) line += ' <span class="bj-cached">（今日结果已缓存，点「重新扫描」刷新）</span>';
    el.innerHTML = line;
    el.hidden = false;
  }
  function renderMainlines(d) {
    var box = $("bj-mainlines");
    if (!box) return;
    var ml = (d.mainlines || []).filter(function (m) { return m && m.src === "daily"; });
    if (!ml.length) { box.innerHTML = ""; return; }
    var h = '<div class="bj-section">主攻主线（同步复盘）</div>' +
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
    var mains = (d.mainlines || []).filter(function (m) { return m && m.src === "daily"; })
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
    var h = '<div class="bj-section">' + (isAll
      ? "板块排行 · 主线优先 + 资金热度（主线=复盘双确认；序号=排名；⭐王者 + 重点 + 备选；点击板块名称新窗口查看行情）"
      : "板块排行 · 底部异动观察（主线以复盘为准；序号=排名；⭐王者 + 重点 + 备选；点击板块名称新窗口查看行情）") + '</div>' +
      (isAll
        ? '<div class="bj-note">💡 怎么用：想动手做板块 → 以「主攻主线」为准（资金+技术双确认）；本榜仅反映资金热度，热度高 ≠ 能追，破位/超买勿左侧。</div>'
        : '<div class="bj-note">💡 怎么用：想动手做板块 → 以「主攻主线」为准；本榜=底部异动观察，异动后需回踩企稳再介入。</div>') +
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
    h = '<details class="bj-fold"><summary>板块排行与资金热度（进阶数据 · 点击展开）</summary>' + h + '</details>';
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
    var h = '<div class="bj-section">同花顺情绪面 · 交叉验证</div>';
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
    var picks = (it.picks || []).map(function (p) {
      var t = p.tier === "king" ? '<span class="t-king">\u2b50</span>' : (p.tier === "key" ? '<span class="t-key">\u25cf</span>' : "");
      return t + esc(p.name);
    }).join(" \u00b7 ");
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
      '<p class="hist-desc">\u6bcf\u65e5\u4e00\u4efd\uff0c\u65b0\u7a97\u53e3\u6253\u5f00\u67e5\u770b\u8be5\u65e5\u7ed3\u679c\uff0c\u65e0\u9700\u91cd\u65b0\u626b\u63cf</p>';
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
      box.innerHTML = '<div class="notice">今日无合格标的：行情整体偏弱或筛选条件过严，可稍后再扫或放宽参数观察。</div>';
      return;
    }
    var html;
    if (d.archive) {
      html = '<div class="bj-section">历史归档主推（数据日期 ' + esc(d.asof || d.date || "") + '）</div>';
      html += '<div class="notice stale">📂 以下为历史归档结果，仅供研究参考，不构成投资建议；最新结果请回到页面顶部查看。</div>';
    } else if (d.stale) {
      html = '<div class="bj-section">上一交易日主推（数据日期 ' + esc(d.stale_from || d.asof || "") + ' · 今日无合格标的）</div>';
      html += '<div class="notice stale">⚠ 今日（' + esc(d.date || "") + '）扫描无合格标的（可能为盘前或数据未更新），以下为上一交易日（' + esc(d.stale_from || "") + '）收盘结果，仅供研究参考，不构成投资建议。</div>';
    } else {
      var nPicks = picks.length;
      var nLeader = 0, nCatch = 0;
      picks.forEach(function (p) { if (p.pickRole === "leader") nLeader++; else if (p.pickRole === "catchup") nCatch++; });
      var roleTxt = "";
      if (nLeader) roleTxt += " · 主线龙头" + nLeader;
      if (nCatch) roleTxt += " · 补涨卡位" + nCatch;
      html = '<div class="bj-section">今日主推（王者⭐ + 重点，共 ' + nPicks + ' 只' + roleTxt + '）</div>';
      if (nPicks && nPicks < 3) {
        html += '<div class="notice">今日合格标的仅 ' + nPicks + ' 只：行情宽度偏弱或筛选条件严格时宁缺毋滥，不强行凑满，供重点跟踪。</div>';
      }
    }
    html += '<div class="notice">本页仅作研究与信息整理，不构成任何投资建议；30CM 波动大，破止损或单日放量长阴 -8% 无条件离场。</div>';
    html += '<div class="pick-grid">';
    picks.forEach(function (p) {
      var chgCls = cls(p.pct);
      var isKing = p.tier === "king";
      var rf = p.risk_free === true;
      var riskTxt = rf ? "<span style='color:var(--fall)'>风险提示通过</span>" : "<span style='color:var(--warn)'>含警示标签</span>";
      html +=
        '<div class="pick-card' + (isKing ? " king" : (p.tier === "key" ? " key" : "")) + '">' +
        '<div class="pick-head">' +
          '<div><span class="pick-num">' + (p.rank || 1) + '</span> ' +
            '<a class="pick-name" href="' + quoteHref(p) + '" target="_blank" rel="noopener">' + esc(p.name) + '</a> ' +
            '<span style="color:var(--muted);font-size:12px">' + esc(p.code) + '</span>' +
            tierBadge(p) + roleBadge(p) +
            '<a class="view-link" href="' + quoteHref(p) + '" target="_blank" rel="noopener">查看行情 ↗</a>' +
          '</div>' +
          '<div style="text-align:right"><span class="pick-price ' + chgCls + '">' + num(p.price, 2) + '</span> <span class="' + chgCls + '" style="font-size:14px;font-weight:700">' + pct(p.pct) + '</span></div>' +
        '</div>' +
        '<div style="margin:8px 0 4px">' + tagHtml(p) + '</div>' +
        '<div class="pick-sub">形态分 <b>' + (p.score != null ? p.score : "—") + '</b> ｜ 最终分 <b>' + (p.final != null ? p.final : "—") + '</b> ｜ 位置 <b>' + num((p.pos != null ? p.pos * 100 : 0), 0) + '%</b> ｜ 市值 ' + money(p.mcap) +
        ' ｜ 成交 ' + money(p.amount) + ' ｜ 5日 ' + pct(p.chg5) + ' ｜ 10日 ' + pct(p.chg10) + ' ｜ 20日 ' + pct(p.chg20) + ' ｜ 换手 ' + num(p.turnover, 1) + '% ｜ ' + riskTxt + '</div>' +
        scarcityHtml(p) + fundHtml(p) + factorsHtml(p) +
        '<div class="levels">' +
          '<span class="s">支撑 ' + num((p.levels || {}).s1, 2) + ' / ' + num((p.levels || {}).s2, 2) + '(MA20)</span>' +
          '<span class="p">压力 ' + num((p.levels || {}).p1, 2) + ' / ' + num((p.levels || {}).p2, 2) + '(60日高)</span>' +
          '<span class="stop">止损 ' + num((p.levels || {}).stop, 2) + '</span>' +
        '</div>' +
        '<div class="kbox"><canvas data-bj-code="' + esc(p.code) + '"></canvas></div>' +
        '<div style="font-size:12px;color:var(--muted)">入选逻辑：' + esc(reasonOf(p)) + '</div>' +
        strategyHtml(p) +
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
    var w = cv.clientWidth || 640, h = cv.clientHeight || 190;
    cv.width = w * dpr; cv.height = h * dpr; cv.style.height = h + "px";
    var ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    var padL = 8, padR = 52, padT = 14, padB = 16, volH = 34;
    var pw = w - padL - padR, ph = h - padT - padB - volH;
    var hi = Math.max.apply(null, hs), lo = Math.min.apply(null, ls);
    var span = hi - lo || 1, padSpan = span * 0.08;
    hi += padSpan; lo -= padSpan;
    function X(i) { return padL + i * (pw / N); }
    function Y(v) { return padT + (hi - v) / (hi - lo) * ph; }
    function Yv(v) { var mx = Math.max.apply(null, vs) || 1; return padT + ph + volH - (v / mx) * volH; }
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#e2e6ec"; ctx.lineWidth = 1;
    for (var g = 0; g <= 4; g++) { var yy = padT + ph * g / 4; ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(w - padR, yy); ctx.stroke(); }
    var bw = Math.max(1, pw / N * 0.62);
    for (var i = 0; i < N; i++) {
      var up = cs[i] >= os[i]; var col = up ? "#e53935" : "#2e7d32";
      ctx.strokeStyle = col; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(X(i), Y(hs[i])); ctx.lineTo(X(i), Y(ls[i])); ctx.stroke();
      ctx.fillStyle = col;
      ctx.fillRect(X(i) - bw / 2, Y(Math.max(os[i], cs[i])), bw, Math.max(1, Math.abs(Y(os[i]) - Y(cs[i]))));
      ctx.fillStyle = up ? "rgba(229,57,53,.55)" : "rgba(46,125,50,.55)";
      ctx.fillRect(X(i) - bw / 2, Yv(vs[i]), bw, Math.max(1, Yv(0) - Yv(vs[i])));
    }
    function line(arr, color) {
      ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.beginPath(); var drawn = false;
      for (var j = 0; j < N; j++) {
        var v = arr[j]; if (v == null || isNaN(v)) continue;
        if (!drawn) { ctx.moveTo(X(j), Y(v)); drawn = true; } else ctx.lineTo(X(j), Y(v));
      }
      if (drawn) ctx.stroke();
    }
    line(ch.ma5, "#fb8c00"); line(ch.ma10, "#1e88e5"); line(ch.ma20, "#8e24aa");
    function hline(v, color, label) {
      if (v == null || isNaN(v)) return;
      ctx.strokeStyle = color; ctx.setLineDash([5, 4]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(padL, Y(v)); ctx.lineTo(w - padR, Y(v)); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = color; ctx.font = "10px Microsoft YaHei";
      ctx.fillText(label + " " + num(v, 2), w - padR + 4, Y(v) - 3);
    }
    hline(ch.p1, "#c62828", "压力"); hline(ch.s1, "#2e7d32", "支撑"); hline(ch.s2, "#2e7d32", "MA20");
    ctx.fillStyle = "#5a6472"; ctx.font = "10px Microsoft YaHei";
    ctx.fillText("MA5橙 MA10蓝 MA20紫", padL, h - 4);
  }

  function load(force) {
    if (state.loading) return;
    state.loading = true;
    var seq = ++reqSeq;
    var btn = $("btn-bj-refresh");
    if (btn) { btn.disabled = true; btn.textContent = "扫描中…"; }
    statusLoading();
    startProgress(state.market, seq);
    apiFetch("/api/bj/screener?market=" + encodeURIComponent(state.market) + (force ? "&force=1" : "")).then(function (d) {
      if (seq !== reqSeq) return;
      state.loading = false;
      stopProgress();
      if (btn) {
        btn.disabled = false;
        var fresh = d && d.cached && !d.refresh_locked;
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
        setStatus("今日无合格标的（" + fmtDate() + "），展示上一交易日结果");
      } else if (d.vip_required) {
        setStatus(marketLabel(state.market) + "板块视图已解锁（" + fmtDate() + "）" + (d.cached ? " · 已加载今日缓存" : ""));
      } else {
        setStatus(marketLabel(state.market) + "扫描完成（" + fmtDate() + "）" + (d.cached ? " · 已加载今日缓存" : ""));
      }
    }).catch(function (e) {
      if (seq !== reqSeq) return;
      state.loading = false;
      stopProgress();
      if (btn) {
        btn.disabled = false;
        var fresh = d && d.cached && !d.refresh_locked;
        btn.textContent = fresh ? "已是最新" : "重新扫描";
        btn.title = fresh ? "今日结果已生成，点击可强制重新扫描" : "重新扫描全部标的（120 秒限一次）";
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
    });
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
    load(false);
    loadThsSentiment();
  }

  return { boot: boot };
})();

