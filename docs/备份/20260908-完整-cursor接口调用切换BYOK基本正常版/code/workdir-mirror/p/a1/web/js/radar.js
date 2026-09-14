(function (global) {
  "use strict";

  var HISTORY_KEY = "ai24x_radar_history";
  var POOL_CACHE_KEY = "ai24x_radar_pool_v1";
  var IDB_NAME = "ai24x_radar";
  var IDB_VER = 1;
  var IDB_STORE = "klines";
  var MAX_HISTORY = 15;
  var scanAbort = false;
  var klineMemCache = Object.create(null);
  var lastScanMode = "full";
  var idbPromise = null;

  var PRESETS = {
    strict: {
      name: "严格",
      bondThreshold: 0.03, bondWindow: 5, bondMinCount: 2,
      ztYearMin: 5, ztYearMax: 10, ztDays: 10,
      maxStageRise: 0.65, avgAmountMin: 1e8, ztAmountMin: 5e7,
      bigCycleMode: "full", divergeMode: "full", volMode: "today",
      ma144Lookback: 5, ma144FlatPct: 1.0, volMultiple: 1.0,
      scanDays: 15, minListDays: 120
    },
    balanced: {
      name: "标准",
      bondThreshold: 0.05, bondWindow: 10, bondMinCount: 2,
      ztYearMin: 3, ztYearMax: 15, ztDays: 15,
      maxStageRise: 0.80, avgAmountMin: 5e7, ztAmountMin: 3e7,
      bigCycleMode: "medium", divergeMode: "medium", volMode: "recent3",
      ma144Lookback: 5, ma144FlatPct: 0.998, volMultiple: 1.1,
      scanDays: 30, minListDays: 120
    },
    loose: {
      name: "宽松",
      bondThreshold: 0.06, bondWindow: 10, bondMinCount: 2,
      ztYearMin: 2, ztYearMax: 20, ztDays: 15,
      maxStageRise: 1.0, avgAmountMin: 3e7, ztAmountMin: 2e7,
      bigCycleMode: "lite", divergeMode: "lite", volMode: "recent3",
      ma144Lookback: 10, ma144FlatPct: 0.995, volMultiple: 1.05,
      scanDays: 30, minListDays: 120
    }
  };

  var CFG = { bigDropMain: 0.93, bigDropGrowth: 0.90, klineDays: 400, batchSize: 28, batchConcurrency: 4, poolConcurrency: 4 };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  }
  function todayKey() {
    var d = new Date();
    var p = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
  }

  function openIdb() {
    if (idbPromise) return idbPromise;
    idbPromise = new Promise(function (resolve) {
      try {
        if (!global.indexedDB) { resolve(null); return; }
        var req = indexedDB.open(IDB_NAME, IDB_VER);
        req.onupgradeneeded = function (ev) {
          var db = ev.target.result;
          if (!db.objectStoreNames.contains(IDB_STORE)) db.createObjectStore(IDB_STORE, { keyPath: "thscode" });
        };
        req.onsuccess = function (ev) { resolve(ev.target.result); };
        req.onerror = function () { resolve(null); };
      } catch (e) { resolve(null); }
    });
    return idbPromise;
  }

  function idbGetKline(thscode) {
    return openIdb().then(function (db) {
      if (!db) return null;
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(IDB_STORE, "readonly");
          var req = tx.objectStore(IDB_STORE).get(normThscode(thscode));
          req.onsuccess = function () { resolve(req.result || null); };
          req.onerror = function () { resolve(null); };
        } catch (e) { resolve(null); }
      });
    });
  }

  function idbSetKline(thscode, items) {
    var key = normThscode(thscode);
    var sorted = sortKlineItems(items);
    if (sorted.length < 180) return Promise.resolve();
    return openIdb().then(function (db) {
      if (!db) return;
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(IDB_STORE, "readwrite");
          tx.objectStore(IDB_STORE).put({ thscode: key, day: todayKey(), items: sorted });
          tx.oncomplete = function () { resolve(); };
          tx.onerror = function () { resolve(); };
        } catch (e) { resolve(); }
      });
    });
  }

  function loadPoolCache() {
    try {
      var raw = localStorage.getItem(POOL_CACHE_KEY);
      if (!raw) return null;
      var o = JSON.parse(raw);
      if (!o || !o.stocks) return null;
      return o;
    } catch (e) { return null; }
  }

  function savePoolCache(map, scanDays, strictness) {
    try {
      var stocks = {};
      var today = todayKey();
      Object.keys(map).forEach(function (k) {
        var s = map[k];
        stocks[k] = {
          thscode: k,
          name: s.name,
          ticker: s.ticker,
          lastSeen: today
        };
      });
      localStorage.setItem(POOL_CACHE_KEY, JSON.stringify({
        day: today,
        scanDays: scanDays,
        strictness: strictness,
        stocks: stocks
      }));
    } catch (e) {}
  }

  function prunePoolMap(map, stockMeta, scanDays) {
    var cutoff = Date.now() - scanDays * 86400000;
    Object.keys(map).forEach(function (k) {
      var seen = stockMeta[k] && stockMeta[k].lastSeen;
      if (!seen) return;
      var t = new Date(String(seen) + "T12:00:00").getTime();
      if (!isNaN(t) && t < cutoff) delete map[k];
    });
  }

  function mergeKlineItems(oldItems, newItems) {
    var map = Object.create(null);
    (oldItems || []).forEach(function (it) {
      if (it && it.date_ms != null) map[it.date_ms] = it;
    });
    (newItems || []).forEach(function (it) {
      if (it && it.date_ms != null) map[it.date_ms] = it;
    });
    var merged = Object.keys(map).map(function (k) { return map[k]; });
    merged = sortKlineItems(merged);
    if (merged.length > CFG.klineDays) merged = merged.slice(-CFG.klineDays);
    return merged;
  }

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function token() {
    try { return String(localStorage.getItem("ai24x_a_token") || "").trim(); } catch (e) { return ""; }
  }

  function apiBase() {
    try {
      var shell = global.AI24X_A_SHELL;
      if (shell && typeof shell.getApiBase === "function") return String(shell.getApiBase() || "").replace(/\/$/, "");
    } catch (e0) {}
    try {
      var saved = String(localStorage.getItem("ai24x_a_api_base") || "").trim().replace(/\/$/, "");
      if (saved) return saved;
    } catch (e1) {}
    return "";
  }

  function apiUrl(path) { return (apiBase() || "") + path; }
  function authHeaders() {
    var t = token();
    return t ? { Authorization: "Bearer " + t } : {};
  }

  function fmtDateTime(ts) {
    if (!ts) return "—";
    var n = Number(ts);
    if (!isFinite(n) || n <= 0) return "—";
    if (n < 1e12) n *= 1000;
    var d = new Date(n);
    if (isNaN(d.getTime())) return "—";
    var p = function (x) { return String(x).padStart(2, "0"); };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  function fmtPrice(v) {
    var n = Number(v);
    return isFinite(n) ? n.toFixed(2) : "—";
  }

  function fmtMetric(val, suffix, naTip) {
    if (val == null || val === "" || (typeof val === "number" && !isFinite(val))) {
      return '<span class="radar-na"' + (naTip ? ' title="' + esc(naTip) + '"' : "") + ">—</span>";
    }
    return esc(val) + (suffix || "");
  }

  function metricNaTip(signalType, col) {
    if (signalType === "回踩二波" && col === "bond") return "回踩信号不含粘合次数";
    if (signalType === "粘合启动" && (col === "pull" || col === "ztgap" || col === "stab")) {
      return "粘合信号不含回撤、距涨停、企稳分";
    }
    return "";
  }

  function fmtDateMs(ms) {
    var d = new Date(ms);
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function setStatus(msg, isErr) {
    var el = $("radar-status");
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("is-err", !!isErr);
  }

  async function proxyPost(path, payload, retries) {
    retries = retries == null ? 2 : retries;
    for (var i = 0; i <= retries; i++) {
      var res = await fetch(apiUrl(path), {
        method: "POST",
        headers: Object.assign({ Accept: "application/json", "Content-Type": "application/json" }, authHeaders()),
        credentials: "same-origin",
        body: JSON.stringify(payload || {})
      });
      var data = null;
      try { data = await res.json(); } catch (e0) { data = null; }
      if (res.status === 401) throw new Error("登录已失效，请重新登录");
      if (res.status === 403) throw new Error((data && data.detail) || "请先开通 VIP");
      if (!res.ok) throw new Error((data && data.message) || (data && data.detail) || "HTTP " + res.status);
      if (data && data.ok === false) {
        if (String(data.message || "").indexOf("4001") >= 0 || String(data.message || "").indexOf("限流") >= 0) {
          await sleep(600 * (i + 1));
          continue;
        }
        throw new Error(data.message || "请求失败");
      }
      return data;
    }
    throw new Error("请求失败，请稍后重试");
  }

  async function proxyGet(path, retries) {
    retries = retries == null ? 2 : retries;
    for (var i = 0; i <= retries; i++) {
      var res = await fetch(apiUrl(path), {
        headers: Object.assign({ Accept: "application/json" }, authHeaders()),
        credentials: "same-origin"
      });
      var data = null;
      try { data = await res.json(); } catch (e0) { data = null; }
      if (res.status === 401) throw new Error("登录已失效，请重新登录");
      if (res.status === 403) throw new Error((data && data.detail) || "请先开通 VIP");
      if (!res.ok) throw new Error((data && data.message) || (data && data.detail) || "HTTP " + res.status);
      if (data && data.ok === false) {
        if (String(data.message || "").indexOf("4001") >= 0 || String(data.message || "").indexOf("限流") >= 0) {
          await sleep(600 * (i + 1));
          continue;
        }
        throw new Error(data.message || "请求失败");
      }
      return data;
    }
    throw new Error("请求失败，请稍后重试");
  }

  function getActiveCfg() {
    var key = ($("radar-strict") && $("radar-strict").value) || "balanced";
    var p = PRESETS[key] || PRESETS.balanced;
    return Object.assign({}, CFG, p);
  }

  function getSignalMode() {
    return ($("radar-signal") && $("radar-signal").value) || "both";
  }

  function getPriceBand() {
    var v = ($("radar-price") && $("radar-price").value) || "any";
    return v === "under10" ? "under10" : "any";
  }

  function priceInBand(px) {
    if (getPriceBand() !== "under10") return true;
    var v = Number(px);
    return isFinite(v) && v >= 2 && v < 10;
  }

  function getPullbackCfg(cfg) {
    var strict = ($("radar-strict") && $("radar-strict").value) || "balanced";
    var base = { pullMin: 0.08, pullMax: 0.25, volShrink: 0.72, minScore: 6, ztDaysMin: 5, ztDaysMax: 20, volLaunch: 1.15, ma20Tol: 0.98 };
    if (strict === "strict") return Object.assign({}, base, { pullMin: 0.10, pullMax: 0.22, volShrink: 0.65, minScore: 7, ztDaysMax: 15 });
    if (strict === "loose") return Object.assign({}, base, { pullMin: 0.06, pullMax: 0.30, volShrink: 0.80, minScore: 5, ztDaysMin: 3, ztDaysMax: 25, ma20Tol: 0.96 });
    return base;
  }

  function boardMeta(code) {
    var c = String(code || "").split(".")[0];
    var is300 = c.indexOf("300") === 0 || c.indexOf("301") === 0;
    var is688 = c.indexOf("688") === 0;
    var isBj = c.indexOf("8") === 0 || c.indexOf("4") === 0 || c.indexOf("920") === 0;
    var limit = (is300 || is688) ? 0.2 : 0.1;
    return { c: c, is300: is300, is688: is688, isBj: isBj, limit: limit, bigDrop: (is300 || is688) ? CFG.bigDropGrowth : CFG.bigDropMain };
  }

  function isLimitUp(close, prev, limit) { return close >= prev * (1 + limit) - 0.003; }
  function isOneWordLimit(open, low, prev, limit) {
    var zt = prev * (1 + limit) - 0.003;
    return open >= zt && low >= zt;
  }

  function getTradingDays(count) {
    var days = [];
    var d = new Date();
    d.setHours(0, 0, 0, 0);
    while (days.length < count) {
      if (d.getDay() !== 0 && d.getDay() !== 6) days.push(d.getTime());
      d.setDate(d.getDate() - 1);
    }
    return days;
  }

  function normThscode(raw, fallback) {
    var s = String(raw || "").trim().toUpperCase();
    if (/^\d{6}\.(SH|SZ)$/.test(s)) return s;
    var c = String(fallback || s).replace(/\D/g, "").slice(-6);
    while (c.length < 6) c = "0" + c;
    if (/^(6|9|5)/.test(c)) return c + ".SH";
    return c + ".SZ";
  }

  function sortKlineItems(items) {
    return (items || []).slice().sort(function (a, b) {
      return Number(a.date_ms || 0) - Number(b.date_ms || 0);
    });
  }

  function cacheKline(thscode, items) {
    var sorted = sortKlineItems(items);
    if (sorted.length >= 180) {
      var key = normThscode(thscode);
      klineMemCache[key] = sorted;
      idbSetKline(key, sorted);
    }
    return sorted;
  }

  function flattenLadderItems(items) {
    var out = [];
    (items || []).forEach(function (row) {
      if (row && row.thscode) { out.push(row); return; }
      var boards = row && row.boards;
      if (!boards || typeof boards !== "object") return;
      Object.keys(boards).forEach(function (k) {
        var arr = boards[k];
        if (Array.isArray(arr)) arr.forEach(function (s) { if (s) out.push(s); });
      });
    });
    return out;
  }

  function parseKlineBase(items, stock) {
    items = sortKlineItems(items);
    if (!items || items.length < 180) return null;
    var code = stock.thscode || stock.ticker || "";
    if (boardMeta(code).isBj) return null;
    var closes = [], highs = [], lows = [], opens = [], volumes = [], turnovers = [];
    items.forEach(function (it) {
      closes.push(Number(it.close_price));
      opens.push(Number(it.open_price));
      highs.push(Number(it.high_price));
      lows.push(Number(it.low_price));
      volumes.push(Number(it.volume || 0));
      turnovers.push(Number(it.turnover || 0));
    });
    var last = closes.length - 1;
    function MA(period, idx) {
      if (idx < period - 1) return null;
      var sum = 0;
      for (var i = idx - period + 1; i <= idx; i++) sum += closes[i];
      return sum / period;
    }
    return { stock: stock, closes: closes, highs: highs, lows: lows, opens: opens, volumes: volumes, turnovers: turnovers, last: last, MA: MA, meta: boardMeta(code) };
  }

  function calcZtStats(base, cfg) {
    var closes = base.closes, opens = base.opens, lows = base.lows, turnovers = base.turnovers, last = base.last, limit = base.meta.limit;
    var ztWindow = cfg.ztDays;
    var zt250 = 0, ztRecent = 0, hasQualifiedZt = false, lastZtDaysAgo = 999;
    for (var i = Math.max(1, last - 249); i <= last; i++) {
      var prev = closes[i - 1];
      if (!isLimitUp(closes[i], prev, limit)) continue;
      zt250++;
      var daysAgo = last - i;
      if (daysAgo < lastZtDaysAgo) lastZtDaysAgo = daysAgo;
      if (i >= last - (ztWindow - 1)) {
        ztRecent++;
        if (!isOneWordLimit(opens[i], lows[i], prev, limit) && turnovers[i] >= cfg.ztAmountMin) hasQualifiedZt = true;
      }
    }
    return { zt250: zt250, ztRecent: ztRecent, hasQualifiedZt: hasQualifiedZt, lastZtDaysAgo: lastZtDaysAgo === 999 ? null : lastZtDaysAgo };
  }

  function checkBigCycle(cfg, MA, ma5, ma10, ma20, ma30, ma60, ma144, last) {
    var ma144Prev = MA(144, last - cfg.ma144Lookback);
    if (!ma60 || !ma144 || !ma144Prev) return { ok: false, reason: "均线数据不足" };
    if (cfg.bigCycleMode === "full") {
      if (!(ma5 > ma60 && ma10 > ma60 && ma20 > ma60 && ma30 > ma60 && ma60 > ma144 && ma144 > ma144Prev)) return { ok: false, reason: "大周期多头不足" };
      return { ok: true };
    }
    if (cfg.bigCycleMode === "medium") {
      if (!(ma20 > ma60 && ma30 > ma60 && ma60 > ma144)) return { ok: false, reason: "MA20/30未站上MA60" };
      var ma144Prev10 = MA(144, last - 10);
      if (!(ma144 >= ma144Prev * cfg.ma144FlatPct || (ma144Prev10 && ma144 >= ma144Prev10 * 0.995))) return { ok: false, reason: "MA144未走平向上" };
      return { ok: true };
    }
    if (!(ma60 > ma144 && ma144 >= ma144Prev * cfg.ma144FlatPct)) return { ok: false, reason: "MA60/MA144不足" };
    return { ok: true };
  }

  function checkDiverge(cfg, MA, ma5, ma10, ma20, last) {
    var ma5_1 = MA(5, last - 1), ma5_2 = MA(5, last - 2);
    if (cfg.divergeMode === "full") {
      return (ma5 > ma10 && ma10 > ma20 && ma5_1 && ma5_2 && ma5 > ma5_1 && ma5_1 > ma5_2) ? { ok: true } : { ok: false };
    }
    if (cfg.divergeMode === "medium") {
      return (ma5 > ma10 && ma10 > ma20 && ma5_1 && ma5 > ma5_1) ? { ok: true } : { ok: false };
    }
    return (ma5 > ma20 && ma5_1 && ma5 > ma5_1) ? { ok: true } : { ok: false };
  }

  function checkVolume(cfg, volumes, last) {
    function volMa5At(idx) {
      var s = 0;
      for (var i = idx - 4; i <= idx; i++) s += volumes[i];
      return s / 5;
    }
    if (cfg.volMode === "today") return volumes[last] > volMa5At(last) ? { ok: true } : { ok: false };
    for (var i = last - 2; i <= last; i++) {
      if (i >= 4 && volumes[i] >= volMa5At(i) * cfg.volMultiple) return { ok: true };
    }
    return { ok: false };
  }

  function avgRange(highs, lows, closes, from, to) {
    var s = 0, c = 0;
    for (var i = from; i <= to; i++) { s += (highs[i] - lows[i]) / closes[i]; c++; }
    return c ? s / c : 0;
  }

  function avgBody(opens, closes, from, to) {
    var s = 0, c = 0;
    for (var i = from; i <= to; i++) { s += Math.abs(closes[i] - opens[i]) / closes[i]; c++; }
    return c ? s / c : 0;
  }

  function makeResultRow(stock, price, fields) {
    var code = String(stock.thscode || stock.ticker || "").split(".")[0];
    return Object.assign({
      thscode: stock.thscode, code: code, name: stock.name, ticker: stock.ticker,
      price: price, scanTime: Date.now(),
      bondCount: null, pullPct: null, daysSinceZt: null, stabScore: null
    }, fields);
  }

  function analyzeStock(klineItems, stock) {
    var cfg = getActiveCfg();
    var base = parseKlineBase(klineItems, stock);
    if (!base) return { pass: false, reason: "[粘合]数据不足" };
    if (base.closes.length < cfg.minListDays + 30) return { pass: false, reason: "[粘合]上市不足" };
    if (!priceInBand(base.closes[base.last])) return { pass: false, reason: "[粘合]股价不符" };
    var zt = calcZtStats(base, cfg);
    if (zt.zt250 < cfg.ztYearMin || zt.zt250 > cfg.ztYearMax) return { pass: false, reason: "[粘合]年涨停不符" };
    if (zt.ztRecent < 1 || !zt.hasQualifiedZt) return { pass: false, reason: "[粘合]近端涨停不符" };
    var last = base.last, MA = base.MA, closes = base.closes, lows = base.lows, volumes = base.volumes, turnovers = base.turnovers, bigDrop = base.meta.bigDrop;
    var ma5 = MA(5, last), ma10 = MA(10, last), ma20 = MA(20, last), ma30 = MA(30, last), ma60 = MA(60, last), ma144 = MA(144, last);
    if (!ma5 || !ma10 || !ma20 || !ma30 || !ma60 || !ma144) return { pass: false, reason: "[粘合]均线不足" };
    if (!checkBigCycle(cfg, MA, ma5, ma10, ma20, ma30, ma60, ma144, last).ok) return { pass: false, reason: "[粘合]大周期" };
    var bondCount = 0;
    for (var i = last - (cfg.bondWindow - 1); i <= last; i++) {
      var m5 = MA(5, i), m10 = MA(10, i), m20 = MA(20, i);
      if (m5 && m10 && m20) {
        var th = cfg.bondThreshold;
        if (Math.abs(m5 / m20 - 1) <= th && Math.abs(m10 / m20 - 1) <= th && Math.abs(m5 / m10 - 1) <= th) bondCount++;
      }
    }
    if (bondCount < cfg.bondMinCount) return { pass: false, reason: "[粘合]粘合不足" };
    if (!checkDiverge(cfg, MA, ma5, ma10, ma20, last).ok) return { pass: false, reason: "[粘合]发散" };
    if (!checkVolume(cfg, volumes, last).ok) return { pass: false, reason: "[粘合]放量" };
    var low60 = Math.min.apply(null, lows.slice(last - 59, last + 1));
    var rise60 = closes[last] / low60 - 1;
    if (rise60 > cfg.maxStageRise) return { pass: false, reason: "[粘合]涨幅过大" };
    var avgTurnover20 = turnovers.slice(last - 19, last + 1).reduce(function (a, b) { return a + b; }, 0) / 20;
    if (avgTurnover20 < cfg.avgAmountMin) return { pass: false, reason: "[粘合]流动性" };
    for (var j = last - 9; j <= last; j++) {
      if (j > 0 && closes[j] / closes[j - 1] <= bigDrop) return { pass: false, reason: "[粘合]大阴线" };
    }
    return {
      pass: true,
      data: makeResultRow(stock, closes[last], {
        signalType: "粘合启动", matchLabel: cfg.name, matchScore: bondCount + 4,
        bondCount: bondCount, zt10: zt.ztRecent, ztYear: zt.zt250,
        rise: Number((rise60 * 100).toFixed(1)), avgTurnover: Math.round(avgTurnover20 / 10000)
      })
    };
  }

  function analyzePullback(klineItems, stock) {
    var cfg = getActiveCfg();
    var pb = getPullbackCfg(cfg);
    var base = parseKlineBase(klineItems, stock);
    if (!base) return { pass: false, reason: "[回踩]数据不足" };
    if (!priceInBand(base.closes[base.last])) return { pass: false, reason: "[回踩]股价不符" };
    if (base.meta.is300 || base.meta.is688) pb.pullMax = Math.min(pb.pullMax + 0.05, 0.35);
    var zt = calcZtStats(base, cfg);
    if (zt.zt250 < cfg.ztYearMin || zt.zt250 > cfg.ztYearMax) return { pass: false, reason: "[回踩]年涨停" };
    if (zt.lastZtDaysAgo == null || zt.lastZtDaysAgo < pb.ztDaysMin || zt.lastZtDaysAgo > pb.ztDaysMax) return { pass: false, reason: "[回踩]距涨停" };
    var last = base.last, MA = base.MA, closes = base.closes, highs = base.highs, lows = base.lows, opens = base.opens, volumes = base.volumes, turnovers = base.turnovers, bigDrop = base.meta.bigDrop;
    var ma5 = MA(5, last), ma10 = MA(10, last), ma20 = MA(20, last), ma30 = MA(30, last), ma60 = MA(60, last), ma144 = MA(144, last);
    if (!checkBigCycle(cfg, MA, ma5, ma10, ma20, ma30, ma60, ma144, last).ok) return { pass: false, reason: "[回踩]大周期" };
    var high20 = Math.max.apply(null, closes.slice(Math.max(0, last - 19), last + 1));
    var pullPct = (high20 - closes[last]) / high20;
    if (pullPct < pb.pullMin || pullPct > pb.pullMax) return { pass: false, reason: "[回踩]回撤" };
    for (var i = last - 4; i <= last; i++) {
      var ma20i = MA(20, i);
      if (ma20i && lows[i] < ma20i * pb.ma20Tol) return { pass: false, reason: "[回踩]破MA20" };
    }
    var volMa5 = volumes.slice(last - 4, last + 1).reduce(function (a, b) { return a + b; }, 0) / 5;
    var volMa20 = volumes.slice(last - 19, last + 1).reduce(function (a, b) { return a + b; }, 0) / 20;
    if (volMa5 >= volMa20 * pb.volShrink) return { pass: false, reason: "[回踩]未缩量" };
    var low60 = Math.min.apply(null, lows.slice(last - 59, last + 1));
    var rise60 = closes[last] / low60 - 1;
    if (rise60 > cfg.maxStageRise) return { pass: false, reason: "[回踩]涨幅过大" };
    var avgTurnover20 = turnovers.slice(last - 19, last + 1).reduce(function (a, b) { return a + b; }, 0) / 20;
    if (avgTurnover20 < cfg.avgAmountMin) return { pass: false, reason: "[回踩]流动性" };
    for (var j = last - 9; j <= last; j++) {
      if (j > 0 && closes[j] / closes[j - 1] <= bigDrop) return { pass: false, reason: "[回踩]大阴线" };
    }
    var score = 0;
    var ma5_1 = MA(5, last - 1), ma5_2 = MA(5, last - 2);
    if (ma5_1 && ma5_2 && ma5 > ma5_1 && ma5_1 <= ma5_2) score += 2;
    if (closes[last] > ma5) score += 2;
    if (volumes[last] > volMa5 * pb.volLaunch) score += 2;
    if (avgRange(highs, lows, closes, last - 2, last) < avgRange(highs, lows, closes, last - 9, last) * 0.85) score += 1;
    if (avgBody(opens, closes, last - 2, last) < 0.03) score += 1;
    var hl = highs[last] - lows[last];
    if (hl > 0 && (closes[last] - lows[last]) / hl > 0.6) score += 1;
    if (ma5_1 && Math.abs(ma5 / ma10 - 1) < 0.02 && ma5 > ma5_1) score += 1;
    if (zt.lastZtDaysAgo >= 5 && zt.lastZtDaysAgo <= 15) score += 1;
    if (score < pb.minScore) return { pass: false, reason: "[回踩]评分不足" };
    var stabLabel = score >= 8 ? "较强" : "关注";
    return {
      pass: true,
      data: makeResultRow(stock, closes[last], {
        signalType: "回踩二波", matchLabel: cfg.name + "·" + stabLabel, matchScore: score,
        pullPct: Number((pullPct * 100).toFixed(1)), daysSinceZt: zt.lastZtDaysAgo, stabScore: score,
        zt10: zt.ztRecent, ztYear: zt.zt250, rise: Number((rise60 * 100).toFixed(1)),
        avgTurnover: Math.round(avgTurnover20 / 10000)
      })
    };
  }

  function mergeHit(map, data) {
    var key = data.thscode || data.code;
    if (!map[key]) { map[key] = data; return; }
    var old = map[key];
    if (old.signalType === data.signalType) return;
    map[key] = Object.assign({}, old, data, {
      signalType: "双信号",
      matchLabel: old.matchLabel + "+" + data.matchLabel,
      matchScore: (Number(old.matchScore) || 0) + (Number(data.matchScore) || 0),
      bondCount: old.bondCount != null ? old.bondCount : data.bondCount,
      pullPct: data.pullPct != null ? data.pullPct : old.pullPct,
      daysSinceZt: data.daysSinceZt != null ? data.daysSinceZt : old.daysSinceZt,
      stabScore: data.stabScore != null ? data.stabScore : old.stabScore
    });
  }

  function addCandidate(map, s) {
    if (!s) return;
    if (s.is_st || s.is_new) return;
    var thscode = normThscode(s.thscode, s.ticker || s.code);
    if (boardMeta(thscode).isBj) return;
    if (!map[thscode]) {
      map[thscode] = {
        thscode: thscode,
        ticker: s.ticker || thscode.split(".")[0],
        name: s.name || s.stock_name || thscode
      };
    }
  }

  async function fetchKlineDelta(thscode, prevItems) {
    var key = normThscode(thscode);
    var r = await proxyGet("/api/radar/proxy/kline?thscode=" + encodeURIComponent(key) + "&days=30&adjust=forward");
    return cacheKline(key, mergeKlineItems(prevItems, r.items || []));
  }

  async function fetchKlineItems(thscode) {
    var key = normThscode(thscode);
    if (klineMemCache[key]) return klineMemCache[key];
    var r = await proxyGet("/api/radar/proxy/kline?thscode=" + encodeURIComponent(key) + "&days=" + CFG.klineDays + "&adjust=forward");
    return cacheKline(key, r.items || []);
  }

  async function prefetchKlines(thscodes, setProgress, opts) {
    opts = opts || {};
    var need = [];
    var seen = Object.create(null);
    var needFull = [];
    var needDelta = [];
    thscodes.forEach(function (c) {
      var key = normThscode(c);
      if (!key || seen[key] || klineMemCache[key]) return;
      seen[key] = 1;
      need.push(key);
    });
    if (!need.length) return 0;

    if (!opts.forceFull) {
      for (var ni = 0; ni < need.length; ni++) {
        if (scanAbort) break;
        var code = need[ni];
        // eslint-disable-next-line no-await-in-loop
        var hit = await idbGetKline(code);
        if (hit && hit.day === todayKey() && hit.items && hit.items.length >= 180) {
          klineMemCache[code] = sortKlineItems(hit.items);
        } else if (hit && hit.items && hit.items.length >= 180) {
          needDelta.push({ code: code, prev: hit.items });
        } else {
          needFull.push(code);
        }
      }
    } else {
      needFull = need.slice();
    }

    var cachedN = need.length - needFull.length - needDelta.length;
    if (cachedN > 0) {
      setProgress(18, "读取走势", "已沿用本地 " + cachedN + " 只…");
    }

    if (needDelta.length && !scanAbort) {
      setProgress(20, "读取走势", "更新 " + needDelta.length + " 只最新走势…");
      await concurrentMap(needDelta, 4, async function (row) {
        if (scanAbort) return;
        try { await fetchKlineDelta(row.code, row.prev); } catch (e) {}
      });
    }

    needFull = needFull.filter(function (c) { return !klineMemCache[c]; });
    if (!needFull.length) {
      return need.filter(function (c) { return !klineMemCache[c]; }).length;
    }

    var chunks = [];
    for (var i = 0; i < needFull.length; i += CFG.batchSize) chunks.push(needFull.slice(i, i + CFG.batchSize));
    var done = cachedN, total = need.length, t0 = Date.now();
    await concurrentMap(chunks, CFG.batchConcurrency, async function (chunk) {
      if (scanAbort) return;
      var r = await proxyPost("/api/radar/proxy/kline-batch", {
        thscodes: chunk,
        days: CFG.klineDays,
        adjust: "forward"
      });
      var map = (r && r.items) || {};
      Object.keys(map).forEach(function (code) { cacheKline(code, map[code]); });
      done += chunk.length;
      var pct = 20 + Math.floor(done / total * 50);
      var elapsed = (Date.now() - t0) / 1000;
      var eta = done > 0 ? Math.round(elapsed / done * (total - done)) : 0;
      var etaStr = eta > 60 ? "约" + Math.ceil(eta / 60) + "分钟" : "约" + eta + "秒";
      setProgress(pct, "读取走势", "已读取 " + done + "/" + total + " · 剩余 " + etaStr);
    });
    var missing = need.filter(function (c) { return !klineMemCache[c]; });
    if (missing.length && !scanAbort) {
      setProgress(72, "读取走势", "补全 " + missing.length + " 只…");
      await concurrentMap(missing, 4, async function (code) {
        if (scanAbort) return;
        try { await fetchKlineItems(code); } catch (e) {}
      });
    }
    return need.filter(function (c) { return !klineMemCache[c]; }).length;
  }

  async function fetchTodayPools(map, onProgress) {
    await fetchLimitUpPool(getTradingDays(1), map, onProgress || function () {});
    await fetchHotPools(map, onProgress || function () {});
  }

  async function buildCandidateList(setProgress, opts) {
    opts = opts || {};
    var cfg = getActiveCfg();
    var strict = ($("radar-strict") && $("radar-strict").value) || "balanced";
    var scanDays = cfg.scanDays || 30;
    var map = {};
    var cached = !opts.forceFull && loadPoolCache();
    var canIncremental = cached && cached.strictness === strict && cached.scanDays === scanDays && cached.stocks;
    var today = todayKey();

    if (canIncremental && cached.day === today) {
      lastScanMode = "incremental";
      Object.keys(cached.stocks).forEach(function (k) {
        var s = cached.stocks[k];
        map[k] = { thscode: k, name: s.name, ticker: s.ticker };
      });
      setProgress(8, "汇总股票", "沿用上次的列表（" + Object.keys(map).length + " 只），刷新今日热门…");
      await fetchTodayPools(map, function (msg) { setProgress(12, "汇总股票", msg); });
    } else if (canIncremental && cached.day < today) {
      lastScanMode = "incremental";
      Object.keys(cached.stocks).forEach(function (k) {
        var s = cached.stocks[k];
        map[k] = { thscode: k, name: s.name, ticker: s.ticker };
      });
      prunePoolMap(map, cached.stocks, scanDays);
      setProgress(8, "汇总股票", "在已有 " + Object.keys(map).length + " 只基础上，补今日热门…");
      await fetchTodayPools(map, function (msg) { setProgress(12, "汇总股票", msg); });
    } else {
      lastScanMode = opts.forceFull ? "full" : "full";
      setProgress(8, "汇总股票", "汇总近" + scanDays + "日热门涨停股…");
      await fetchLimitUpPool(getTradingDays(scanDays), map, function (msg) { setProgress(12, "汇总股票", msg); });
      await fetchHotPools(map, function (msg) { setProgress(18, "补充热门", msg); });
    }
    savePoolCache(map, scanDays, strict);
    return Object.keys(map).map(function (k) { return map[k]; });
  }

  async function fetchLimitUpPool(tradingDays, map, onProgress) {
    await concurrentMap(tradingDays, CFG.poolConcurrency, async function (dayMs, di) {
      if (scanAbort) return;
      onProgress("热门涨停 " + (di + 1) + "/" + tradingDays.length + " · " + fmtDateMs(dayMs));
      try {
        for (var page = 1; page <= 3; page++) {
          var r = null;
          for (var attempt = 0; attempt < 3; attempt++) {
            try {
              r = await proxyGet("/api/radar/proxy/special?name=limit-up-pool&date_ms=" + dayMs + "&page=" + page + "&size=200");
              break;
            } catch (eTry) {
              if (attempt >= 2) throw eTry;
              await sleep(400 * (attempt + 1));
            }
          }
          var items = r.items || [];
          items.forEach(function (s) { addCandidate(map, s); });
          if (items.length < 200) break;
        }
      } catch (e) { /* skip day */ }
    });
  }

  async function fetchHotPools(map, onProgress) {
    onProgress("补充连板、热股、飙升榜…");
    var tasks = [
      proxyGet("/api/radar/proxy/special?name=limit-up-ladder&page=1&size=300&period=day").catch(function () { return { items: [] }; }),
      proxyGet("/api/radar/proxy/special?name=hot-stock-list&page=1&size=30&period=day").catch(function () { return { items: [] }; }),
      proxyGet("/api/radar/proxy/special?name=skyrocket-list&page=1&size=30&period=day").catch(function () { return { items: [] }; })
    ];
    var rs = await Promise.all(tasks);
    flattenLadderItems(rs[0].items || []).forEach(function (s) { addCandidate(map, s); });
    (rs[1].items || []).forEach(function (s) { addCandidate(map, s); });
    (rs[2].items || []).forEach(function (s) { addCandidate(map, s); });
  }

  async function concurrentMap(items, concurrency, fn) {
    var idx = 0;
    async function worker() {
      while (idx < items.length) {
        if (scanAbort) return;
        var i = idx++;
        try { await fn(items[i], i); } catch (e) {}
      }
    }
    var n = Math.min(concurrency, items.length || 1);
    await Promise.all(Array.from({ length: n }, worker));
  }

  async function scanCandidates(candidateList, setProgress, opts) {
    var signalMode = getSignalMode();
    var klineMiss = await prefetchKlines(candidateList.map(function (s) { return s.thscode; }), setProgress, opts);
    if (scanAbort) return { results: [], filterStats: {}, scanned: 0, elapsed_s: 0, klineMiss: klineMiss };
    var done = 0, hitMap = {}, filterStats = {}, t0 = Date.now();
    for (var si = 0; si < candidateList.length; si++) {
      if (scanAbort) break;
      var stock = candidateList[si];
      done++;
      var pct = 75 + Math.floor(done / candidateList.length * 22);
      setProgress(pct, "正在筛选", "已看 " + done + "/" + candidateList.length + " · 入选 " + Object.keys(hitMap).length);
      try {
        var kline = klineMemCache[normThscode(stock.thscode, stock.ticker)];
        if (!kline || !kline.length) {
          filterStats["__kline_miss__"] = (filterStats["__kline_miss__"] || 0) + 1;
          continue;
        }
        if (signalMode === "bond" || signalMode === "both") {
          var res = analyzeStock(kline, stock);
          if (res.pass) mergeHit(hitMap, res.data);
          else filterStats[res.reason] = (filterStats[res.reason] || 0) + 1;
        }
        if (signalMode === "pullback" || signalMode === "both") {
          var res2 = analyzePullback(kline, stock);
          if (res2.pass) mergeHit(hitMap, res2.data);
          else filterStats[res2.reason] = (filterStats[res2.reason] || 0) + 1;
        }
      } catch (e) {}
    }
    var results = Object.keys(hitMap).map(function (k) { return hitMap[k]; });
    var pri = { "双信号": 3, "回踩二波": 2, "粘合启动": 1 };
    results.sort(function (a, b) {
      return (pri[b.signalType] || 0) - (pri[a.signalType] || 0)
        || (Number(b.matchScore) || 0) - (Number(a.matchScore) || 0)
        || (Number(b.zt10) || 0) - (Number(a.zt10) || 0);
    });
    return { results: results, filterStats: filterStats, scanned: candidateList.length, elapsed_s: Math.round((Date.now() - t0) / 1000), klineMiss: klineMiss };
  }

  function signalClass(t) {
    if (t === "双信号") return "tag-radar-both";
    if (t === "回踩二波") return "tag-radar-pull";
    return "tag-radar-bond";
  }

  function secidForCode(code) {
    var c = String(code || "").replace(/\D/g, "").slice(-6);
    if (/^(6|9|5)/.test(c)) return "1." + c;
    return "0." + c;
  }

  function quoteHref(item) {
    return "demo.html?secid=" + encodeURIComponent(secidForCode(item.code))
      + "&period=day" + (item.name ? "&name=" + encodeURIComponent(item.name) : "");
  }

  function humanFilterReason(raw) {
    var s = String(raw || "").replace(/^\[(粘合|回踩)\]/, "").trim();
    var map = {
      "行情缺失": "走势数据暂缺",
      "__kline_miss__": "走势数据暂缺",
      "数据不足": "历史走势不足",
      "上市不足": "上市时间偏短",
      "年涨停不符": "年度涨停次数不符",
      "近端涨停不符": "近期缺少合格涨停",
      "均线不足": "均线数据不足",
      "大周期": "大趋势条件未满足",
      "粘合不足": "均线粘合不够",
      "发散": "短期均线未发散",
      "放量": "近期量能不足",
      "涨幅过大": "阶段涨幅偏大",
      "流动性": "成交额偏低",
      "大阴线": "近端有大阴线",
      "年涨停": "年度涨停次数不符",
      "距涨停": "距最近涨停时间不符",
      "回撤": "回调幅度不符",
      "破MA20": "跌破20日均线",
      "未缩量": "回调未缩量",
      "评分不足": "企稳评分偏低",
      "股价不符": "现价不在所选区间（10元下为 2～10 元）"
    };
    return map[s] || s;
  }

  function renderChips() {
    var el = $("radar-chips");
    if (!el) return;
    el.innerHTML = "";
    el.hidden = true;
  }

  function renderFilterStats(stats) {
    var box = $("radar-filter-stats");
    var grid = $("radar-filter-grid");
    if (!box || !grid) return;
    var entries = Object.entries(stats || {}).sort(function (a, b) { return b[1] - a[1]; });
    if (!entries.length) { box.hidden = true; return; }
    box.hidden = false;
    grid.innerHTML = entries.slice(0, 20).map(function (e) {
      return '<div class="filter-stat-item"><span>' + esc(humanFilterReason(e[0])) + '</span><span class="num">' + e[1] + "</span></div>";
    }).join("");
  }

  function showEmpty(msg) {
    $("radar-result-section").hidden = true;
    var empty = $("radar-empty");
    if (empty) { empty.hidden = false; empty.querySelector("p").textContent = msg || "暂无入选标的"; }
    if ($("radar-clear")) $("radar-clear").hidden = true;
  }

  function renderResults(items) {
    var sec = $("radar-result-section");
    var empty = $("radar-empty");
    var tbody = $("radar-results");
    var cnt = $("radar-count");
    if (!tbody) return;
    if (empty) empty.hidden = true;
    if (cnt) cnt.textContent = String((items || []).length);
    if (!items || !items.length) { showEmpty("暂无入选标的"); return; }
    if (sec) sec.hidden = false;
    if ($("radar-clear")) $("radar-clear").hidden = false;
    tbody.innerHTML = items.map(function (it) {
      var sig = it.signalType || "";
      var pull = fmtMetric(it.pullPct, "%", metricNaTip(sig, "pull"));
      var ds = fmtMetric(it.daysSinceZt, "日", metricNaTip(sig, "ztgap"));
      var stab = fmtMetric(it.stabScore, "", metricNaTip(sig, "stab"));
      var bond = fmtMetric(it.bondCount, "次", metricNaTip(sig, "bond"));
      var zt10 = it.zt10 != null && isFinite(Number(it.zt10))
        ? '<span class="tag-zt">' + esc(it.zt10) + "次</span>"
        : fmtMetric(null, "", "");
      var ztYear = fmtMetric(it.ztYear, "次", "");
      var rise = it.rise != null && isFinite(Number(it.rise))
        ? '<span class="tag-rise">+' + esc(Number(it.rise).toFixed(1)) + "%</span>"
        : fmtMetric(null, "", "");
      var avgTurn = it.avgTurnover != null && isFinite(Number(it.avgTurnover))
        ? esc(it.avgTurnover) + "万"
        : fmtMetric(null, "", "");
      return "<tr>"
        + '<td><span class="' + signalClass(sig) + '">' + esc(sig) + "</span></td>"
        + '<td><span class="tag-match">' + esc(it.matchLabel || "—") + "</span></td>"
        + '<td><a class="stock-name" href="' + esc(quoteHref(it)) + '" target="_blank" rel="noopener">' + esc(it.name || it.code) + "</a></td>"
        + '<td class="code">' + esc(it.code) + "</td>"
        + '<td class="price">' + esc(fmtPrice(it.price)) + "</td>"
        + '<td class="code">' + pull + "</td>"
        + '<td class="code">' + ds + "</td>"
        + '<td class="code">' + stab + "</td>"
        + '<td class="code">' + bond + "</td>"
        + '<td>' + zt10 + "</td>"
        + '<td class="code">' + ztYear + "</td>"
        + '<td>' + rise + "</td>"
        + '<td class="code">' + avgTurn + "</td>"
        + '<td class="code">' + esc(fmtDateTime(it.scanTime)) + "</td>"
        + "</tr>";
    }).join("");
  }

  function loadHistory() {
    try {
      var raw = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]") || [];
      var seen = Object.create(null);
      var out = [];
      raw.forEach(function (h) {
        var fp = entryFingerprint(h);
        if (!fp || seen[fp]) return;
        seen[fp] = 1;
        if (!h.fp) h.fp = fp;
        out.push(h);
      });
      if (out.length !== raw.length) {
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(out)); } catch (e1) {}
      }
      return out;
    } catch (e) { return []; }
  }

  function historyFingerprint(items, signal, strictness, price) {
    var sig = String(signal || "both");
    var st = String(strictness || "balanced");
    var px = String(price || "any");
    var core = (items || []).slice().sort(function (a, b) {
      return String(a.code || "").localeCompare(String(b.code || ""));
    }).map(function (it) {
      return [
        it.code || "",
        it.signalType || "",
        it.matchScore != null ? it.matchScore : "",
        it.bondCount != null ? it.bondCount : "",
        it.pullPct != null ? it.pullPct : "",
        it.daysSinceZt != null ? it.daysSinceZt : "",
        it.stabScore != null ? it.stabScore : ""
      ].join(":");
    }).join("|");
    return sig + ";" + st + ";" + px + ";" + core;
  }

  function entryFingerprint(entry) {
    if (!entry) return "";
    if (entry.fp) return entry.fp;
    return historyFingerprint(entry.items || [], entry.signal || "both", entry.strictness || "balanced", entry.price || "any");
  }

  function saveHistoryEntry(payload) {
    if (!payload.results || !payload.results.length) return;
    var signal = ($("radar-signal") && $("radar-signal").value) || "both";
    var strictness = ($("radar-strict") && $("radar-strict").value) || "balanced";
    var price = getPriceBand();
    var fp = historyFingerprint(payload.results, signal, strictness, price);
    var hist = loadHistory();
    for (var i = 0; i < hist.length; i++) {
      if (entryFingerprint(hist[i]) === fp) return;
    }
    hist.unshift({
      id: Date.now(), time: Date.now(), fp: fp, signal: signal, strictness: strictness, price: price,
      count: payload.results.length, scanned: payload.scanned,
      elapsed_s: payload.elapsed_s, items: payload.results.slice(),
      filterStats: payload.filterStats || {}
    });
    if (hist.length > MAX_HISTORY) hist.length = MAX_HISTORY;
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(hist)); } catch (e) {}
    renderHistory();
  }

  function renderHistory() {
    var box = $("radar-history");
    var list = $("radar-history-list");
    if (!box || !list) return;
    var hist = loadHistory();
    if (!hist.length) { box.hidden = true; return; }
    box.hidden = false;
    list.innerHTML = hist.map(function (h) {
      var names = h.items.slice(0, 3).map(function (s) { return s.name; }).join("、");
      if (h.items.length > 3) names += " 等" + h.items.length + "只";
      return '<div class="radar-history-item" data-id="' + h.id + '">'
        + '<div class="info"><b>' + h.count + '只</b>' + esc(names)
        + '<div class="sub">共看 ' + (h.scanned || "?") + " 只" + (h.elapsed_s ? " · 用时 " + h.elapsed_s + " 秒" : "") + "</div></div>"
        + '<span class="time">' + esc(fmtDateTime(h.time)) + '</span>'
        + '<span class="del" data-del="' + h.id + '">删除</span></div>';
    }).join("");
    list.querySelectorAll(".radar-history-item .info").forEach(function (el) {
      el.addEventListener("click", function () {
        var id = Number(el.parentElement.getAttribute("data-id"));
        var row = loadHistory().filter(function (x) { return x.id === id; })[0];
        if (!row) return;
        renderFilterStats(row.filterStats);
        renderResults(row.items);
        setStatus("历史记录 · " + fmtDateTime(row.time), false);
      });
    });
    list.querySelectorAll(".del").forEach(function (el) {
      el.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var id = Number(el.getAttribute("data-del"));
        var next = loadHistory().filter(function (x) { return x.id !== id; });
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch (e) {}
        renderHistory();
      });
    });
  }

  function setProgress(pct, stage, detail) {
    var bar = $("radar-progress-fill");
    var txt = $("radar-progress-text");
    var stageEl = $("radar-progress-stage");
    var pctEl = $("radar-progress-pct");
    var p = Math.max(0, Math.min(100, Number(pct) || 0));
    if (bar) bar.style.width = p + "%";
    if (stageEl) stageEl.textContent = stage || "扫描中";
    if (pctEl) pctEl.textContent = Math.round(p) + "%";
    if (txt) txt.textContent = detail || "";
  }

  var scanning = false;
  var _confirmResolve = null;

  function closeRadarConfirm(ok) {
    var box = $("radar-confirm");
    if (box) box.hidden = true;
    try { document.body.classList.remove("radar-modal-open"); } catch (e0) {}
    if (_confirmResolve) {
      var fn = _confirmResolve;
      _confirmResolve = null;
      fn(!!ok);
    }
  }

  function showRadarConfirm(opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var box = $("radar-confirm");
      if (!box) { resolve(!!opts.defaultOk); return; }
      var titleEl = $("radar-confirm-title");
      var msgEl = $("radar-confirm-msg");
      var notesEl = $("radar-confirm-notes");
      var okBtn = $("radar-confirm-ok");
      var cancelBtn = $("radar-confirm-cancel");
      if (titleEl) titleEl.textContent = opts.title || "请确认";
      if (msgEl) msgEl.textContent = opts.message || "";
      if (notesEl) {
        var list = opts.notes || [];
        if (list.length) {
          notesEl.hidden = false;
          notesEl.innerHTML = list.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("");
        } else {
          notesEl.hidden = true;
          notesEl.innerHTML = "";
        }
      }
      if (okBtn) okBtn.textContent = opts.okText || "确定";
      if (cancelBtn) cancelBtn.textContent = opts.cancelText || "取消";
      _confirmResolve = resolve;
      box.hidden = false;
      try { document.body.classList.add("radar-modal-open"); } catch (e1) {}
      setTimeout(function () { if (okBtn) okBtn.focus(); }, 40);
    });
  }

  function bindRadarConfirm() {
    var box = $("radar-confirm");
    if (!box || box.__bound) return;
    box.__bound = true;
    var okBtn = $("radar-confirm-ok");
    var cancelBtn = $("radar-confirm-cancel");
    var closeBtn = $("radar-confirm-close");
    if (okBtn) okBtn.addEventListener("click", function () { closeRadarConfirm(true); });
    if (cancelBtn) cancelBtn.addEventListener("click", function () { closeRadarConfirm(false); });
    if (closeBtn) closeBtn.addEventListener("click", function () { closeRadarConfirm(false); });
    box.addEventListener("click", function (ev) {
      if (ev.target === box) closeRadarConfirm(false);
    });
    document.addEventListener("keydown", function (ev) {
      if (box.hidden) return;
      if (ev.key === "Escape") {
        ev.preventDefault();
        closeRadarConfirm(false);
      }
    });
  }

  function scanQuery() {
    var signal = getSignalMode();
    var strictness = ($("radar-strict") && $("radar-strict").value) || "balanced";
    var price = getPriceBand();
    return "signal=" + encodeURIComponent(signal)
      + "&strictness=" + encodeURIComponent(strictness)
      + "&price=" + encodeURIComponent(price);
  }

  function humanServerProgress(p) {
    var phase = String(p.phase || "");
    var msg = String(p.msg || "");
    var done = Number(p.done) || 0;
    var total = Number(p.total) || 0;
    var hits = Number(p.hits) || 0;
    var eta = Number(p.eta_s) || 0;
    var etaStr = "";
    if (eta >= 120) etaStr = " · 约剩 " + Math.max(1, Math.ceil(eta / 60)) + " 分钟";
    else if (eta > 0) etaStr = " · 约剩 " + eta + " 秒";

    if (/候选|汇总/.test(phase)) {
      var poolDetail = total > 0
        ? ("汇总热门股 " + done + "/" + total + " 天…")
        : msg.replace(/候选池/g, "股票").replace(/候选 /g, "共看 ");
      return { stage: "汇总股票", detail: poolDetail };
    }
    if (/K线|分析|筛选/.test(phase)) {
      var scanDetail = total > 0
        ? ("已筛选 " + done + "/" + total + " · 入选 " + hits + etaStr)
        : msg.replace(/命中/g, "入选").replace(/候选 /g, "共看 ");
      return { stage: "正在筛选", detail: scanDetail };
    }
    if (/完成/.test(phase)) {
      return {
        stage: "完成",
        detail: total > 0
          ? ("共看 " + total + " 只 · 入选 " + hits)
          : msg.replace(/候选 /g, "共看 ").replace(/命中/g, "入选")
      };
    }
    return { stage: phase || "扫描中", detail: msg };
  }

  async function fetchServerResult() {
    var res = await fetch(apiUrl("/api/radar/screener/result?" + scanQuery()), {
      headers: Object.assign({ Accept: "application/json" }, authHeaders()),
      credentials: "same-origin",
      cache: "no-store"
    });
    if (res.status === 401) throw new Error("登录已失效，请重新登录");
    if (res.status === 403) throw new Error("请先开通 VIP");
    var data = null;
    try { data = await res.json(); } catch (e0) { data = null; }
    if (data && data.running) return { running: true };
    if (data && data.ok === false && data.error === "no_cache") return null;
    return data;
  }

  function applyServerPayload(data, cached) {
    var items = data.items || [];
    var meta = data.meta || {};
    var elapsed = meta.elapsed_s || 0;
    var scanned = data.scanned || 0;
    renderFilterStats(data.filterStats || {});
    renderResults(items);
    var tag = cached ? " · 今日结果" : "";
    setStatus(
      "共看 " + scanned + " 只 · 入选 " + items.length + " 只"
        + (elapsed ? " · 用时 " + elapsed + " 秒" : "") + tag,
      false
    );
    if (items.length) {
      saveHistoryEntry({
        results: items,
        scanned: scanned,
        elapsed_s: elapsed,
        filterStats: data.filterStats || {}
      });
    }
  }

  async function pollServerScan() {
    var deadline = Date.now() + 15 * 60 * 1000;
    while (!scanAbort && Date.now() < deadline) {
      var res = await fetch(apiUrl("/api/radar/screener/progress"), {
        headers: Object.assign({ Accept: "application/json" }, authHeaders()),
        credentials: "same-origin",
        cache: "no-store"
      });
      var p = null;
      try { p = await res.json(); } catch (e0) { p = null; }
      if (p && p.running) {
        var hp = humanServerProgress(p);
        setProgress(Number(p.pct) || 0, hp.stage, hp.detail);
        await sleep(380);
        continue;
      }
      break;
    }
  }

  async function startServerScan(forceFull) {
    var res = await fetch(
      apiUrl("/api/radar/screener/start?" + scanQuery() + "&force=" + (forceFull ? "1" : "0")),
      {
        headers: Object.assign({ Accept: "application/json" }, authHeaders()),
        credentials: "same-origin",
        cache: "no-store"
      }
    );
    var data = null;
    try { data = await res.json(); } catch (e0) { data = null; }
    if (res.status === 401) throw new Error("登录已失效，请重新登录");
    if (res.status === 403) throw new Error((data && data.detail) || "请先开通 VIP");
    if (res.status === 429) throw new Error((data && data.detail) || "操作过于频繁，请稍后再试");
    if (!res.ok) throw new Error((data && data.message) || "启动扫描失败");
  }

  async function tryLoadServerResult() {
    try {
      var data = await fetchServerResult();
      if (data && data.ok && !data.running) {
        applyServerPayload(data, !!data.cached);
        return true;
      }
    } catch (e) {}
    return false;
  }

  async function runScan(forceFull) {
    if (scanning) return;
    scanAbort = false;
    scanning = true;
    renderChips();
    $("radar-scan").disabled = true;
    if ($("radar-scan-full")) $("radar-scan-full").disabled = true;
    $("radar-stop").hidden = false;
    $("radar-progress").hidden = false;
    setStatus("扫描中…", false);
    setProgress(3, "准备", forceFull ? "正在重新汇总…" : "正在载入今日结果…");
    try {
      if (!forceFull) {
        var cached = await fetchServerResult();
        if (scanAbort) { setStatus("已停止", false); return; }
        if (cached && cached.ok && !cached.running) {
          applyServerPayload(cached, true);
          setProgress(100, "完成", "已载入今日结果");
          return;
        }
      }
      await startServerScan(!!forceFull);
      setProgress(5, "扫描中", "正在筛选，数字会随进度更新…");
      await pollServerScan();
      if (scanAbort) { setStatus("已停止", false); return; }
      var out = await fetchServerResult();
      if (out && out.ok && !out.running) {
        applyServerPayload(out, !!out.cached);
        setProgress(100, "完成", "扫描完成");
      } else if (out && out.running) {
        setStatus("仍在扫描中，请稍后再试", false);
      } else {
        showEmpty("暂无入选标的");
        setStatus("扫描完成，暂无入选", false);
      }
    } catch (e) {
      setStatus(e.message || "扫描失败", true);
      setProgress(0, "失败", e.message || "");
    } finally {
      scanning = false;
      scanAbort = false;
      $("radar-scan").disabled = false;
      if ($("radar-scan-full")) $("radar-scan-full").disabled = false;
      $("radar-stop").hidden = true;
      $("radar-progress").hidden = true;
    }
  }

  function stopScan() {
    if (scanning) scanAbort = true;
  }

  async function boot() {
    if (!token()) { $("radar-guest").hidden = false; return; }
    try {
      var res = await fetch(apiUrl("/api/me"), { headers: authHeaders(), cache: "no-store" });
      if (res.status === 401) { $("radar-guest").hidden = false; return; }
      if (!res.ok) throw new Error("HTTP " + res.status);
      var me = await res.json();
      var plan = String((me && me.quota && me.quota.plan) || "free").toLowerCase();
      if (!plan || plan === "free" || plan === "anon") { $("radar-vipgate").hidden = false; return; }
    } catch (e) {
      $("radar-guest").hidden = false;
      return;
    }
    $("radar-main").hidden = false;
    bindRadarConfirm();
    renderChips();
    renderHistory();
    setStatus("就绪 · 打开即可看今日结果", false);
    $("radar-scan").addEventListener("click", function () { runScan(false); });
    if ($("radar-scan-full")) {
      $("radar-scan-full").addEventListener("click", function () {
        showRadarConfirm({
          title: "确认完整重扫",
          message: "将重新汇总近 30 日热门涨停股，并更新今日结果。",
          notes: [
            "预计需要 2～4 分钟，请耐心等待",
            "请勿连续多次点击",
            "日常查看结果，点「开始扫描」即可"
          ],
          okText: "继续重扫",
          cancelText: "先不扫"
        }).then(function (ok) {
          if (ok) runScan(true);
        });
      });
    }
    $("radar-stop").addEventListener("click", stopScan);
    $("radar-signal").addEventListener("change", function () { tryLoadServerResult(); });
    $("radar-strict").addEventListener("change", function () { tryLoadServerResult(); });
    if ($("radar-price")) $("radar-price").addEventListener("change", function () { tryLoadServerResult(); });
    if ($("radar-clear")) $("radar-clear").addEventListener("click", function () {
      showEmpty("已清空展示");
      renderFilterStats({});
      setStatus("就绪", false);
    });
    if ($("radar-history-clear")) $("radar-history-clear").addEventListener("click", function () {
      showRadarConfirm({
        title: "清空扫描记录",
        message: "确定清空本机保存的全部扫描记录吗？此操作不可恢复。",
        okText: "清空",
        cancelText: "保留"
      }).then(function (ok) {
        if (!ok) return;
        try { localStorage.removeItem(HISTORY_KEY); } catch (e) {}
        renderHistory();
      });
    });
    tryLoadServerResult().then(function (ok) {
      if (ok) return;
      var hist = loadHistory();
      if (hist.length && hist[0].items && hist[0].items.length) {
        renderFilterStats(hist[0].filterStats);
        renderResults(hist[0].items);
        setStatus("本机记录 · " + fmtDateTime(hist[0].time), false);
      }
    });
  }

  global.AI24X_Radar = { boot: boot, runScan: runScan, stopScan: stopScan };
})(window);
