/* AI24X 复盘 VIP 页（gd.html）—— 前端只负责展示，算法全部在服务端 /api/bj/screener */
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
  function money(v) {
    if (v == null || !isFinite(v)) return "—";
    var a = Math.abs(v);
    var s = v < 0 ? "-" : "";
    if (a >= 1e8) return s + (a / 1e8).toFixed(1) + "亿";
    if (a >= 1e4) return s + (a / 1e4).toFixed(0) + "万";
    if (a < 1) return "0";
    return s + a.toFixed(0);
  }
  function moneyYi(v) {
    if (v == null || !isFinite(v)) return "—";
    var a = Math.abs(v);
    if (a < 1e5) return "—";
    var s = v < 0 ? "-" : "";
    if (a >= 1e8) return s + Math.round(a / 1e8) + "亿";
    return s + (a / 1e8).toFixed(1) + "亿";
  }
  function pct(v) { if (v == null || !isFinite(v)) return "—"; return (v >= 0 ? "+" : "") + v.toFixed(2) + "%"; }
  function cls(v) { return v > 0 ? "up" : (v < 0 ? "down" : ""); }
  function fmtDate() { var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  // 数据日统一口径：今日收盘更新完成 → 今日；盘前/盘中/非交易日/今日未生成/今日无合格（展示最近归档）→ 昨日；归档 → 具体日期
  function dataDayLabel(d) {
    if (!d) return "今日";
    if (d.archive) return String(d.asof || d.date || "");
    if (d.off_market || d.intraday || d.stale || d.today_missing) return "昨日";
    return "今日";
  }
  function staleLabel(d) {
    var sf = (d && d.stale_from) || "";
    if (!sf) return "";
    var sd = (d && d.stale_scan_date && d.stale_scan_date !== sf)
      ? "（" + esc(d.stale_scan_date) + " 扫描 · 数据截至 " + esc(sf) + " 收盘）"
      : "（数据截至 " + esc(sf) + " 收盘）";
    return sd;
  }
  function reportDayLabel(d) {
    var dt = String((d && (d.date || d.asof)) || "");
    return (dt && dt === fmtDate() ? "今日" : "昨日") + "大盘";
  }
  function marketLabel(m) {
    if (m === "hs") return "沪深主线";
    if (m === "kc") return "科创主线";
    if (m === "bj") return "北证主线";
    if (m === "bj_all") return "北证全市场";
    if (m === "macd") return "MACD首红";
    if (m === "pb") return "回踩企稳";
    if (m === "low10") return "10元下";
    return m === "all" ? "沪深京全市场" : "北证全市场";
  }
  function marketScope(d) {
    var m = (d && d.market_code) || state.market;
    if (m === "hs") return "沪深主线 · 看主线板块里刚转强的票";
    if (m === "kc") return "科创主线 · 科创板主线里刚转强的票";
    if (m === "bj") return "北证主线 · 北证主线里刚转强的票";
    if (m === "bj_all") return "北证全市场 · 全市场里刚转强的活跃票";
    if (m === "macd") return "MACD首红 · 底部刚翻红的启动信号";
    if (m === "pb") return "回踩企稳 · 异动/首板后缩量回踩未破位";
    if (m === "low10") return "10元下 · 低价且刚右侧走强的活跃票";
    return m === "all" ? "沪深京全市场" : "北证全市场";
  }
  function marketHint(d) {
    var m = (d && d.market_code) || state.market;
    // 主线页已有视觉舱，不再塞教学长文；仅特殊栏目给一句提示
    var one = {
      macd: "底部刚翻红 + 有量",
      pb: "异动后缩量回踩、未破位",
      low10: "股价 <10 元且刚转强",
      bj_all: "全市场 · 宁缺毋滥"
    };
    if (!one[m]) return "";
    return '<div class="bj-note" style="margin:0 0 10px">' + one[m] + '</div>';
  }
  function pathTags(p) {
    var h = [];
    if (p.downSlope) h.push('<span class="tag path-down">下坡途中·已排除</span>');
    else if (p.pathOk) h.push('<span class="tag path-up">上涨途中</span>');
    if (p.activeOk) h.push('<span class="tag path-active">股性活跃' + (p.activityScore != null ? '·' + p.activityScore : '') + '</span>');
    else if (p.activityScore != null && p.activityScore < 35) h.push('<span class="tag path-dull">股性偏弱</span>');
    if (p.midUpOk && p.pathOk) h.push('<span class="tag path-mid">途中未过热</span>');
    return h;
  }

  var state = { loading: false, data: null, market: "hs", cache: {} };
  var reqSeq = 0;

  function setStatus(s, isErr, isWarn) {
    var el = $("bj-status");
    if (!el) return;
    el.innerHTML = s || "";
    el.style.color = isErr ? "var(--rise)" : (isWarn ? "var(--warn)" : "");
    el.style.fontWeight = isWarn ? "800" : "";
  }
  function statusLoading() {
    if (state.market === "macd") {
      setStatus('<span class="spin"></span> 正在扫描MACD首红…（沪深京全市场，约 1~2 分钟）');
      return;
    }
    setStatus('<span class="spin"></span> 正在扫描' + marketLabel(state.market) + '…（沪深/科创约 30~60 秒，北证约 20~40 秒）');
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
        if (p && p.running === true) {
          apiFetch("/api/bj/screener/partial?market=" + encodeURIComponent(state.market)).then(function (part) {
            if (seq !== reqSeq || !part || part.partial !== true) return;
            state.data = part;
            renderMeta(part);
            renderMainlines(part);
            renderPartialPreview(part);
          }).catch(function () {});
        }
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
    return "demo.html?secid=" + encodeURIComponent(secidForCode(p.code)) + "&period=day" + (p.name ? "&name=" + encodeURIComponent(p.name) : "");
  }
  function sanitizeSt(t) {
    return String(t || "")
      .replace(/（现价[^）]*）/g, "")
      .replace(/，[^，。]*追突破/g, "")
      .replace(/分批建仓/g, "分批")
      .replace(/分批/g, "参考区间")
      .replace(/轻仓/g, "")
      .replace(/追突破/g, "")
      .replace(/建仓/g, "")
      .replace(/低吸/g, "")
      .replace(/放弃\/减半/g, "")
      .replace(/减半/g, "")
      .replace(/止损价/g, "参考位")
      .replace(/无条件离场/g, "注意风险")
      .replace(/离场/g, "注意风险")
      .replace(/\s+/g, " ")
      .trim();
  }
  function sanitizeOps(t) {
    var s2 = String(t || "");
    // 历史归档大盘报告的旧操作文案 -> 中性风险提示
    s2 = s2.replace(/右侧确认后总仓[^；;]+/g, "注意控制仓位风险")
      .replace(/主线不追高、等回踩/g, "避免盲目追高")
      .replace(/等回踩/g, "")
      .replace(/总仓从严[^；;]+/g, "从严控制仓位")
      .replace(/再进攻/g, "再观察")
      .replace(/可低吸/g, "关注回踩企稳")
      .replace(/破位即撤/g, "破位注意风险")
      .replace(/只做回踩低吸/g, "优先跟踪回踩企稳")
      .replace(/无条件离场/g, "注意风险")
      .replace(/离场/g, "注意风险")
      .replace(/本报告不构成投资建议。?/g, "")
      .replace(/不构成投资建议。?/g, "")
      .replace(/；+$/g, "。")
      .replace(/\s+/g, " ")
      .trim();
    return s2;
  }
  function tierBadge(p) {
    if (p.tier === "king") return '<span class="tier-badge tier-king">⭐ 评分最高</span>';
    if (p.tier === "key") return '<span class="tier-badge tier-key">评分次高</span>';
    return "";
  }
  function roleBadge(p) {
    if (p.pickRole === "leader") return p.obsHit
      ? '<span class="tier-badge tier-obs">重点观察代表</span>'
      : '<span class="tier-badge tier-leader">主线代表</span>';
    if (p.pickRole === "catchup") return '<span class="tier-badge tier-catchup">补涨观察</span>';
    return "";
  }
  function mainBadge(p) {
    if (p.mainHit) return '<span class="tier-badge tier-main">主线·' + esc(p.mainName || "") + '</span>';
    if (p.obsHit) return '<span class="tier-badge tier-obs">重点观察·' + esc(p.obsName || "") + '</span>';
    return '<span class="tier-badge tier-offmain">非主线</span>';
  }
  function indBadge(p) {
    if (p.ind && p.ind !== "-") return '<span class="tier-badge tier-ind">' + esc(p.ind) + '</span>';
    return "";
  }
  function coreTags(p) {
    var a = p.patterns || {}, h = pathTags(p);
    if (a.firstWeek) h.push('<span class="tag ok strong">近1周首板\u00b7底部右侧</span>');
    else if (a.ztWeek) h.push('<span class="tag ok strong">近1周涨停</span>');
    if (a.pb45) h.push('<span class="tag ok strong">首板4-5日回踩企稳</span>');
    if (a.washOut) h.push('<span class="tag ok strong">单日砸盘企稳\u00b7' + (p.washoutDays || 0) + '天前</span>');
    if (a.surgeStart) h.push('<span class="tag ok">底部异动·' + (p.surgeDaysAgo || 0) + '天前</span>');
    if (a.surgePullback) h.push('<span class="tag ok strong">异动回踩企稳·' + (p.surgePullbackDays || 0) + '天前</span>');
    if (a.ztPullback) h.push('<span class="tag ok strong">涨停级回踩</span>');
    else if (a.pullback) h.push('<span class="tag ok">异动回踩企稳</span>');
    if (a.firstBoardRight) h.push('<span class="tag ok strong">首板右侧上拐</span>');
    if (a.breakout) h.push('<span class="tag ok strong">二波突破</span>');
    if (a.pullback2) h.push('<span class="tag ok strong">板后回踩\u00b7' + (p.pullback2Days || 0) + '天前</span>');
    if (a.macdFirstRed) h.push('<span class="tag ok strong">MACD首根红柱\u00b7' + (p.macdFirstRedDays > 0 ? p.macdFirstRedDays + '天前' : '今日首红') + '</span>');
    if (a.weekConfirm) h.push('<span class="tag ok strong">周线金叉·中期确认</span>');
    if (a.steadyUp) h.push('<span class="tag ok strong">稳步向上\u00b7趋势' + (p.trendScore != null ? p.trendScore : "") + '</span>');
    // 主线已在头部徽章显示，标签区不再重复
    if (a.baseUp) h.push('<span class="tag ok">底部走多</span>');
    if (a.smallYang) h.push('<span class="tag ok">一路小阳</span>');
    if (a.tightBurst) h.push('<span class="tag ok">均线发散</span>');
    if (p.boardLeader) h.push('<span class="tag ok strong">板块代表</span>');
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
    if (a.firstWeek) r.push("近1周首板\u00b7底部右侧刚启动");
    else if (a.ztWeek && !a.firstBoardRight && !a.ztPullback && !a.pullback2) r.push("近1周有涨停\u00b7强势确认");
    if (a.pb45) r.push("首板4-5日回踩·未破位企稳");
    if (a.washOut) r.push("异动10%+后单日砸盘未破位·缩量企稳");
    if (a.surgeStart) r.push("底部放量异动" + (p.surgeDaysAgo || 0) + "天前启动");
    if (a.surgePullback) r.push("放量异动后缩量回踩" + (p.surgePullbackDays || 0) + "日企稳未破位");
    if (a.pullback) r.push("异动拉升后缩量回踩企稳");
    if (a.ztPullback) r.push("涨停级回踩企稳");
    if (a.firstBoardRight) r.push("首板右侧上拐·回调企稳后放量转强");
    if (a.breakout) r.push("放量突破板日/平台高点·二波启动");
    if (a.pullback2) r.push("2周内涨停板后回踩企稳");
    if (a.macdFirstRed) r.push("底部金叉首根红柱" + (p.macdFirstRedDays > 0 ? p.macdFirstRedDays + "天前翻红" : "今日翻红"));
    if (a.weekConfirm) r.push("周线金叉/拐头+放量·中期确认");
    if (a.steadyUp) r.push("稳步向上·趋势评分" + (p.trendScore != null ? p.trendScore : ""));
    if (a.smallYang) r.push("连续小阳趋势上拐");
    if (a.baseUp) r.push("站上MA20且均线上拐");
    if (a.tightBurst) r.push("均线粘合后发散");
    if (p.obsHit && p.obsName) r.push("重点观察:" + p.obsName);
    if (p.mainHit && p.mainName) r.push("主线板块:" + p.mainName);
    if (p.revHit && p.revName) r.push("主线反推共振:" + p.revName);
    if (p.boardLeader) r.push("板块代表");
    if (p.hotName) r.push("板块共振:" + p.hotName);
    if (p.snap && p.snap.score != null) r.push("AI综合分" + num(p.snap.score, 0));
    if (r.length > 3) r = r.slice(0, 3);
    return r.join("、") || "形态健康";
  }
  function runnerTags(r) {
    var a = r.patterns || {}, t = [];
    if (a.firstWeek) t.push('<span class="tag ok strong">近1周首板</span>');
    else if (a.ztWeek) t.push('<span class="tag ok strong">近1周涨停</span>');
    if (a.pb45) t.push('<span class="tag ok strong">首板4-5日回踩</span>');
    if (a.washOut) t.push('<span class="tag ok strong">单日砸盘企稳</span>');
    if (a.macdFirstRed) t.push('<span class="tag ok strong">MACD首红\u00b7' + (r.macdFirstRedDays > 0 ? r.macdFirstRedDays + '天前' : '今日首红') + '</span>');
    if (a.weekConfirm) t.push('<span class="tag ok strong">周线金叉</span>');
    if (a.surgeStart) t.push('<span class="tag ok">底部异动·' + (r.surgeDaysAgo || 0) + '天前</span>');
    if (a.surgePullback) t.push('<span class="tag ok strong">异动回踩企稳·' + (r.surgePullbackDays || 0) + '天前</span>');
    if (a.pullback2) t.push('<span class="tag ok strong">板后回踩·' + (r.pullback2Days || 0) + '天前</span>');
    if (a.ztPullback) t.push('<span class="tag ok strong">涨停级回踩</span>');
    else if (a.pullback) t.push('<span class="tag ok">异动回踩</span>');
    if (a.firstBoardRight) t.push('<span class="tag ok strong">首板右侧上拐</span>');
    if (a.breakout) t.push('<span class="tag ok strong">二波突破</span>');
    if (a.steadyUp) t.push('<span class="tag ok strong">稳步向上</span>');
    if (a.baseUp) t.push('<span class="tag ok">底部走多</span>');
    return t.length ? '<span class="runner-tags">' + t.slice(0, 2).join('') + '</span>' : '';
  }
  function redDaysTag(m) {
    var d = m.macdFirstRedDays;
    if (d == null && m.red_days != null) d = Math.max(0, Number(m.red_days) - 1);
    d = Number(d);
    if (!isFinite(d) || d < 0) d = 0;
    if (d === 0) return '<span class="tag ok strong">今日首红</span>';
    return '<span class="tag ok strong">红柱第' + (d + 1) + '天</span>';
  }
  function macdRedSection(d) {
    var list = d.macd_reds || [];
    if (!list.length) return "";
    var h = '<div class="bj-section">🔥 MACD首红 · 底部刚翻红（' + list.length + ' 只）</div>';
      h += '<div class="bj-note">看两点就够：① 底部刚出现第一根红柱；② 有量配合。优先「今日首红 / 红柱第2-3天」，下坡途中的不会进榜。</div>';
    h += '<div class="mr-grid">';
    list.forEach(function (m, i) {
      var pchg = (m.pct != null && isFinite(Number(m.pct))) ? Number(m.pct)
        : ((m.up_pct != null && isFinite(Number(m.up_pct))) ? Number(m.up_pct) : null);
      var chgCls = cls(pchg);
      var posV = m.pos;
      if (posV != null && isFinite(Number(posV)) && Number(posV) > 1.5) posV = Number(posV) / 100;
      var fin = (m.final != null) ? m.final : m.score;
      var badge = m.mainHit ? '<span class="tier-badge tier-main">主线·' + esc(m.mainName || "") + '</span>'
        : (m.obsHit ? '<span class="tier-badge tier-obs">重点观察·' + esc(m.obsName || m.board || "") + '</span>' : '');
      var riskBadge = m.bearish_level === "hard" ? '<span class="tag risk">硬伤</span>'
        : (m.bearish_level === "warn" ? '<span class="tag warn">警示</span>' : '');
      var srcTag = m.src ? '<span class="tag src-tag">' + esc(m.src) + '</span>' : '';
      var lv = m.levels || {};
      var reason = reasonOf(m);
      if ((!m.patterns || !Object.keys(m.patterns).length) && (m.risks || []).length) {
        reason = "MACD翻红观察 · " + (m.risks || []).slice(0, 2).join("；");
      }
      h += '<div class="mr-card' + (i < 3 ? ' mr-top' : '') + '">' +
        '<div class="mr-head">' +
          '<span class="mr-rank">' + (i + 1) + '</span>' +
          '<a class="mr-name" href="' + quoteHref(m) + '" target="_blank" rel="noopener">' + esc(m.name) + '</a>' +
          '<span class="pick-code">' + esc(m.code) + '</span>' +
          redDaysTag(m) + badge + riskBadge + srcTag +
          (i < 3 ? '<span class="tag ok strong">评分靠前</span>' : '') +
        '</div>' +
        '<div class="mr-body">' +
          '<span class="mr-price ' + chgCls + '">' + num(m.price, 2) + ' ' + pct(pchg) + '</span>' +
          '<span class="mr-k">最终分 <b>' + (fin != null ? fin : '—') + '</b></span>' +
          '<span class="mr-k">位置 <b>' + num((posV != null ? posV * 100 : 0), 0) + '%</b></span>' +
          '<span class="mr-k">5日 <b class="' + cls(m.chg5) + '">' + pct(m.chg5) + '</b></span>' +
          '<span class="mr-k">市值 ' + money(m.mcap) + '</span>' +
          (lv.s1 != null ? '<span class="mr-k">支撑 <b>' + num(lv.s1, 2) + '</b> / 压力 <b>' + num(lv.p1, 2) + '</b></span>' : '') +
        '</div>' +
        '<div class="mr-reason">' + esc(reason) + '</div>' +
        '<a class="view-link" href="' + quoteHref(m) + '" target="_blank" rel="noopener">查看行情 ↗</a>' +
        '</div>';
    });
    h += '</div>';
    return h;
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
    var pills = [];
    pills.push('<span class="bj-pill">截至 <b>' + esc(d.asof || d.date || "") + '</b></span>');
    pills.push('<span class="bj-pill">扫描 <b>' + esc(String(d.scanned || 0)) + '</b></span>');
    pills.push('<span class="bj-pill">合格 <b>' + esc(String(d.fine || 0)) + '</b></span>');
    if (d.regime) {
      var regMap = { attack: "强攻", stable: "稳健", defensive: "防守" };
      var rt = regMap[d.regime];
      if (rt) pills.push('<span class="bj-pill"><b>' + rt + '</b></span>');
    }
    if (d.off_market) pills.push('<span class="bj-pill warn">非交易日</span>');
    else if (d.today_missing) pills.push('<span class="bj-pill warn">今日未生成</span>');
    else if (d.stale) pills.push('<span class="bj-pill warn">用归档</span>');
    el.className = "bj-meta bj-meta-strip";
    el.innerHTML = pills.join("");
    el.hidden = false;
  }
  function boardHref(b) {
    // 板块查询优先同花顺 ths:88xxxx（行情页主路径）；无映射再回退东财 90.BK
    if (!b) return "#";
    var secid = String(b.secid || "").trim();
    var ths = String(b.ths || "").trim();
    var fallThs = {
      "军工": "ths:881166", "国防军工": "ths:881166", "煤炭": "ths:881105",
      "证券": "ths:881157", "PCB": "ths:884092", "半导体": "ths:881121",
      "光伏设备": "ths:881279", "通信光模块CPO": "ths:886033"
    };
    var fallBk = {
      "军工": "90.BK0490", "煤炭": "90.BK0437", "证券": "90.BK0473",
      "PCB": "90.BK1340", "半导体": "90.BK1036", "光伏设备": "90.BK1031",
      "通信光模块CPO": "90.BK1128", "国防军工": "90.BK1204"
    };
    var key = String(b.name || "").replace(/\s+/g, "");
    var use = ths || fallThs[key] || "";
    if (use && /^\d{6}$/.test(use)) use = "ths:" + use;
    if (use && !/^ths:/i.test(use) && /^88\d{4}$/.test(use)) use = "ths:" + use;
    if (!use) use = secid || fallBk[key] || "";
    if (!use) return "#";
    return "demo.html?secid=" + encodeURIComponent(use) + "&period=day" +
      (b.name ? "&name=" + encodeURIComponent(b.name) : "");
  }
  function enrichBoardRank(d) {
    // 前端兜底：把主线判定里的 fund_t/fund5/avg_up 填进空壳板块；补 secid/ths
    var fallBk = { "军工": "90.BK0490", "煤炭": "90.BK0437", "证券": "90.BK0473",
      "PCB": "90.BK1340", "半导体": "90.BK1036", "光伏设备": "90.BK1031",
      "通信光模块CPO": "90.BK1128", "国防军工": "90.BK1204" };
    var fallThs = {
      "军工": "ths:881166", "国防军工": "ths:881166", "煤炭": "ths:881105",
      "证券": "ths:881157", "PCB": "ths:884092", "半导体": "ths:881121",
      "光伏设备": "ths:881279", "通信光模块CPO": "ths:886033"
    };
    var by = {};
    (d.mainlines || []).forEach(function (m) {
      if (m && m.name) by[String(m.name).replace(/\s+/g, "")] = m;
    });
    (d.board_rank || []).forEach(function (b) {
      if (!b) return;
      var key = String(b.name || "").replace(/\s+/g, "");
      var m = by[key] || by[String(b.ml_name || "").replace(/\s+/g, "")] || null;
      if (m) {
        if (!(Math.abs(Number(b.f62) || 0) >= 1e5) && m.fund_t != null) b.f62 = m.fund_t;
        if (!(Math.abs(Number(b.f164) || 0) >= 1e5) && m.fund5 != null) b.f164 = m.fund5;
        if (b.pct == null && m.avg_up != null) b.pct = m.avg_up;
        if (b.p5 == null && m.chg5_med != null) b.p5 = m.chg5_med;
      }
      if (!String(b.secid || "").trim() && fallBk[key]) b.secid = fallBk[key];
      if (!String(b.ths || "").trim() && fallThs[key]) b.ths = fallThs[key];
    });
  }
  function renderMainlines(d) {
    enrichBoardRank(d);
    var box = $("bj-mainlines");
    if (!box) return;
    var ml = (d.mainlines || []).filter(function (m) {
      return m && (!m.src || m.src === "daily" || m.src === "archive" || m.src === "recalc" || m.src === "fallback");
    });
    var obs = d.observes || [];
    var rankBy = {};
    (d.board_rank || []).forEach(function (b) {
      if (b && b.name) rankBy[String(b.name).replace(/\s+/g, "")] = b;
    });

    if (!ml.length) {
      var isFan = !!(d.style && d.style.mode === "fan");
      var finalized = d.archive || d.mainline_from === "archive" || d.mainline_from === "recalc";
      var obsChips = obs.length
        ? '<div class="ml-obs-row">' + obs.map(function (o) {
            return '<span class="ml-obs">' + esc(o.name || "") + '</span>';
          }).join("") + '</div>'
        : '';
      if (isFan || (finalized && obs.length)) {
        box.innerHTML =
          '<div class="ml-empty"><b>暂无主线</b>轮动快，先看观察</div>' +
          (obsChips ? '<div class="ml-side" style="margin-top:12px"><div class="lab">观察</div>' + obsChips + '</div>' : '');
        return;
      }
      box.innerHTML = '<div class="ml-empty"><b>主线生成中</b>收盘后自动锁定</div>';
      return;
    }

    // 主攻 / 观察 / 回避：亮色圆点 + 观察保留眼睛
    var names = ml.map(function (m, i) {
      var rb = rankBy[String(m.name || "").replace(/\s+/g, "")] || { name: m.name };
      return '<a class="ml-name" href="' + boardHref(rb) + '" target="_blank" rel="noopener"><span class="ord">' + (i + 1) + '</span>' + esc(m.name || "") + '</a>';
    }).join("");
    var obsHtml = obs.length
      ? ('<div class="ml-side"><div class="lab"><i class="ic-dot cool" aria-hidden="true"></i><span class="ic-emoji" aria-hidden="true">👀</span>观察</div><div class="ml-obs-row">' +
        obs.map(function (o) {
          var rb = rankBy[String(o.name || "").replace(/\s+/g, "")] || { name: o.name };
          return '<a class="ml-obs" href="' + boardHref(rb) + '" target="_blank" rel="noopener">' + esc(o.name || "") + '</a>';
        }).join("") +
        '</div></div>')
      : '<div class="ml-side"><div class="lab"><i class="ic-dot cool" aria-hidden="true"></i><span class="ic-emoji" aria-hidden="true">👀</span>观察</div><div class="ml-obs-row"><span class="ml-obs" style="opacity:.55">暂无</span></div></div>';

    box.innerHTML =
      '<div class="sec-label">今日主线</div>' +
      '<div class="ml-deck">' +
      '<div class="ml-hero"><div class="ml-kicker"><i class="ic-dot gold" aria-hidden="true"></i>主攻方向</div><div class="ml-names">' + names + '</div></div>' +
      obsHtml +
      '</div>';
  }
  function renderBoardRank(d) {
    enrichBoardRank(d);
    var box = $("bj-boardrank");
    if (!box) return;
    var rank = d.board_rank || [];
    if (!rank.length) { box.innerHTML = ""; return; }
    var topMlName = "";
    var _topMl = (d.mainlines || []).filter(function (m) {
      return m && (!m.src || m.src === "daily" || m.src === "archive" || m.src === "recalc" || m.src === "fallback");
    })[0];
    if (_topMl) topMlName = String(_topMl.name || "").replace(/\s+/g, "");
    var obsNames = (d.observes || []).map(function (o) { return String(o.name || "").replace(/\s+/g, ""); });

    function fundPill(v, lab) {
      if (v == null || !isFinite(Number(v)) || Math.abs(Number(v)) < 1e5)
        return '<span class="mp"><i>' + lab + '</i><b class="muted">—</b></span>';
      var n = Number(v);
      return '<span class="mp"><i>' + lab + '</i><b class="' + (n >= 0 ? "up" : "down") + '">' + moneyYi(n) + '</b></span>';
    }
    function pctPill(v, lab) {
      if (v == null || !isFinite(Number(v)))
        return '<span class="mp"><i>' + lab + '</i><b class="muted">—</b></span>';
      return '<span class="mp"><i>' + lab + '</i><b class="' + cls(v) + '">' + pct(v) + '</b></span>';
    }

    var rows = "";
    rank.slice(0, 6).forEach(function (b, idx) {
      var _bn = String(b.name || "").replace(/\s+/g, "");
      var _bml = b.ml_name ? String(b.ml_name).replace(/\s+/g, "") : "";
      var isTop = !!(b.mainline && ((_bml && _bml === topMlName) || (!_bml && _bn === topMlName)));
      var isMain = !!(isTop && (b.tier === "king" || idx === 0));
      var isObs = b.observe || obsNames.indexOf(_bn) >= 0;
      var href = boardHref(b);
      var tags = "";
      if (isMain) tags += '<span class="tagx on">主线</span>';
      else if (b.mainline) tags += '<span class="tagx on">关注</span>';
      else if (isObs) tags += '<span class="tagx">观察</span>';
      if (b.ml_src === "new") tags += '<span class="tagx">新晋</span>';
      else if (b.ml_src === "cont") tags += '<span class="tagx">延续</span>';
      if (b.streak >= 2) tags += '<span class="tagx">连' + b.streak + '</span>';

      var lds = (b.leaders || []).slice(0, 3).map(function (ld) {
        if (!ld || !ld.name) return "";
        return '<a href="' + quoteHref(ld) + '" target="_blank" rel="noopener">' +
          esc(ld.name) +
          (ld.pct != null ? '<span class="' + cls(ld.pct) + '">' + pct(ld.pct) + '</span>' : '') +
          '</a>';
      }).filter(Boolean).join('<span class="sep">·</span>');

      // 单行：序号 | 名称+标签 | 四指标 | 代表（靠右）
      var rowCls = "br-row" + (isMain ? " king" : (b.mainline || b.tier === "key" ? " key" : ""));
      rows += '<div class="' + rowCls + '">' +
        '<div class="br-num">' + (idx + 1) + '</div>' +
        '<div class="br-namecell">' +
          '<a class="nm" href="' + href + '" target="_blank" rel="noopener">' + esc(b.name || "") + '</a>' +
          (tags ? '<span class="tags">' + tags + '</span>' : '') +
        '</div>' +
        '<div class="br-metrics">' +
          fundPill(b.f62, "今主力") +
          fundPill(b.f164, "5日主力") +
          pctPill(b.pct, "今涨") +
          pctPill(b.p5, "5日涨") +
        '</div>' +
        (lds ? '<div class="br-leaders"><span class="lab">代表</span> ' + lds + '</div>' : '<div class="br-leaders"></div>') +
        '</div>';
    });
    box.innerHTML =
      '<div class="sec-label">板块热度</div>' +
      '<div class="br-clean">' + rows + '</div>';
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
      return '<a class="chip" href="demo.html?secid=' + encodeURIComponent(secidForCode(it.ticker)) + '&period=day' + (it.name ? '&name=' + encodeURIComponent(it.name) : '') + '" target="_blank" rel="noopener" title="在AI行情官中查看 ' + esc(it.name) + '">' + (i + 1) + '. ' + esc(it.name) + ' ' + arrow + '</a>';
    });
    var sky = d.skyrocket || [];
    h += chipsRow('🚀 飙升榜 TOP5', sky, function (it, i) {
      return '<a class="chip" href="demo.html?secid=' + encodeURIComponent(secidForCode(it.ticker)) + '&period=day' + (it.name ? '&name=' + encodeURIComponent(it.name) : '') + '" target="_blank" rel="noopener" title="在AI行情官中查看 ' + esc(it.name) + '">' + (i + 1) + '. ' + esc(it.name) + '</a>';
    });
    var hm = d.hot_money || [];
    h += chipsRow('💰 龙虎榜资金净买入 TOP5', hm, function (it, i) {
      return '<span class="chip" title="' + esc((it.stocks || []).slice(0, 3).join('、')) + '">' + (i + 1) + '. ' + esc(it.name) + ' <span class="up">+' + money(it.buying) + '</span>' + (it.stocks && it.stocks.length ? ' · ' + esc(it.stocks.slice(0, 2).join('、')) : '') + '</span>';
    });
    var ld = d.ladder || {};
    var lrows = (ld.rows || []).filter(function (r) { return r.count > 0; });
    if (lrows.length) {
      h += '<div class="ths-sub">📈 连板梯队</div><div class="ths-inline">' + lrows.map(function (r) {
        return '<span class="chip">' + esc(thsBoardLab(r.board)) + ' ' + r.count + ' 家' + (r.names && r.names.length ? ' · ' + esc(r.names.slice(0, 2).join('、')) : '') + '</span>';
      }).join('') + '</div>';
    }
      h += '<div class="ths-foot">同花顺金融数据API · 仅做热点交叉验证；数据截至 ' + esc(d.date || '-') + '</div>';
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
    apiFetch("/api/bj/history?market=" + encodeURIComponent(state.market)).then(function (d) {
      renderHistory((d && d.list) || []);
    }).catch(function () {
      renderHistory([]);
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
    var _base = 'gd.html?date=' + encodeURIComponent(it.date) + '&market=' + encodeURIComponent(market);
    return '<div class="hr-wrap">' +
      '<a class="hist-row" href="' + _base + '" target="_blank" rel="noopener" title="\u626b\u63cf\u65e5 ' + esc(it.date) + '\uff08\u6570\u636e\u622a\u81f3 ' + esc(it.asof || it.date) + ' \u6536\u76d8\uff09\u00b7 \u65b0\u7a97\u53e3\u6253\u5f00\u5f52\u6863">' +
        '<span class="hr-date">' + esc(it.date) + asofTxt + '</span>' +
        '<span class="hr-picks">' + (picks || "\u2014") + '</span>' +
        '<span class="hr-go">\u2197</span></a>' +
      '<a class="hr-replay" href="' + _base + '&replay=1" target="_blank" rel="noopener" title="\u7528\u6700\u65b0\u7b97\u6cd5\u56de\u653e\u8be5\u65e5\uff08\u53ea\u8bfb\u9884\u89c8\uff09">\u26a1\u56de\u653e</a>' +
      '</div>';
  }
  function renderHistory(list) {
    var box = $("bj-history");
    if (!box) return;
    list = dedupByDay(list || []);
    if (!list.length) { box.innerHTML = ""; return; }
    var h = '<div class="hist-card">' +
      '<div class="bj-section hist-title">历史归档 · 往期筛选（' + marketLabel(state.market) + '）</div>' +
      '<p class="hist-desc">每日一份（按最新算法口径·最终版），新窗口打开查看该日结果；历史多版本仅存档，不参与页面展示</p>';
    h += '<div class="hist-grid">';
    list.forEach(function (it) { h += historyRow(it, state.market); });
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
  function openReplay(dateKey, market) {
    if (!dateKey) return;
    setStatus("正在用最新算法回放 " + dateKey + " …");
    apiFetch("/api/bj/replay?date=" + encodeURIComponent(dateKey) + "&market=" + encodeURIComponent(market)).then(function (d) {
      if (!d || d.ok === false) {
        setStatus("回放失败：" + esc((d && d.message) || "未知错误"), true);
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
      setStatus("最新算法回放 · " + dateKey);
    }).catch(function (e) {
      if (e && e.status === 403) {
        var gMain = $("bj-main"); if (gMain) gMain.hidden = true;
        var gGate = $("bj-vipgate"); if (gGate) gGate.hidden = false;
        setStatus("当前账号未开通 VIP");
        return;
      }
      setStatus("回放失败：" + esc((e && e.message) || "网络错误"), true);
    });
  }
  window.openReplay = openReplay;
  function emotionBanner(d) {
    var emo = (d.meta && d.meta.emotion) || null;
    var h = "";
    if (emo && emo.regime === "risk_off") {
      h += '<div class="bj-gap-alert">⚠️ 情绪偏冷（温度' + (emo.temperature != null ? emo.temperature : "—") + '）：注意控制仓位、以回踩企稳为主，回踩企稳门槛额外 +3。</div>';
    }
    if (d.market_code === "pb" && emo && emo.fb) {
      var _pr = emo.promote_rate != null ? Math.round(emo.promote_rate * 100) : null;
      var _hint = emo.promote_rate >= 0.25 ? "晋级率偏高" : (emo.promote_rate < 0.15 ? "晋级率偏低·谨慎" : "晋级率中性");
      h += '<div class="bj-note">昨日首板 ' + emo.fb + ' 只 · 今日晋级 ' + emo.promote + ' 只' +
        (_pr != null ? '（晋级率 ' + _pr + '% · ' + _hint + '）' : '') +
        '：回踩企稳仅跟踪「缩量不破位 + 主线共振」形态。</div>';
    }
    return h;
  }
  function renderPicks(d) {
    var box = $("bj-result");
    if (!box) return;
    var hint = marketHint(d);
    if ((d && d.market_code) === "macd") {
      var mlist = d.macd_reds || [];
      if (!mlist.length) {
        box.innerHTML = hint + '<div class="bj-empty-alert"><div class="ico">\ud83d\udca1</div><div class="bd"><b>' + dataDayLabel(d) + '暂无 MACD 首红标的</b><span>底部刚翻红 + 有量确认的票，多出现在大盘/个股刚启动时；现在若多在红柱延伸段，空着是正常的，可稍后重扫或看其它栏目。</span></div></div>';
        return;
      }
      box.innerHTML = hint + macdRedSection(d) +
        '<div class="notice">题材波动大，注意破位 / 放量长阴-8% 风险。</div>';
      return;
    }
    var picks = d.picks || [];
    var emoHtml = emotionBanner(d);
    var mfrAll = (picks || []).concat(d.runners || []).filter(function (x) { return x && x.patterns && x.patterns.macdFirstRed; });
    if (!picks.length) {
      var emptyTitle = d.archive ? '该日期无归档筛选记录' : (d.market_code === 'pb' ? '暂无回踩企稳标的' : (d.market_code === 'low10' ? '暂无10元下合格标的' : dataDayLabel(d) + '暂无合格标的'));
      var emptySub = d.archive ? '可查看其它日期的历史归档。' : (d.market_code === 'pb' ? '需要近期有异动/首板，再缩量回踩且未破位；当前没有就空着，可稍后重扫或看其它栏目。' : (d.market_code === 'low10' ? '要同时满足：股价<10元、刚右侧转强、股性活跃；不够格就不推，可稍后重扫。' : '只要上涨途中、股性活跃的票；今天没有合格的就空着，宁缺毋滥。'));
      box.innerHTML = hint + emoHtml + '<div class="bj-empty-alert"><div class="ico">\ud83d\udca1</div><div class="bd"><b>' + esc(emptyTitle) + '</b><span>' + emptySub + '</span></div></div>';
      return;
    }
    var html = hint + emoHtml;
    if (d.archive) {
      var _dkey = d.asof || d.date || "";
      if (d.replay) {
        html += '<div class="bj-section">历史筛选 · 最新算法回放（数据日期 ' + esc(_dkey) + '）</div>';
        html += '<div class="notice stale">⚡ 最新算法 × 历史收盘数据回放（只读预览，未写入归档）。</div>';
      } else {
        html += '<div class="bj-section">历史筛选（数据日期 ' + esc(_dkey) + '）</div>';
        html += '<div class="notice stale">📂 以下为历史归档结果；最新结果请回到页面顶部查看。</div>';
        html += '<button class="btn-blue" style="margin:8px 0 12px" onclick="window.openReplay(\'' + esc(_dkey) + '\',\'' + esc(state.market) + '\')">⚡ 用最新算法回放该日</button>';
      }
    } else if (d.stale) {
      var _tf = d.today_fine || {};
      var _tfTxt = '';
      if (_tf.fine != null) {
        _tfTxt = '今日扫描：达标 ' + _tf.fine + ' 只';
        if (_tf.top && _tf.top.name) {
          _tfTxt += '（最接近：' + esc(_tf.top.name) + ' ' + esc(_tf.top.code || '') + (_tf.top.final != null ? ' · ' + _tf.top.final + ' 分' : '') + (_tf.top.risks && _tf.top.risks.length ? ' · ' + esc(_tf.top.risks.join('；')) : '') + '）';
        }
        _tfTxt += '，均未达入选线（宁缺毋滥）。';
      }
      var _sf = d.stale_from || "";
      var _sd = staleLabel(d);
      var _staleNote = d.intraday
        ? '未到收盘（约 15:15 服务端自动更新今日，全站共用）：当前展示最近归档' + _sd + '。'
        : '⚠ 今日（' + esc(d.date || "") + '）扫描无合格标的' + (_tfTxt ? '：' + _tfTxt : '（可能为盘前或数据未更新）') + '，以下为最近归档' + _sd + '。'
      html += '<div class="bj-section">最近归档筛选（数据日期 ' + esc(_sf || d.asof || "") + (d.stale_scan_date && d.stale_scan_date !== _sf ? ' · ' + esc(d.stale_scan_date) + ' 扫描' : '') + ' · ' + (d.intraday ? '未到收盘' : '<span class="bj-empty-flag">今日无合格标的</span>') + '）</div>';
      html += '<div class="notice stale">' + _staleNote + '</div>';
    } else {
      var trk = d.prev_track || [];
      if (d.prev_date && trk.length) {
        html += '<div class="bj-section">昨日筛选 · 今日跟踪（' + esc(d.prev_date) + '）</div>' +
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
          '<div class="pt-note">未破位继续跟踪；破位或放量长阴-8% 注意风险；不因新面孔频繁换股。</div>';
      }
      var nPicks = picks.length;
      html += '<div class="sec-label">' + dataDayLabel(d) + '精选 · ' + nPicks + ' 只</div>';
      if (mfrAll.length) {
        html += '<div class="bj-note">另有 MACD 首红 ' + mfrAll.length + ' 只 · 可切「MACD首红」</div>';
      }
      if (d.mainline_gap) {
        var _mln = (d.mainlines || []).filter(function (m) {
          return m && (!m.src || m.src === "daily" || m.src === "archive" || m.src === "recalc" || m.src === "fallback");
        })
          .map(function (m) { return esc(m.name || ""); }).filter(Boolean);
        html += '<div class="bj-gap-alert">⚠️ 主线（' + (_mln.length ? _mln.join('、') : '主线') + '）' + dataDayLabel(d) + '暂无低风险合格标的；以下为资金热度个券/备选，仅作技术面跟踪。</div>';
      }
      if (d.relaxed) {
        html += '<div class="notice">' + dataDayLabel(d) + '严格档无合格标的，采用放宽兜底档（位置/换手/启动门槛小幅放宽，利空硬伤与主线约束不变）。</div>';
      }
    }
    var _disc = '30CM 波动大，注意破位 / 放量长阴-8% 风险。';
    if (nPicks && nPicks < 3) _disc = dataDayLabel(d) + '仅 ' + nPicks + ' 只合格，少而精不凑满；' + _disc;
    html += '<div class="notice">' + _disc + '</div>';
    html += '<div class="pick-grid">';
    picks.forEach(function (p) {
      var chgCls = cls(p.pct);
      var isKing = p.tier === "king";
      var lv = p.levels || {};
      var st = p.strategy || {};
      var posSpan = '';
      var stLine = '';
      if (st && (st.entry || st.period)) {
        var stPeriod = String(st.period || '').trim().replace(/主线龙头/g, '主线代表').replace(/龙头组合/g, '代表组合').replace(/补涨卡位/g, '补涨观察');
        var stEntry = sanitizeSt(st.entry);
        stLine = '<div class="pick-strategy"><span class="st-tag">技术参考</span>' +
          '<b>' + esc(stPeriod) + '</b> ｜ ' + esc(stEntry) +
          ' ｜ <span class="st-disc">不追高·缩量回踩·破位/长阴-8%注意风险</span></div>';
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
          '<span class="stop">破位参考 ' + num(lv.stop, 2) + '</span>' + posSpan +
        '</div>' +
        stLine +
        fundHtml(p) +
        '<div class="pick-reason">筛选依据：' + esc(reasonOf(p)) + '</div>' +
        bearishHtml(p) +
        '</div>';
    });
    html += '</div>';
    html += macdRedSection(d);
    // runners
    var runners = d.runners || [];
    if (runners.length) {
      html += '<div class="bj-section">备选池（落选原因）</div>';
      html += '<div class="table-scroll"><table class="bj-table"><tr><th>#</th><th>代码</th><th>名称</th><th>现价</th><th>涨跌</th><th>最终分</th><th>位置</th><th>市值</th><th>5日</th><th>20日</th><th>落选原因</th></tr>';
      runners.forEach(function (r, ri) {
        var blBadge = r.bearish_level === "hard" ? "<span style='color:var(--rise)'>硬伤</span>" : (r.bearish_level === "warn" ? "<span style='color:var(--warn)'>警示</span>" : "");
        html += '<tr><td style="color:var(--muted)">' + (ri + 1) + '</td><td style="color:var(--muted)">' + esc(r.code) + '</td><td><a href="demo.html?secid=' + encodeURIComponent(secidForCode(r.code)) + '&period=day" target="_blank" rel="noopener" style="color:var(--bj-acc)">' + esc(r.name) + '</a>' + runnerTags(r) + '</td><td class="' + cls(r.pct) + '">' + num(r.price, 2) + '</td><td class="' + cls(r.pct) + '">' + pct(r.pct) + '</td><td>' + (r.final != null ? r.final : "—") + '</td><td>' + num((r.pos != null ? r.pos * 100 : 0), 0) + '%</td><td>' + money(r.mcap) + '</td><td class="' + cls(r.chg5) + '">' + pct(r.chg5) + '</td><td class="' + cls(r.chg20) + '">' + pct(r.chg20) + '</td><td>' + blBadge + ' ' + esc((r.risks || []).join("；") || "排名靠后") + '</td></tr>';
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
    // 量能（实色高对比）
// MACD 副图：柱 + DIF/DEA + 首根红/绿加亮 + 金叉/死叉箭头
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
    // 会话缓存：同一市场 10 分钟内已加载过，直接秒回不再请求，避免快速切栏触发后端限流（429）
    if (!force) {
      var hit = state.cache[state.market];
      if (hit && Date.now() - hit.ts < 10 * 60 * 1000) {
        var btn0 = $("btn-bj-refresh");
        applyScanResult(hit.data, reqSeq, btn0);
        return;
      }
    }
    state.loading = true;
    var seq = ++reqSeq;
    var btn = $("btn-bj-refresh");
    if (btn) { btn.disabled = true; btn.textContent = "扫描中…"; }
    statusLoading();
    waitDeadline = 0;
    if (force) {
      delete state.cache[state.market];
      // 异步重扫：先启动后台任务，轮询进度，避免长请求触发 nginx 60s 网关超时（504）
      apiFetch("/api/bj/screener/start?market=" + encodeURIComponent(state.market)).then(function (st) {
        if (seq !== reqSeq) return;
        if (!st || st.ok !== true) {
          state.loading = false;
          stopProgress();
          if (btn) { btn.disabled = false; btn.textContent = "重新扫描"; }
        applyScanGate(btn);
        applyScanGate(btn);
        applyScanGate(btn);
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
  function renderPartialPreview(d) {
    var box = $("bj-result");
    if (!box) return;
    var picks = d.picks || [];
    var h = '<div class="bj-section">初筛预览 · 深度复核进行中</div>' +
      '<div class="notice">K线形态筛选已完成；AI评分、基本面、龙虎榜与尾盘强度仍在后台复核。以下为初筛结果，仅供参考。</div>';
    if (!picks.length) { box.innerHTML = h + '<div class="bj-note">初筛尚未产生候选，请继续等待。</div>'; return; }
    h += '<div class="bj-preview-grid">';
    picks.forEach(function (p) {
      h += '<div class="bj-preview-card"><b>' + esc(p.name || p.code || "-") + '</b>' +
        '<span>' + esc(p.code || "") + '</span>' +
        '<span>形态分 ' + num(p.score, 0) + ' · ' + esc(p.mainName || p.revName || p.ind || "待归类") + '</span>' +
        '<small>等待深度复核，仅供参考，不构成投资建议</small></div>';
    });
    h += '</div>';
    box.innerHTML = h;
  }
  function applyScanResult(d, seq, btn) {
    if (seq !== reqSeq) return;
    state.loading = false;
    stopProgress();
    if (btn) {
      btn.disabled = false;
      // 今日已生成即可视为定型：「stale」仅表示今日无主推而展示归档，不等于没扫过
      var fresh = d && d.cached && !d.refresh_locked && !d.intraday && !d.today_missing;
      btn.textContent = fresh ? "已是最新" : "重新扫描";
      btn.title = fresh
        ? (d.stale
          ? "今日已扫完（暂无主推，展示归档）；一般无需重扫"
          : "今日结果已由服务端生成（全站共用），一般无需重扫；点击可强制刷新")
        : "仅异常时再点；正常由服务端约 15:15 自动更新（120 秒限一次）";
    }
    applyScanGate(btn);
    if (!d || d.ok === false) {
      setStatus("扫描失败：" + esc((d && d.message) || (d && d.error) || "未知错误"), true);
      return;
    }
    if (d.partial === true) {
      state.data = d;
      $("bj-vipgate").hidden = true;
      $("bj-main").hidden = false;
      renderMeta(d);
      renderMainlines(d);
      renderPartialPreview(d);
      setStatus("已显示K线初筛预览，深度复核进行中…");
      return;
    }    state.data = d;
    state.cache[state.market] = { ts: Date.now(), data: d };
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
      if (d.market_code !== "macd") loadHistory();
    }
    if (d.stale) {
      var staleTxt = d.intraday
        ? "\ud83d\udca1 今日未收盘：展示最近归档" + staleLabel(d) + "结果"
        : (d.today_missing ? "\ud83d\udca1 今日数据尚未生成（" + fmtDate() + "），展示最近归档" + staleLabel(d) + "结果" : "\ud83d\udca1 今日无合格标的（" + fmtDate() + "），展示最近归档" + staleLabel(d) + "结果");
      setStatus(staleTxt, false, true);
    } else if (d.vip_required) {
      setStatus(marketLabel(state.market) + "板块视图已解锁（" + fmtDate() + "）" + (d.cached ? " · 已加载" + dataDayLabel(d) + "缓存" : ""));
    } else {
      setStatus(marketLabel(state.market) + "扫描完成（" + fmtDate() + "）" + (d.cached ? " · 已加载" + dataDayLabel(d) + "缓存" : ""));
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
    applyScanGate(btn);
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
        try { localStorage.setItem("bj_tab", m); } catch (e) {}
        state.data = null;
        historyState = { loaded: false, list: [] };
        var all = document.querySelectorAll("#bj-tabs .bj-tab");
        for (var j = 0; j < all.length; j++) all[j].classList.toggle("active", all[j] === this);
        ["bj-result", "bj-history", "bj-boardrank"].forEach(function (id) {
          var el = $(id); if (el) el.innerHTML = "";
        });
        var meta = $("bj-meta"); if (meta) meta.hidden = true;
        load(false);
        if (window.scrollTo) window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }
  }
  function archiveParams() {
    var out = { date: "", market: "", replay: "" };
    try {
      var q = location.search || "";
      var m1 = q.match(/[?&]date=([^&]+)/);
      if (m1 && m1[1]) out.date = decodeURIComponent(m1[1]).trim();
      var m2 = q.match(/[?&]market=([^&]+)/);
      if (m2 && m2[1]) out.market = decodeURIComponent(m2[1]).trim();
      var m3 = q.match(/[?&]replay=([^&]+)/);
      if (m3 && m3[1]) out.replay = m3[1];
    } catch (eA) {}
    return out;
  }

  /* —— 大盘环境 + 今日策略（市场驾驶舱统一口径，免费大盘可见，策略/板块/个股 VIP） —— */
  function stripMdLink(t) {
    return String(t || "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*/g, "").replace(/\*\*/g, "").trim();
  }
  function loadMarket() {
    var box = $("bj-market");
    if (!box) return;
    function fill(d, label) {
      if (!d || !d.ok || !d.md) { box.hidden = true; return; }
      renderMarket(d.md, !!d.vip, d.asof || d.date || "", label || "", d.indexes || null);
    }
    apiFetch("/api/report/today").then(function (d) {
      if (d && d.ok) { fill(d, reportDayLabel(d)); return; }
      apiFetch("/api/report/history").then(function (h) {
        var items = (h && h.items) || [];
        if (!items.length) { box.hidden = true; return; }
        var latest = items[0].date;
        apiFetch("/api/report/" + encodeURIComponent(latest)).then(function (d2) { fill(d2, "最近大盘 " + latest); })
          .catch(function () { box.hidden = true; });
      }).catch(function () { box.hidden = true; });
    }).catch(function () { box.hidden = true; });
  }
  function renderMarket(md, vip, asof, label, indexesBlob) {
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

    var PRIMARY = ["上证指数", "深证成指", "创业板指", "北证50"];
    var STYLE = ["中证500", "中证1000"];
    var idxMap = {};
    var ixRoot = indexesBlob && typeof indexesBlob === "object" ? indexesBlob : null;
    var ixDict = ixRoot && ixRoot.indexes && typeof ixRoot.indexes === "object" ? ixRoot.indexes : (ixRoot || null);
    if (ixRoot && ixRoot.env && pts == null && ixRoot.env.pts != null) pts = Number(ixRoot.env.pts);
    if (ixDict) {
      Object.keys(ixDict).forEach(function (k) {
        var r = ixDict[k] || {};
        if (!r || r.error) return;
        var labs = r.recent_labels || [];
        var macd = r.macd_last || {};
        idxMap[k] = {
          name: k,
          close: r.last_close,
          pct: r.pct,
          score: r.score,
          bar: macd.bar,
          sig: labs.length ? String(labs[labs.length - 1]).replace(/　/g, " ") : ""
        };
      });
    }
    if (!Object.keys(idxMap).length) {
      var lines = String(md).split("\n");
      for (var i = 0; i < lines.length; i++) {
        var L = lines[i].trim();
        if (!/^\|\s*\d+\s*\|/.test(L) || /排名/.test(L)) continue;
        var parts = L.split("|").map(function (x) { return String(x || "").trim(); }).filter(function (_, idx2) { return idx2 > 0; });
        if (parts.length < 5) continue;
        var nm = stripMdLink(parts[1]);
        var closeV = null, pctV = null, sig = "", score = "", bar = null;
        if (parts.length >= 8 && /[\d.]/.test(parts[2]) && /%|-/.test(parts[3])) {
          closeV = parseFloat(parts[2]);
          pctV = parseFloat(String(parts[3]).replace("%", ""));
          sig = stripMdLink(parts[4]);
          score = parts[5];
          bar = parseFloat(parts[6]);
        } else {
          sig = stripMdLink(parts[2]);
          score = parts[3];
          bar = parseFloat(parts[4]);
        }
        idxMap[nm] = { name: nm, close: isFinite(closeV) ? closeV : null, pct: isFinite(pctV) ? pctV : null, score: score, bar: isFinite(bar) ? bar : null, sig: sig };
      }
    }
    function shortName(n) {
      return String(n || "").replace(/指数$/, "").replace(/成指$/, "成指");
    }
    function rowHtml(it, slim) {
      if (!it) return "";
      var pctN = it.pct != null && isFinite(Number(it.pct)) ? Number(it.pct) : null;
      var pctCls = pctN == null ? "" : (pctN > 0 ? " up" : (pctN < 0 ? " down" : ""));
      var pctTxt = pctN == null ? "—" : ((pctN > 0 ? "+" : "") + pctN.toFixed(2) + "%");
      var closeTxt = it.close != null && isFinite(Number(it.close))
        ? Number(it.close).toFixed(Number(it.close) >= 1000 ? 0 : 2)
        : "—";
      var scTxt = it.score != null && it.score !== "" ? String(it.score) : "—";
      var barN = it.bar != null && isFinite(Number(it.bar)) ? Number(it.bar) : null;
      var barTxt = barN == null ? "—" : ((barN >= 0 ? "+" : "") + barN.toFixed(1));
      var tip = [it.sig, "评" + scTxt, "MACD " + barTxt].filter(Boolean).join(" · ");
      return '<div class="mkt-row' + (slim ? " slim" : "") + '" title="' + esc(tip) + '">' +
        '<span class="nm">' + esc(shortName(it.name)) + '</span>' +
        '<span class="px' + pctCls + '">' + esc(pctTxt) + '</span>' +
        '<span class="cl">' + esc(closeTxt) + '</span>' +
        '<span class="sc">' + esc(scTxt) + '</span>' +
        '<span class="bar">' + esc(barTxt) + '</span></div>';
    }
    var envLine = "";
    var em = md.match(/大盘环境[：:]\s*([^\n]+)/);
    if (em && em[1]) envLine = stripMdLink(em[1]).replace(/（[^）]*）/g, "").replace(/；\s*$/, "");

    var observe = "", avoid = "";
    if (vip) {
      var om = md.match(/\*{0,2}观察\*{0,2}[：:]\s*([^\n；;]+)/);
      if (om && om[1]) observe = stripMdLink(om[1]);
      var av = md.match(/回避[^：:\n]*[：:]\s*([^\n；;]+)/);
      if (av && av[1]) avoid = stripMdLink(av[1]);
    }

    var dayL = (asof && String(asof) === fmtDate()) ? "今日" : "昨日";
    var h = '<div class="sec-label">' + esc(label || (dayL + "大盘")) + '</div>';
    h += '<div class="mkt-signal compact"><div class="mkt-badge-sm ' + envCls + '"><span class="big">' + envTxt + '</span>';
    if (pts != null) h += '<span class="sm">' + pts.toFixed(1) + '</span>';
    h += '</div><div class="mkt-idx-wrap">';
    h += '<div class="mkt-head"><span>指数</span><span>涨跌</span><span>收盘</span><span>评分</span><span>MACD</span></div>';
    var any = false;
    for (var j = 0; j < PRIMARY.length; j++) {
      if (idxMap[PRIMARY[j]]) { h += rowHtml(idxMap[PRIMARY[j]], false); any = true; }
    }
    for (var k = 0; k < STYLE.length; k++) {
      if (idxMap[STYLE[k]]) { h += rowHtml(idxMap[STYLE[k]], true); any = true; }
    }
    if (!any) h += '<div class="mkt-empty">' + esc(envLine || "大盘信号已更新") + '</div>';
    h += '</div></div>';
    box.innerHTML = h;
    box.hidden = false;

    var stratBox = $("bj-strategy");
    if (stratBox) {
      if (vip && (observe || avoid)) {
        var bits = [];
        if (observe) bits.push('<span class="bj-pill"><i class="ic-dot cool" aria-hidden="true"></i><span class="ic-emoji" aria-hidden="true">👀</span>观察 <b>' + esc(observe) + '</b></span>');
        if (avoid) bits.push('<span class="bj-pill warn"><i class="ic-dot rose" aria-hidden="true"></i>回避 <b>' + esc(avoid) + '</b></span>');
        stratBox.innerHTML = '<div class="bj-meta-strip" style="margin:0 0 12px">' + bits.join("") + '</div>';
        stratBox.hidden = false;
      } else if (!vip) {
        stratBox.innerHTML = '<div class="bj-mkt-gate">观察与标的为 VIP · <a href="./account.html#vip">开通</a></div>';
        stratBox.hidden = false;
      } else {
        stratBox.innerHTML = "";
        stratBox.hidden = true;
      }
    }
  }

  var _winrateItems = [];
  function winrateRowHtml(p) {
    var isDone = p.state === "done";
    var fwd5, fwd10;
    if (isDone && p.fwd5 != null) {
      fwd5 = p.fwd5 >= 5 ? '<b class="up">+' + num(p.fwd5, 1) + '%</b>' : (p.fwd5 >= 0 ? num(p.fwd5, 1) + '%' : '<span class="down">' + num(p.fwd5, 1) + '%</span>');
    } else if (p.since != null) {
      fwd5 = '<span class="muted">' + num(p.since, 1) + '%</span>';
    } else {
      fwd5 = '<span class="muted">—</span>';
    }
    fwd10 = (p.fwd10 != null) ? (p.fwd10 >= 0 ? num(p.fwd10, 1) + '%' : '<span class="down">' + num(p.fwd10, 1) + '%</span>') : '<span class="muted">—</span>';
    var st;
    if (p.stop_hit) st = '<span class="win-st win-stop">破位</span>';
    else if (isDone && p.fwd5 >= 5) st = '<span class="win-st win-hit">强势</span>';
    else if (isDone) st = '<span class="win-st win-miss">未走强</span>';
    else st = '<span class="win-st win-trk">跟踪中</span>';
    var tier = p.tier === "king" ? ' ⭐' : (p.tier === "key" ? ' · 评分次高' : '');
    var lastTxt = (p.last != null) ? num(p.last, 2) + ' <span class="muted">' + esc(p.lastDate || "") + '</span>' : '—';
    return '<tr>' +
      '<td class="muted">' + esc(p.asof) + '</td>' +
      '<td class="win-name"><a class="win-link" href="' + quoteHref(p) + '" target="_blank" rel="noopener">' + esc(p.name || p.code) + tier + '</a><span class="muted"> ' + esc(p.code) + '</span></td>' +
      '<td>' + (p.entry != null ? num(p.entry, 2) : '—') + '</td>' +
      '<td>' + lastTxt + '</td>' +
      '<td>' + (isDone && p.high5 != null ? num(p.high5, 2) : '—') + '</td>' +
      '<td>' + fwd5 + '</td>' +
      '<td>' + fwd10 + '</td>' +
      '<td>' + st + '</td>' +
      '</tr>';
  }
  function openWinrateDetail() {
    var items = _winrateItems || [];
    var m = document.getElementById("wr-modal");
    if (!m) {
      m = document.createElement("div");
      m.id = "wr-modal";
      m.className = "wr-modal";
      m.hidden = true;
      m.innerHTML =
        '<div class="wr-modal-box">' +
        '<div class="wr-modal-head"><b>📋 形态回溯统计明细（' + items.length + ' 只）</b>' +
        '<button type="button" class="wr-close" aria-label="关闭">✕</button></div>' +
        '<div class="wr-modal-body"><div class="wr-table-scroll"><table class="wr-table"><thead><tr>' +
        '<th>入选日</th><th>标的</th><th>入选价</th><th>最新价</th><th>5日最高</th><th>5日涨幅</th><th>10日涨幅</th><th>状态</th>' +
        '</tr></thead><tbody>' + items.map(winrateRowHtml).join("") + '</tbody></table></div></div>' +
    '<div class="wr-modal-foot">点击标的名称查看 K 线（新窗口）。强势=入选后5日内最高涨幅≥+5%；破位=10日内跌破参考位；跟踪中=入选≤5日尚无完整验证。历史统计不代表未来表现，仅作算法回溯检验。</div>' +
        '</div>';
      document.body.appendChild(m);
      m.addEventListener("click", function (e) { if (e.target === m) closeWinrateDetail(); });
      var cb = m.querySelector(".wr-close");
      if (cb) cb.addEventListener("click", closeWinrateDetail);
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeWinrateDetail(); });
    }
    m.hidden = false;
    var h = document.querySelector(".wr-head");
    if (h) h.setAttribute("aria-expanded", "true");
  }
  function closeWinrateDetail() {
    var m = document.getElementById("wr-modal");
    if (m) m.hidden = true;
    var h = document.querySelector(".wr-head");
    if (h) h.setAttribute("aria-expanded", "false");
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
          if (b.n) tierTxt += ' ｜ ' + (k === "king" ? "评分最高" : k === "key" ? "评分次高" : "其他") + ' ' + b.n + '只·强势' + num(b.n ? b.hit / b.n * 100 : 0, 0) + '%';
        });
      }
      _winrateItems = d.items || [];
      box.innerHTML =
        '<div class="bj-section wr-head" role="button" tabindex="0" aria-expanded="false" title="点击查看逐只统计明细">形态回溯统计（近 ' + d.n + ' 只 · ' + esc(d.asof) + '）<span class="wr-see">📋 点击查看明细</span></div>' +
        '<div class="winrate-strip"><span>5日强势占比 <b class="up">' + rate + '</b></span>' +
        '<span>5日收正占比 <b class="up">' + posRate + '</b></span>' +
        '<span>10日破位占比 <b class="down">' + stop + '</b></span>' +
        '<span>跟踪中 ' + d.tracking + ' 只</span>' + tierTxt + '</div>' +
    '<div class="winrate-note">口径：以入选后5日内最高涨幅≥+5% 统计"强势"、10日内跌破参考位统计"破位"，仅作算法回溯检验；历史统计不代表未来表现。</div>';
      var head = box.querySelector(".wr-head");
      if (head) {
        head.addEventListener("click", openWinrateDetail);
        head.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openWinrateDetail(); } });
      }
      box.hidden = false;
    }).catch(function () {});
  }

  // —— 重新扫描门控：盘中（15:01 收盘数据定型前）禁止强制重扫，避免未定型 K 线污染当日数据 ——
  // 正常路径：约 15:15 服务端预扫一次，全站读缓存；「重新扫描」仅异常/强制时用。
  var _SCAN_HINT_OK = "约 15:15 自动更新，异常再重扫";
  function scanGateState() {
    var now = new Date();
    var d = now.getDay();
    if (d === 0 || d === 6) return { allow: false, note: "非交易日：展示最近收盘归档，无需重新扫描" };
    var hm = now.getHours() * 60 + now.getMinutes();
    if (hm < 15 * 60 + 1) {
      return { allow: false, note: "盘中未定型：15:01 后可手扫；约 15:15 服务端自动更新（全站共用）" };
    }
    return { allow: true, note: _SCAN_HINT_OK };
  }
  function applyScanGate(btn) {
    if (!btn) return;
    var g = scanGateState();
    var note = $("bj-refresh-note");
    if (!g.allow) {
      btn.disabled = true;
      btn.title = g.note;
      btn.classList.add("btn-gated");
      if (note) { note.textContent = g.note; note.hidden = false; }
    } else {
      btn.disabled = false;
      if (!btn.textContent || btn.textContent === "重新扫描") {
        btn.title = "仅异常时再点；正常由服务端约 15:15 自动更新（120 秒限一次）";
      }
      btn.classList.remove("btn-gated");
      if (note) { note.textContent = g.note; note.hidden = false; }
    }
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
    if (btn) {
      btn.addEventListener("click", function () {
        var g = scanGateState();
        if (!g.allow) { setStatus(g.note, true); return; }
        load(true);
      });
      applyScanGate(btn);
      setInterval(function () { applyScanGate(btn); }, 30 * 1000);
    }
    bindTabs();
    var ap = archiveParams();
    if (ap.date) {
      // 历史归档模式：新窗口直达该日结果（不触发扫描）
      if (ap.market === "bj" || ap.market === "all" || ap.market === "hs" || ap.market === "kc" || ap.market === "bj_all" || ap.market === "macd" || ap.market === "pb" || ap.market === "low10") {
        state.market = ap.market;
        var tabsAll = document.querySelectorAll("#bj-tabs .bj-tab");
        for (var tJ = 0; tJ < tabsAll.length; tJ++) {
          tabsAll[tJ].classList.toggle("active", tabsAll[tJ].getAttribute("data-market") === state.market);
        }
      }
      if (btn) btn.style.display = "none";
      if (ap.replay) {
        openReplay(ap.date, ap.market);
      } else {
        openArchive(ap.date);
      }
      return;
    }
    // 刷新停留：URL market 参数优先，其次上次所在 tab（localStorage），默认沪深主线
    var savedM = "";
    try { savedM = String(localStorage.getItem("bj_tab") || "").trim(); } catch (eS) {}
    var initM = (ap.market && ["hs", "kc", "bj", "bj_all", "macd", "pb", "low10"].indexOf(ap.market) >= 0) ? ap.market
      : ((savedM && ["hs", "kc", "bj", "bj_all", "macd", "pb", "low10"].indexOf(savedM) >= 0) ? savedM : "hs");
    if (initM !== state.market) {
      state.market = initM;
      var tabsAll2 = document.querySelectorAll("#bj-tabs .bj-tab");
      for (var tJ2 = 0; tJ2 < tabsAll2.length; tJ2++) {
        tabsAll2[tJ2].classList.toggle("active", tabsAll2[tJ2].getAttribute("data-market") === state.market);
      }
    }
    loadMarket();
    load(false);
    loadThsSentiment();
    loadWinrate();
  }

  return { boot: boot };
})();
