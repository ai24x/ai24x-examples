
(function(){
'use strict';
var TOKEN_KEY = "ai24x_a_token";
function token(){ try{ return localStorage.getItem(TOKEN_KEY) || ""; }catch(e){ return ""; } }
/* 本地 18001 静态服务无 /api 反代 → 指向本地后端 18011；生产同源 Nginx 反代保持相对路径 */
var API_BASE = (function(){
  try {
    var host = String(location.hostname || "");
    var port = String(location.port || "");
    if ((host === "127.0.0.1" || host === "localhost") && port === "18001") return "http://127.0.0.1:18011";
  } catch (e) {}
  return "";
})();
function api(path, qs){
  var url = API_BASE + path + (qs ? ("?" + qs) : "");
  var h = { "Content-Type": "application/json" };
  var t = token(); if (t) h["Authorization"] = "Bearer " + t;
  var ctrl = null;
  try { ctrl = new AbortController(); } catch (e) {}
  var opt = { headers: h };
  if (ctrl){ opt.signal = ctrl.signal; setTimeout(function(){ try{ ctrl.abort(); }catch(e){} }, 25000); }
  return fetch(url, opt).then(function(r){ return r.json().catch(function(){ return {}; }); });
}
function fmt(n){ return (n==null||isNaN(n)) ? "--" : Number(n).toFixed(2); }

var IDX_NAMES = { "1.000001":"上证指数", "0.399001":"深证成指", "1.000852":"中证1000", "0.899050":"北证50" };
var state = { secid: "1.000001", period: "day", name: "上证指数", favs: [], vis: 60, zoom: 1 };
(function(){
  try{
    var sp = new URLSearchParams(location.search);
    var s = String(sp.get('secid') || '').trim();
    var nm = String(sp.get('name') || '').trim();
    if (s){
      state.secid = s;
      if (nm) state.name = nm;
      var qnm = document.getElementById('q-nm');
      if (qnm) qnm.textContent = nm || s;
      var qi = document.getElementById('q');
      if (qi && nm) qi.value = nm;
    }
  }catch(e){}
})();
function favNormalize(list){
  return (list || []).map(function(f){
    return typeof f === "string"
      ? { secid: String(f), name: String(f) }
      : { secid: String(f.secid || ""), name: String(f.name || f.secid || "") };
  }).filter(function(f){ return !!f.secid; });
}
function favFind(secid){
  for (var i = 0; i < state.favs.length; i++){
    if (String(state.favs[i].secid) === String(secid)) return i;
  }
  return -1;
}
try{ state.favs = favNormalize(JSON.parse(localStorage.getItem("ai24x_m_favs") || "[]")); }catch(e){ state.favs = []; }
var sigCache = [];
var sigError = "";
var cacheRows = null, cacheSigs = [];

function codeToSecid(code){
  code = String(code).trim();
  if (/^\d{6}$/.test(code)) {
    if (code.startsWith("6") || code.startsWith("9") || code.startsWith("4") || code.startsWith("8")) return "1." + code;
    return "0." + code;
  }
  if (/^\d+\.\d{6}$/.test(code)) return code;
  return null;
}

/* ===== 搜索（名称/代码，走 /api/suggest） ===== */
function apiSuggest(kw){
  return api("/api/suggest", "q=" + encodeURIComponent(kw) + "&include_plates=1").then(function(json){
    var rows = (json && json.QuotationCodeTable && json.QuotationCodeTable.Data) || [];
    var out = [], seen = {};
    rows.forEach(function(r){
      var qid = String(r.QuoteID || "");
      var cl = String(r.Classify || "");
      if (!/^[01]\.\d{6}$/.test(qid)) return;
      if (cl !== "AStock" && cl !== "NEEQ" && cl !== "Index") return;
      if (seen[qid]) return; seen[qid] = 1;
      out.push({ qid: qid, name: String(r.Name || r.Code || qid), code: String(r.Code || "") });
    });
    return out.slice(0, 8);
  }).catch(function(){ return []; });
}
var qEl = document.getElementById("q");
var suggestEl = document.getElementById("suggest");
function hideSuggest(){ suggestEl.classList.remove("show"); suggestEl.innerHTML = ""; }
function showSuggest(list){
  if (!list.length){ hideSuggest(); return; }
  suggestEl.innerHTML = "";
  list.forEach(function(it){
    var d = document.createElement("div"); d.className = "sg";
    d.innerHTML = '<span class="nm">' + it.name + '</span><span class="cd">' + (it.code || it.qid) + '</span>';
    d.addEventListener("click", function(){ goto(it.qid, it.name); hideSuggest(); });
    suggestEl.appendChild(d);
  });
  suggestEl.classList.add("show");
}
var suggestTimer = null;
qEl.addEventListener("input", function(){
  var v = qEl.value.trim();
  clearTimeout(suggestTimer);
  if (!v){ hideSuggest(); return; }
  suggestTimer = setTimeout(function(){ apiSuggest(v).then(showSuggest); }, 300);
});
document.addEventListener("click", function(e){ if (!e.target.closest(".search")) hideSuggest(); });
function doSearch(){
  var v = qEl.value.trim();
  if (!v) return;
  var secid = codeToSecid(v);
  if (secid){ goto(secid, v); hideSuggest(); return; }
  apiSuggest(v).then(function(list){
    if (list.length){ var it = list[0]; goto(it.qid, it.name); hideSuggest(); }
    else { qEl.placeholder = "未找到，请输入6位代码或名称"; hideSuggest(); }
  });
}
document.getElementById("btn-go").addEventListener("click", doSearch);
qEl.addEventListener("keydown", function(e){ if (e.key === "Enter") doSearch(); });

/* ===== K线（带 period 参数；遍历兼容 day/qfqday/week/qfqweek/month/qfqmonth 全字段） ===== */
var COUNT = { day: 400, week: 560, month: 660 };
var KLINE_KEYS = ["qfqday","day","qfqweek","week","qfqmonth","month"];
function pickKlineRows(d){
  if (!d || !d.data) return null;
  var keys = Object.keys(d.data);
  for (var k=0;k<KLINE_KEYS.length;k++){
    for (var i=0;i<keys.length;i++){
      var v = d.data[keys[i]];
      if (!v || typeof v !== "object" || Array.isArray(v)) continue;
      var a = v[KLINE_KEYS[k]];
      if (Array.isArray(a) && a.length) return a;
    }
  }
  return null;
}
function loadKline(){
  var cnt = COUNT[state.period] || 400;
  return api("/api/kline", "secid=" + encodeURIComponent(state.secid) + "&period=" + encodeURIComponent(state.period) + "&count=" + cnt).then(function(d){
    if (!d || d.code !== 0) throw new Error((d && d.msg) || "no data");
    var rows = null;
    if (d && d.data) {
      var prefer = state.period === "week" ? ["week","qfqweek"]
                 : state.period === "month" ? ["month","qfqmonth"]
                 : ["day","qfqday"];
      var keys = Object.keys(d.data);
      for (var p=0;p<prefer.length && !rows;p++){
        for (var i=0;i<keys.length;i++){
          var v = d.data[keys[i]];
          if (!v || typeof v !== "object" || Array.isArray(v)) continue;
          var a = v[prefer[p]];
          if (Array.isArray(a) && a.length){ rows = a; break; }
        }
      }
      if (!rows) rows = pickKlineRows(d);
    }
    if (!rows || !rows.length) throw new Error("no data");
    return rows.map(function(r){ return { t:r[0], o:+r[1], c:+r[2], h:+r[3], l:+r[4], v:+r[5] }; });
  });
}

function sma(arr, p){
  var out = new Array(arr.length).fill(null); var s = 0;
  for (var i=0;i<arr.length;i++){ s += arr[i]; if (i>=p) s -= arr[i-p]; if (i>=p-1) out[i] = s/p; }
  return out;
}
function ema(arr, p){
  var out = new Array(arr.length).fill(null); var k = 2/(p+1); var prev = null;
  for (var i=0;i<arr.length;i++){ prev = (prev==null) ? arr[i] : arr[i]*k + prev*(1-k); out[i] = prev; }
  return out;
}
function macd(rows){
  var closes = rows.map(function(r){ return r.c; });
  var e12 = ema(closes,12), e26 = ema(closes,26);
  var dif = closes.map(function(_,i){ return (e12[i]!=null&&e26[i]!=null) ? e12[i]-e26[i] : null; });
  var dea = ema(dif.filter(function(v){return v!=null;}), 9);
  var deaFull = new Array(closes.length).fill(null); var j=0;
  for (var i=0;i<closes.length;i++){ if (dif[i]!=null){ deaFull[i]=dea[j]; j++; } }
  var hist = closes.map(function(_,i){ return (dif[i]!=null&&deaFull[i]!=null) ? (dif[i]-deaFull[i])*2 : null; });
  return { dif: dif, dea: deaFull, hist: hist };
}

/* ===== 报价/涨跌幅：由 K 线收盘价计算（原版同口径，不依赖需登录的快照接口） ===== */
function updateQuote(rows){
  if (!rows || rows.length < 2) return;
  var cur = rows[rows.length-1].c, prev = rows[rows.length-2].c;
  var chg = prev != null && !isNaN(prev) && prev !== 0 ? (cur - prev) / prev * 100 : null;
  document.getElementById("q-nm").textContent = state.name || "行情";
  document.getElementById("q-px").textContent = fmt(cur);
  var chgEl = document.getElementById("q-chg");
  if (chg != null){
    chgEl.textContent = (chg>=0?"+":"") + chg.toFixed(2) + "%";
    chgEl.style.color = chg>=0 ? "var(--up)" : "var(--down)";
    document.getElementById("q-px").style.color = chg>=0 ? "var(--up)" : "var(--down)";
  }
}

/* ===== 大盘环境条（上证/深证/中证/北证，可点击切换，涨跌幅由K线计算） ===== */
var ENV = [["1.000001","上证指数"],["0.399001","深证成指"],["0.399006","创业板指"],["1.000852","中证1000"],["0.899050","北证50"]];
function loadEnv(){
  var el = document.getElementById("env-strip"); if (!el) return;
  el.innerHTML = "";
  ENV.forEach(function(e){
    var chip = document.createElement("div"); chip.className = "env-chip";
    chip.dataset.secid = e[0]; chip.dataset.name = e[1];
    chip.innerHTML = '<span class="env-nm">' + e[1] + '</span>';
    if (e[0] === state.secid) chip.classList.add("active");
    chip.addEventListener("click", function(){
      if (state.secid === this.dataset.secid) return;
      goto(this.dataset.secid, this.dataset.name);
      var cs = el.querySelectorAll(".env-chip"); cs.forEach(function(c){ c.classList.toggle("active", c === chip); });
    });
    el.appendChild(chip);
  });
}

function normSig(text){
  text = String(text || "");
  text = text.replace(/卖([12])/g, "等$1").replace(/卖/g, "等");
  return text;
}
function classifySig(text){
  var t = normSig(text);
  if (t.indexOf("底") >= 0) return { label: "底", color: "#fbbf24" };
  if (t.indexOf("金") >= 0) return { label: "金", color: "#fbbf24" };
  if (t.indexOf("险") >= 0 || t.indexOf("破") >= 0 || t.indexOf("顶") >= 0) return { label: "险", color: "#60a5fa" };
  if (t.indexOf("等") >= 0) return { label: "等", color: "#00e68a" };
  if (t.indexOf("↗") >= 0) return { label: "↗", color: "#00e5ff" };
  if (t.indexOf("↘") >= 0) return { label: "↘", color: "#00e5ff" };
  if (t.indexOf("买") >= 0) return { label: "买", color: "#ff3d5c" };
  return { label: t || "信号", color: "#60a5fa" };
}
function loadSignals(){
  return api("/api/signals", "secid=" + encodeURIComponent(state.secid) + "&period=" + encodeURIComponent(state.period) + "&count=400").then(function(d){
    if (!d || d.code !== 0 || !(d.data && Array.isArray(d.data.markers))) {
      sigError = (d && d.msg) || "信号加载失败";
      sigCache = [];
      return [];
    }
    sigError = "";
    var arr = d.data.markers;
    var byDay = {};
    arr.forEach(function(m){
      var dt = m.time || m.date || "";
      if (!dt) return;
      var txt = normSig(m.text);
      if (!txt || !txt.replace(/​/g, "").trim()) return;
      var c = classifySig(txt);
      if (!byDay[dt]) byDay[dt] = [];
      byDay[dt].push({ label: c.label, color: m.color || c.color, note: txt, raw: txt, shape: m.shape || "circle", position: m.position || "belowBar" });
    });
    sigCache = Object.keys(byDay).map(function(dt){
      var list = byDay[dt];
      var seen = {}, labels = [], notes = [];
      list.forEach(function(s){
        if (seen[s.raw]) return;
        seen[s.raw] = 1;
        labels.push(s.label);
        notes.push(s.raw);
      });
      var first = list[0];
      var color = first.color;
      for (var k2 = 0; k2 < list.length; k2++){
        var cc = String(list[k2].color || "");
        if (/ff3d5c|f43f5e|fbbf24|ff1744|e11d48/i.test(cc)){ color = cc; break; }
      }
      return { date: dt, label: labels.join(" "), color: color, note: notes.join(" "), raw: notes.join(" "), shape: first.shape, position: first.position };
    });
    sigCache.sort(function(a, b){ return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
    return sigCache;
  }).catch(function(){ sigError = "信号加载失败"; sigCache = []; return []; });
}
function renderSigList(){
  var el = document.getElementById("sig-list");
  if (!sigCache.length){
    var dv = document.createElement("div"); dv.className = "empty";
    dv.textContent = sigError || "近期暂无信号";
    el.innerHTML = ""; el.appendChild(dv);
    return;
  }
  el.innerHTML = "";
  sigCache.slice(-20).reverse().forEach(function(s){
    var row = document.createElement("div"); row.className = "sig-row";
    row.innerHTML = '<span class="d">' + (s.date||"") + '</span><span class="s" style="color:' + (s.color||"var(--gold)") + '">' + s.label + '</span><span class="t">' + (s.note||"") + '</span>';
    el.appendChild(row);
  });
}

/* ===== 绘制（信号=小圆点+文字留间距；量能副图跟随缩放且底部大留白防遮挡） ===== */
function resize(cv){
  var dpr = window.devicePixelRatio || 1;
  var w = cv.clientWidth, h = cv.clientHeight;
  if (!w || !h) return null;
  cv.width = w * dpr; cv.height = h * dpr;
  var ctx = cv.getContext("2d"); ctx.setTransform(dpr,0,0,dpr,0,0);
  return { ctx: ctx, w: w, h: h };
}
function drawMarker(ctx, x, y, mk, dir, flip){
  var color = mk.color || "#60a5fa";
  ctx.fillStyle = color;
  ctx.strokeStyle = "rgba(11,18,32,.9)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI*2); ctx.fill(); ctx.stroke();
  var txt = String(mk.raw || mk.label || "").replace(/\s+/g, "").slice(0, 6).replace(/[·.。]+$/, "");
  if (txt){
    ctx.font = "bold 10px sans-serif"; ctx.textAlign = "center";
    var tw = ctx.measureText(txt).width;
    var ty = flip ? (dir > 0 ? y - 14 : y + 22) : (dir > 0 ? y + 22 : y - 14);
    var bx = x - tw / 2 - 3, by = ty - 7;
    ctx.fillStyle = "rgba(8,13,24,.8)";
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(bx, by, tw + 6, 15, 4); else ctx.rect(bx, by, tw + 6, 15);
    ctx.fill();
    ctx.fillStyle = color;
    ctx.fillText(txt, x, ty);
  }
}
function drawK(rows, sigs){
  var cv = document.getElementById("k-canvas");
  var R = resize(cv); if (!R) return;
  var ctx = R.ctx, W = R.w, H = R.h;
  ctx.clearRect(0,0,W,H);
  if (!rows || !rows.length) { ctx.fillStyle="#8aa0bf"; ctx.font="12px sans-serif"; ctx.fillText("暂无数据",12,20); return; }
  var closes = rows.map(function(r){ return r.c; });
  var ma1 = sma(closes,14), ma2 = sma(closes,28), ma3 = sma(closes,57);
  var vis = Math.max(20, Math.min(rows.length, state.vis));
  var sub = rows.slice(rows.length - vis);
  var lo = Infinity, hi = -Infinity;
  sub.forEach(function(r){ if(r.l<lo)lo=r.l; if(r.h>hi)hi=r.h; });
  var mid = (hi + lo) / 2, half = ((hi - lo) / 2) * state.zoom;
  hi = mid + half; lo = mid - half;
  var padL=8, padR=18, padT=14, padB=10;
  var plotW = W - padL - padR, plotH = H - padT - padB;
  var range = (hi - lo) || 1;
  function x(i){ return padL + (i/(vis-1))*plotW; }
  function y(p){ return padT + (hi-p)/range*plotH; }
  var cw = Math.max(1.5, plotW/vis*0.8);
  ctx.strokeStyle = "rgba(148,163,184,.12)"; ctx.lineWidth = 1;
  for (var g=1;g<5;g++){ var gy=padT+plotH*g/5; ctx.beginPath(); ctx.moveTo(0,gy); ctx.lineTo(W,gy); ctx.stroke(); }
  for (var i=0;i<vis;i++){
    var r = sub[i], xi = x(i);
    var up = r.c >= r.o;
    ctx.strokeStyle = up ? "#f03a52" : "#00b578"; ctx.fillStyle = up ? "#f03a52" : "#00b578";
    ctx.beginPath(); ctx.moveTo(xi, y(r.h)); ctx.lineTo(xi, y(r.l)); ctx.stroke();
    ctx.fillRect(xi-cw/2, Math.min(y(r.o),y(r.c)), cw, Math.max(1, Math.abs(y(r.o)-y(r.c))));
  }
  function line(arr, color){
    ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath(); var started = false;
    for (var i=0;i<vis;i++){
      var v = arr[rows.length - vis + i];
      if (v == null) continue;
      var px = x(i), py = y(v);
      if (!started){ ctx.moveTo(px,py); started = true; } else ctx.lineTo(px,py);
    }
    ctx.stroke();
  }
  line(ma1, "rgba(255,128,0,.55)"); line(ma2, "rgba(51,153,255,.55)"); line(ma3, "rgba(0,200,83,.55)");
  if (sigs && sigs.length) {
    var byDate = {}; sigs.forEach(function(s){ if (s.date) byDate[String(s.date)] = s; });
    var lastSigX = -1e9, flipSig = false;
    for (var j=0;j<vis;j++){
      var r = sub[j], s = byDate[String(r.t)];
      if (!s) continue;
      var xi2 = x(j);
      var dotY, dir;
      if (s.position === "aboveBar"){ dotY = Math.max(y(r.h) - 10, padT + 10); dir = -1; }
      else if (s.position === "inBar"){ dotY = (y(r.h)+y(r.l))/2; dir = 0; }
      else { dotY = Math.min(y(r.l) + 10, H - 24); dir = 1; }
      if (xi2 - lastSigX < 30){ flipSig = !flipSig; } else { flipSig = false; }
      drawMarker(ctx, xi2, dotY, s, dir, flipSig);
      lastSigX = xi2;
    }
  }
  if ((!sigs || !sigs.length) && sigError){
    ctx.fillStyle = "rgba(138,160,191,.95)"; ctx.font = "11px sans-serif"; ctx.textAlign = "right";
    var hint = sigError === "请先登录后再查询" ? "信号：登录后显示" : sigError;
    ctx.fillText(hint, W - padR, padT + 12);
    ctx.textAlign = "left";
  }
  document.getElementById("k-legend").textContent = "K线信号";
}
function drawMacdCross(ctx, x, y, isGold){
  ctx.fillStyle = isGold ? "#ff1744" : "#00e676";
  ctx.beginPath();
  if (isGold){ ctx.moveTo(x, y); ctx.lineTo(x-5, y+8); ctx.lineTo(x+5, y+8); }
  else { ctx.moveTo(x, y); ctx.lineTo(x-5, y-8); ctx.lineTo(x+5, y-8); }
  ctx.closePath(); ctx.fill();
}
function drawM(rows){
  var cv = document.getElementById("m-canvas");
  var R = resize(cv); if (!R) return;
  var ctx = R.ctx, W = R.w, H = R.h;
  ctx.clearRect(0,0,W,H);
  if (!rows || !rows.length) return;
  var m = macd(rows);
  var vis = Math.max(20, Math.min(rows.length, state.vis));
  var start = rows.length - vis;
  var vals = [];
  for (var i=start;i<rows.length;i++){ if (m.hist[i]!=null) vals.push(m.hist[i]); if (m.dif[i]!=null) vals.push(m.dif[i]); if (m.dea[i]!=null) vals.push(m.dea[i]); }
  var mx = 1; vals.forEach(function(v){ var a=Math.abs(v); if(a>mx)mx=a; });
  mx = mx * state.zoom; /* 纵向缩放跟随主图 */
  var padT=16, padB=18, padL=8, padR=18;
  var plotH = H-padT-padB, plotW = W-padL-padR;
  function x(i){ return padL + (i/(vis-1))*plotW; }
  function y(v){ return padT + (mx-v)/(2*mx)*plotH; }
  ctx.strokeStyle = "rgba(148,163,184,.3)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0,y(0)); ctx.lineTo(W,y(0)); ctx.stroke();
  var cw = Math.max(1.5, plotW/vis*0.8);
  var y0 = y(0);
  var firstRed = -1, firstGreen = -1;
  for (var i=0;i<vis;i++){
    var v = m.hist[start+i]; if (v==null) continue;
    if (v > 0 && firstRed < 0 && (i === 0 || (m.hist[start+i-1] != null && m.hist[start+i-1] <= 0))) firstRed = i;
    if (v < 0 && firstGreen < 0 && (i === 0 || (m.hist[start+i-1] != null && m.hist[start+i-1] >= 0))) firstGreen = i;
  }
  for (var i=0;i<vis;i++){
    var v = m.hist[start+i]; if (v==null) continue;
    var xi = x(i), yv = y(v);
    var hl = (i === firstRed || i === firstGreen);
    ctx.fillStyle = v>=0 ? (hl ? "rgba(239,68,68,.95)" : "rgba(239,68,68,.53)") : (hl ? "rgba(34,197,94,.95)" : "rgba(34,197,94,.53)");
    ctx.fillRect(xi-cw/2, Math.min(y0,yv), cw, Math.max(1, Math.abs(y0-yv)));
  }
  function lline(arr, color){
    ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath(); var started = false;
    for (var i=0;i<vis;i++){
      var v = arr[start+i]; if (v==null) continue;
      var px = x(i), py = y(v);
      if (!started){ ctx.moveTo(px,py); started = true; } else ctx.lineTo(px,py);
    }
    ctx.stroke();
  }
  lline(m.dif, "#e2e8f0"); lline(m.dea, "#f59e0b");
  for (var i=1;i<vis;i++){
    var d1 = m.dif[start+i-1], e1 = m.dea[start+i-1];
    var d2 = m.dif[start+i], e2 = m.dea[start+i];
    if (d1==null||e1==null||d2==null||e2==null) continue;
    var cy = y((d2+e2)/2);
    if (cy < padT + 8) cy = padT + 8;
    if (cy > H - padB - 8) cy = H - padB - 8;
    if (d1 < e1 && d2 >= e2){ drawMacdCross(ctx, x(i), cy, true); }
    else if (d1 > e1 && d2 <= e2){ drawMacdCross(ctx, x(i), cy, false); }
  }
  document.getElementById("m-legend").textContent = "量能";
}

/* ===== 技术指标快照（底部面板，登录后显示，与自选评分榜/查询页同口径） ===== */
var snapEl = document.getElementById("snap");
var snapCache = {};
var snapSeq = 0;
var snapBusy = {};
var snapWaiters = {};
function snapCls(sc){ return sc >= 70 ? "up" : sc >= 45 ? "mid" : "low"; }
function snapState(sc){ return sc >= 70 ? "偏强" : sc >= 45 ? "中性" : "偏弱"; }
function renderSnap(d){
  if (!snapEl) return;
  if (!d || d.ok === false){ _lastSnapData = null; snapEl.hidden = true; redraw(); return; }
  var sc = Number(d.score || 0);
  var cls = snapCls(sc);
  var scoreEl = document.getElementById("snap-score");
  scoreEl.textContent = sc ? sc.toFixed(0) : "--";
  scoreEl.className = "snap-score " + cls;
  var stateEl = document.getElementById("snap-state");
  stateEl.textContent = snapState(sc);
  stateEl.className = "snap-state " + cls;
  var mkt = d.market;
  var mktEl = document.getElementById("snap-mkt");
  if (mkt && mkt.name){
    var mpts = Number(mkt.pts || 0);
    var mcls = mpts >= 2 ? "up" : mpts <= -2 ? "down" : "flat";
    var mlbl = mpts >= 2 ? "顺风" : mpts <= -2 ? "逆风" : "中性";
    mktEl.innerHTML = "大盘 <b class='" + mcls + "'>" + mlbl + " " + mpts.toFixed(1) + "</b>";
  } else mktEl.innerHTML = "";
  var tagEl = document.getElementById("snap-tags"); tagEl.innerHTML = "";
  (d.tags || []).slice(0, 6).forEach(function(t){
    var sp = document.createElement("span");
    var amber = /动能偏热|波动收敛|量价配合/.test(t);
    var gray = /位置\d+%|超跌区|低位修复/.test(t);
    sp.className = "snap-tag" + (amber ? " amber" : gray ? " gray" : "");
    sp.textContent = t;
    tagEl.appendChild(sp);
  });
  var risks = (d.risks || []).slice(0, 3);
  document.getElementById("snap-risk").textContent = risks.length ? ("风险：" + risks.join(" / ")) : "";
  var warnEl = document.getElementById("snap-warn");
  var allRisks = d.risks || [];
  if (allRisks.length){ warnEl.textContent = "风险 " + allRisks.length; warnEl.hidden = false; }
  else { warnEl.textContent = ""; warnEl.hidden = true; }
  snapEl.hidden = false;
  _lastSnapData = d;
  redraw();
}
function loadSnap(done){
  function fin(){ if (typeof done === "function") done(); }
  function fire(){
    var arr = snapWaiters[secid] || [];
    snapWaiters[secid] = [];
    arr.forEach(function(w){ try{ w(); }catch(e){} });
  }
  var secid = String(state.secid || "");
  if (!secid){ if (snapEl) snapEl.hidden = true; fin(); return; }
  var hit = snapCache[secid];
  if (hit && Date.now() - hit.at < 300000){ renderSnap(hit.d); fin(); return; }
  if (snapBusy[secid]){
    if (typeof done === "function") (snapWaiters[secid] = snapWaiters[secid] || []).push(done);
    return;
  }
  snapBusy[secid] = true;
  var seq = ++snapSeq;
  api("/api/quote/snapshot", "secid=" + encodeURIComponent(secid) + "&name=" + encodeURIComponent(String(state.name || "")))
    .then(function(d){
      snapBusy[secid] = false;
      if (seq === snapSeq){
        if (d && d.ok) snapCache[secid] = { at: Date.now(), d: d };
        renderSnap(d);
      }
      fire();
    })
    .catch(function(){
      snapBusy[secid] = false;
      if (seq === snapSeq){ if (snapEl) snapEl.hidden = true; }
      fire();
    });
}
(function(){
  var head = document.getElementById("snap-head");
  if (!head) return;
  head.addEventListener("click", function(){
    var det = document.getElementById("snap-detail");
    var tg = document.getElementById("snap-toggle");
    det.hidden = !det.hidden;
    tg.textContent = det.hidden ? "详情 ▾" : "收起 ▲";
  });
})();
/* ===== 信号分享卡（竖版，手机端保存/长按分享） ===== */
var _lastSnapData = null;
function rr(ctx, x, y, w, h, r){
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
function drawMiniK(ctx, rows, x0, y0, x1, y1){
  var closes = rows.map(function(r){ return r.c; });
  var ma1 = sma(closes, 14), ma2 = sma(closes, 28), ma3 = sma(closes, 57);
  var vis = Math.max(20, Math.min(rows.length, state.vis));
  var sub = rows.slice(rows.length - vis);
  var lo = Infinity, hi = -Infinity;
  sub.forEach(function(r){ if (r.l < lo) lo = r.l; if (r.h > hi) hi = r.h; });
  var padT = 8, padB = 8;
  var plotH = (y1 - y0) - padT - padB, plotW = x1 - x0;
  var range = (hi - lo) || 1;
  var step = plotW / vis;
  function X(i){ return x0 + (i + 0.5) * step; }
  function Y(p){ return y0 + padT + (hi - p) / range * plotH; }
  ctx.strokeStyle = "rgba(148,163,184,.1)"; ctx.lineWidth = 1;
  for (var g = 1; g < 5; g++){ var gy = y0 + padT + plotH * g / 4; ctx.beginPath(); ctx.moveTo(x0, gy); ctx.lineTo(x1, gy); ctx.stroke(); }
  var cw = Math.max(1.2, plotW / vis * 0.72);
  for (var i = 0; i < vis; i++){
    var r = sub[i], xi = X(i);
    var up = r.c >= r.o;
    ctx.strokeStyle = up ? "rgba(240,58,82,.9)" : "rgba(0,181,120,.9)";
    ctx.fillStyle = ctx.strokeStyle;
    ctx.beginPath(); ctx.moveTo(xi, Y(r.h)); ctx.lineTo(xi, Y(r.l)); ctx.stroke();
    ctx.fillRect(xi - cw / 2, Math.min(Y(r.o), Y(r.c)), cw, Math.max(1, Math.abs(Y(r.o) - Y(r.c))));
  }
  function line(arr, color){
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath(); var st = false;
    for (var i = 0; i < vis; i++){
      var v = arr[rows.length - vis + i]; if (v == null) continue;
      var px = X(i), py = Y(v);
      if (!st){ ctx.moveTo(px, py); st = true; } else ctx.lineTo(px, py);
    }
    ctx.stroke();
  }
  line(ma1, "rgba(255,128,0,.55)"); line(ma2, "rgba(51,153,255,.55)"); line(ma3, "rgba(0,200,83,.55)");
  var sigsForCard = (cacheSigs && cacheSigs.length) ? cacheSigs : sigCache;
  if (sigsForCard && sigsForCard.length){
    var byDate = {};
    sigsForCard.forEach(function(s){ if (s && s.date) byDate[String(s.date)] = s; });
    var hits = [];
    var lastSigX2 = -1e9, flip2 = false;
    for (var i = 0; i < vis; i++){
      var sg = byDate[String(sub[i].t)];
      if (sg) hits.push({ i: i, sg: sg });
    }
    for (var h = 0; h < hits.length; h++){
      var sg = hits[h].sg, r = sub[hits[h].i], mx = X(hits[h].i);
      var dotY, dir;
      if (sg.position === "aboveBar"){ dotY = Math.max(Y(r.h) - 10, y0 + 8); dir = -1; }
      else if (sg.position === "inBar"){ dotY = (Y(r.h) + Y(r.l)) / 2; dir = 0; }
      else { dotY = Math.min(Y(r.l) + 10, y1 - 14); dir = 1; }
      var lbl = String(sg.raw || sg.note || sg.label || "").slice(0, 7).replace(/[·.。]+$/, "");
      if (lbl){
        ctx.font = "bold 17px sans-serif"; ctx.textAlign = "center";
        var tw = ctx.measureText(lbl).width;
        var nextX = (h + 1 < hits.length) ? X(hits[h + 1].i) : Infinity;
        var tx = Math.max(x0 + tw / 2, Math.min(mx, x1 - tw / 2));
        if (nextX - mx < step * 0.9 && h + 1 < hits.length){ /* 信号过密，只画点不画字 */ }
        else {
          if (h > 0 && mx - lastSigX2 < tw + 12){ flip2 = !flip2; } else { flip2 = false; }
          var ty = (dir < 0) ? (flip2 ? dotY + 24 : dotY - 16) : (flip2 ? dotY - 16 : dotY + 24);
          var bx2 = tx - tw / 2 - 4, by2 = ty - 9;
          ctx.fillStyle = "rgba(8,13,24,.8)";
          ctx.beginPath();
          if (ctx.roundRect) ctx.roundRect(bx2, by2, tw + 8, 19, 5); else ctx.rect(bx2, by2, tw + 8, 19);
          ctx.fill();
          ctx.fillStyle = sg.color || "#fbbf24";
          ctx.fillText(lbl, tx, ty);
        }
        lastSigX2 = mx;
      }
    }
  }
  ctx.strokeStyle = "rgba(148,163,184,.22)"; ctx.lineWidth = 1;
  ctx.strokeRect(x0, y0 + padT, plotW, plotH);
}
function drawMiniMacd(ctx, rows, x0, y0, x1, y1){
  var closes = rows.map(function(r){ return r.c; });
  function ema(arr, n){
    var out = [], k = 2 / (n + 1), prev = arr[0];
    for (var i = 0; i < arr.length; i++){
      prev = (i === 0) ? arr[0] : arr[i] * k + prev * (1 - k);
      out.push(prev);
    }
    return out;
  }
  var e12 = ema(closes, 12), e26 = ema(closes, 26);
  var dif = [], i;
  for (i = 0; i < closes.length; i++) dif.push(e12[i] - e26[i]);
  var dea = ema(dif, 9);
  var hist = [];
  for (i = 0; i < dif.length; i++) hist.push((dif[i] - dea[i]) * 2);
  var vis = Math.max(20, Math.min(rows.length, state.vis));
  var hs = hist.slice(hist.length - vis), ds = dif.slice(dif.length - vis), es = dea.slice(dea.length - vis);
  var lo = Infinity, hi = -Infinity;
  hs.forEach(function(v){ if (v < lo) lo = v; if (v > hi) hi = v; });
  ds.forEach(function(v){ if (v < lo) lo = v; if (v > hi) hi = v; });
  es.forEach(function(v){ if (v < lo) lo = v; if (v > hi) hi = v; });
  var rng = (hi - lo) || 1;
  var padT = 12, padB = 16, plotH = (y1 - y0) - padT - padB, plotW = x1 - x0;
  var step = plotW / vis;
  function X(i){ return x0 + (i + 0.5) * step; }
  function Y(v){ return y0 + padT + (hi - v) / rng * plotH; }
  var zero = Y(0);
  ctx.strokeStyle = "rgba(148,163,184,.14)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x0, zero); ctx.lineTo(x1, zero); ctx.stroke();
  var cw = Math.max(1.2, plotW / vis * 0.72);
  var firstRed = -1, firstGreen = -1;
  for (i = 0; i < vis; i++){
    var v = hs[i];
    if (v > 0 && firstRed < 0 && (i === 0 || hs[i - 1] <= 0)) firstRed = i;
    if (v < 0 && firstGreen < 0 && (i === 0 || hs[i - 1] >= 0)) firstGreen = i;
  }
  for (i = 0; i < vis; i++){
    var v = hs[i], xi = X(i);
    if (v == null) continue;
    var hl = (i === firstRed || i === firstGreen);
    ctx.fillStyle = v >= 0 ? (hl ? "rgba(239,68,68,.95)" : "rgba(239,68,68,.6)") : (hl ? "rgba(34,197,94,.95)" : "rgba(34,197,94,.6)");
    ctx.fillRect(xi - cw / 2, Math.min(zero, Y(v)), cw, Math.max(1, Math.abs(zero - Y(v))));
  }
  function line2(arr, color){
    ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.beginPath(); var st = false;
    for (i = 0; i < vis; i++){
      var v = arr[i]; if (v == null) continue;
      var px = X(i), py = Y(v);
      if (!st){ ctx.moveTo(px, py); st = true; } else ctx.lineTo(px, py);
    }
    ctx.stroke();
  }
  line2(ds, "#e2e8f0");
  line2(es, "#f59e0b");
  for (i = 1; i < vis; i++){
    var d1 = ds[i - 1], e1 = es[i - 1], d2 = ds[i], e2 = es[i];
    if (d1 == null || e1 == null || d2 == null || e2 == null) continue;
    var cy = Y((d2 + e2) / 2);
    if (cy < y0 + padT + 6) cy = y0 + padT + 6;
    if (cy > y1 - padB - 6) cy = y1 - padB - 6;
    if (d1 < e1 && d2 >= e2){
      ctx.fillStyle = "#ff1744";
      ctx.beginPath(); ctx.moveTo(X(i), cy); ctx.lineTo(X(i) - 5, cy + 8); ctx.lineTo(X(i) + 5, cy + 8); ctx.closePath(); ctx.fill();
    } else if (d1 > e1 && d2 <= e2){
      ctx.fillStyle = "#00e676";
      ctx.beginPath(); ctx.moveTo(X(i), cy); ctx.lineTo(X(i) - 5, cy - 8); ctx.lineTo(X(i) + 5, cy - 8); ctx.closePath(); ctx.fill();
    }
  }
  ctx.fillStyle = "rgba(138,160,191,.85)"; ctx.font = "19px sans-serif"; ctx.textAlign = "left";
  ctx.fillText("量能 · MACD", x0 + 2, y0 + 6);
  ctx.strokeStyle = "rgba(148,163,184,.22)"; ctx.lineWidth = 1;
  ctx.strokeRect(x0, y0 + padT, plotW, plotH);
}

var INVITE_CODE = "BWPX3Z8B";
function buildShareCard(done){
  if (!cacheRows || !cacheRows.length){ if (typeof done === "function") done(null); return; }
  var rows = cacheRows;
  var W = 750, H = 1240, pad = 36;
  var dpr = Math.max(2, Math.min(3, window.devicePixelRatio || 2));
  var cv = document.createElement("canvas");
  cv.width = W * dpr; cv.height = H * dpr;
  var ctx = cv.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.textBaseline = "middle";
  var UP = "#f03a52", DOWN = "#00b578", MUTED = "#8aa0bf", TEXT = "#e6edf7", GOLD = "#fbbf24";
  var bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, "#152238"); bg.addColorStop(1, "#0b1220");
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "#22314d"; ctx.lineWidth = 2;
  rr(ctx, 1, 1, W - 2, H - 2, 18); ctx.stroke();
  var cur = rows[rows.length - 1].c, prev = rows[rows.length - 2].c;
  var chg = (prev != null && !isNaN(prev) && prev !== 0) ? (cur - prev) / prev * 100 : null;
  var isUp = chg >= 0;
  var pc = (chg == null) ? MUTED : (isUp ? UP : DOWN);
  ctx.fillStyle = TEXT; ctx.font = "bold 46px sans-serif"; ctx.textAlign = "left";
  ctx.fillText(state.name || state.secid, pad, 62);
  ctx.fillStyle = MUTED; ctx.font = "26px sans-serif";
  ctx.fillText(String(state.secid).replace(/^\d+\./, ""), pad, 112);
  ctx.textAlign = "right";
  ctx.fillStyle = pc; ctx.font = "bold 56px sans-serif";
  ctx.fillText(cur.toFixed(2), W - pad, 62);
  ctx.font = "bold 30px sans-serif";
  ctx.fillText(chg == null ? "--" : (isUp ? "+" : "") + chg.toFixed(2) + "%", W - pad, 112);
  ctx.strokeStyle = "rgba(148,163,184,.16)"; ctx.beginPath(); ctx.moveTo(pad, 146); ctx.lineTo(W - pad, 146); ctx.stroke();
  drawMiniK(ctx, rows, pad, 168, W - pad, 408);
  drawMiniMacd(ctx, rows, pad, 426, W - pad, 558);
  var y = 586;
  var snap = _lastSnapData;
  ctx.fillStyle = MUTED; ctx.font = "22px sans-serif"; ctx.textAlign = "left";
  ctx.fillText("技术指标快照", pad, y); y += 44;
  if (snap && snap.ok){
    var sc = Number(snap.score || 0);
    var cls = sc >= 70 ? UP : sc >= 45 ? GOLD : MUTED;
    ctx.fillStyle = cls; ctx.font = "bold 62px sans-serif";
    ctx.fillText(sc ? sc.toFixed(0) : "--", pad, y);
    ctx.fillStyle = cls; ctx.font = "bold 30px sans-serif";
    ctx.fillText(sc >= 70 ? "偏强" : sc >= 45 ? "中性" : "偏弱", pad + 120, y + 6);
    y += 46;
    var mkt = snap.market;
    if (mkt && mkt.name){
      var mpts = Number(mkt.pts || 0);
      var mlbl = mpts >= 2 ? "顺风" : mpts <= -2 ? "逆风" : "中性";
      var mcl = mpts >= 2 ? UP : mpts <= -2 ? DOWN : MUTED;
      var mTags = (mkt.tags || []).map(function(t){ return String(t).replace(/^大盘/, ""); });
      ctx.fillStyle = MUTED; ctx.font = "24px sans-serif";
      ctx.fillText("大盘环境", pad, y);
      ctx.fillStyle = mcl; ctx.font = "bold 24px sans-serif";
      ctx.fillText(mlbl + " " + mpts.toFixed(1) + "  " + mTags.slice(0, 2).join(" / "), pad + 150, y);
      y += 42;
    }
    var tags = snap.tags || [];
    var tx = pad, ty = y + 14;
    tags.slice(0, 4).forEach(function(t){
      ctx.font = "20px sans-serif";
      var w = ctx.measureText(t).width + 22;
      if (tx + w > W - pad){ tx = pad; ty += 36; }
      rr(ctx, tx, ty - 16, w, 30, 15);
      ctx.fillStyle = "rgba(244,63,94,.12)"; ctx.fill();
      ctx.strokeStyle = "rgba(244,63,94,.35)"; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = "#f43f5e"; ctx.textAlign = "left";
      ctx.fillText(t, tx + 13, ty);
      tx += w + 8;
    });
    y = ty + 40;
    var risks = snap.risks || [];
    if (risks.length){
      ctx.fillStyle = "#f87171"; ctx.font = "24px sans-serif";
      ctx.fillText("风险：" + risks.slice(0, 3).join(" / ") + (risks.length > 3 ? " 等" : ""), pad, y);
      y += 38;
    }
  } else {
    ctx.fillStyle = MUTED; ctx.font = "24px sans-serif";
    ctx.fillText("技术指标快照暂不可用", pad, y);
    y += 38;
  }
  ctx.fillStyle = GOLD; ctx.font = "bold 26px sans-serif"; ctx.textAlign = "left";
  ctx.fillText("AI行情官 · 灯塔版", pad, 944);
  ctx.fillStyle = MUTED; ctx.font = "22px sans-serif";
  ctx.fillText("邀请码 " + INVITE_CODE, pad, 986);
  ctx.fillStyle = "rgba(138,160,191,.7)"; ctx.font = "19px sans-serif"; ctx.textAlign = "center";
  ctx.fillText("数据截至 " + String(rows[rows.length - 1].t) + " · 公开技术指标统计，仅供自主决策参考，不构成投资建议", W / 2, H - 32);
  ctx.textAlign = "left";
  var baseUrl = null;
  try { baseUrl = cv.toDataURL("image/png"); } catch (e) { baseUrl = null; }
  var qrSize = 132, qrX = W - pad - qrSize, qrY = 920;
  var qrLink = "https://a.ai24x.com/i/" + INVITE_CODE;
  var sid = String(state.secid || "");
  if (sid) qrLink += "?secid=" + encodeURIComponent(sid) + "&period=" + encodeURIComponent(state.period || "day");
  var qrUrl = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + encodeURIComponent(qrLink);
  var qrImg = new Image();
  qrImg.crossOrigin = "anonymous";
  qrImg.src = qrUrl;
  var settled = false;
  function finish(url){ if (!settled){ settled = true; if (typeof done === "function") done(url || baseUrl); } }
  var timer = setTimeout(function(){ finish(baseUrl); }, 2500);
  qrImg.onload = function(){
    if (settled) return; clearTimeout(timer);
    try {
      var cv2 = document.createElement("canvas");
      cv2.width = cv.width; cv2.height = cv.height;
      var c2 = cv2.getContext("2d");
      c2.drawImage(cv, 0, 0);
      c2.save();
      c2.setTransform(dpr, 0, 0, dpr, 0, 0);
      c2.fillStyle = "#ffffff";
      rr(c2, qrX - 6, qrY - 6, qrSize + 12, qrSize + 12, 12); c2.fill();
      c2.drawImage(qrImg, 0, 0, 300, 300, qrX, qrY, qrSize, qrSize);
      c2.restore();
      finish(cv2.toDataURL("image/png"));
    } catch (e) { finish(baseUrl); }
  };
  qrImg.onerror = function(){ if (!settled){ clearTimeout(timer); finish(baseUrl); } };
}
function openShare(){
  if (!cacheRows || !cacheRows.length) return;
  var build = function(){
    var img = document.getElementById("card-img");
    buildShareCard(function(dataUrl){
      if (!dataUrl) return;
      img.src = dataUrl;
      document.getElementById("sheet-share").classList.add("show");
    });
  };
  build();
  if (!(_lastSnapData && String(_lastSnapData.secid) === String(state.secid))){
    loadSnap(function(){
      if (_lastSnapData && String(_lastSnapData.secid) === String(state.secid)) build();
    });
  }
}
function dataUrlToBlob(dataUrl){
  try {
    var idx = dataUrl.indexOf(",");
    if (idx < 0) return null;
    var meta = dataUrl.slice(0, idx);
    var mm = /data:([^;]+)/.exec(meta);
    var mime = mm ? mm[1] : "image/png";
    var bin = atob(dataUrl.slice(idx + 1));
    var arr = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return new Blob([arr], { type: mime });
  } catch (e) { return null; }
}
function showSaveToast(msg){
  var t = document.createElement("div");
  t.style.cssText = "position:fixed;left:50%;bottom:14%;transform:translateX(-50%);max-width:82vw;padding:10px 16px;border-radius:10px;background:rgba(11,18,32,.94);color:#e6edf7;font-size:14px;line-height:1.5;z-index:99999;text-align:center;box-shadow:0 4px 14px rgba(0,0,0,.4)";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.style.transition = "opacity .3s"; t.style.opacity = "0"; }, 2400);
  setTimeout(function(){ if (t.parentNode) t.parentNode.removeChild(t); }, 2800);
}
function openShareCardPage(src){
  var filename = (state.name || state.secid) + "_sharecard.png";
  var mask = document.createElement("div");
  mask.id = "card-preview";
  mask.style.cssText = "position:fixed;inset:0;z-index:99998;background:rgba(4,8,16,.96);display:flex;flex-direction:column;align-items:center;justify-content:center;";
  var closeBtn = document.createElement("div");
  closeBtn.textContent = "× 关闭";
  closeBtn.style.cssText = "position:fixed;top:16px;right:18px;color:#8aa0bf;font-size:16px;padding:10px;z-index:2";
  var inner = document.createElement("div");
  inner.style.cssText = "display:flex;flex-direction:column;align-items:center;justify-content:center;width:92vw;max-height:88vh";
  var im = document.createElement("img");
  im.src = src;
  im.style.cssText = "max-width:92vw;max-height:74vh;border-radius:12px;background:#fff;box-shadow:0 6px 24px rgba(0,0,0,.5)";
  var tip = document.createElement("div");
  tip.style.cssText = "color:#8aa0bf;font-size:14px;line-height:1.7;text-align:center;margin-top:14px;padding:0 8px";
  tip.innerHTML = "长按图片 → 保存到相册 / 转发<br/>如菜单未弹出，可截图后裁剪使用";
  var dl = document.createElement("a");
  dl.textContent = "尝试直接下载";
  dl.href = src;
  dl.download = filename;
  dl.style.cssText = "display:inline-block;margin-top:12px;padding:9px 22px;border-radius:20px;background:#2563eb;color:#fff;font-size:15px;text-decoration:none";
  inner.appendChild(im); inner.appendChild(tip); inner.appendChild(dl);
  mask.appendChild(closeBtn); mask.appendChild(inner);
  function close(){ if (mask.parentNode) mask.parentNode.removeChild(mask); }
  closeBtn.addEventListener("click", close);
  mask.addEventListener("click", function(e){ if (e.target === mask) close(); });
  document.body.appendChild(mask);
  showSaveToast("长按图片可保存到相册或转发");
}
function saveCard(){
  var img = document.getElementById("card-img");
  if (!img || !img.src) return;
  var src = img.src;
  var filename = (state.name || state.secid) + "_sharecard.png";
  var blob = dataUrlToBlob(src);
  if (blob && navigator.share && navigator.canShare) {
    try {
      var file = new File([blob], filename, { type: "image/png" });
      if (navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], title: state.name || "AI行情官", text: "AI行情官 · " + (state.name || state.secid) + " 分享卡片" }).catch(function(){ openShareCardPage(src); });
        return;
      }
    } catch (e) {}
  }
  openShareCardPage(src);
}
function render(){
  var want = String(state.secid || "");
  loadKline().then(function(rows){
    if (String(state.secid || "") !== want) return;
    return loadSignals().then(function(sigs){
      if (String(state.secid || "") !== want) return;
      cacheRows = rows; cacheSigs = sigs;
      drawK(rows, sigs); drawM(rows); updateQuote(rows); loadSnap();
    });
  }).catch(function(err){
    if (String(state.secid || "") !== want) return;
    var cv = document.getElementById("k-canvas");
    var R = resize(cv); if (R){
      R.ctx.clearRect(0,0,R.w,R.h); R.ctx.fillStyle="#8aa0bf"; R.ctx.font="13px sans-serif";
      var msg = (err && err.message && String(err.message).indexOf("no data") < 0) ? String(err.message) : "数据加载失败，请稍后重试";
      if (msg.length > 22) msg = msg.slice(0, 21) + "…";
      R.ctx.fillText(msg, 12, 24);
    }
  });
}
function redraw(){ if (cacheRows) { drawK(cacheRows, cacheSigs); drawM(cacheRows); } else render(); }
function refresh(){ render(); }

function goto(secid, name){
  if (!secid) return;
  state.secid = secid; if (name) state.name = name;
  state.period = "day"; state.vis = 80; state.zoom = 1;
  document.querySelectorAll("#period-grp button").forEach(function(b){ b.classList.toggle("on", b.dataset.p === "day"); });
  document.getElementById("q-nm").textContent = name || secid;
  document.getElementById("q").value = name || secid;
  document.getElementById("q-px").textContent = "--";
  document.getElementById("q-chg").textContent = "--";
  document.getElementById("q-px").style.color = "";
  document.getElementById("q-chg").style.color = "";
  document.getElementById("snap").hidden = true;
  document.querySelectorAll(".env-chip").forEach(function(c){ c.classList.toggle("active", c.dataset.secid === secid); });
  refresh();
}
document.getElementById("period-grp").addEventListener("click", function(e){
  var b = e.target.closest("button"); if (!b) return;
  state.period = b.dataset.p;
  document.querySelectorAll("#period-grp button").forEach(function(x){ x.classList.toggle("on", x===b); });
  render();
});
document.getElementById("btn-fav").addEventListener("click", function(){
  var i = favFind(state.secid);
  if (i >= 0){ state.favs.splice(i,1); document.getElementById("btn-fav").textContent = "☆"; }
  else { state.favs.push({ secid: state.secid, name: state.name || state.secid }); document.getElementById("btn-fav").textContent = "★"; }
  try{ localStorage.setItem("ai24x_m_favs", JSON.stringify(state.favs)); }catch(e){}
  renderFavList();
});
document.getElementById("btn-home").addEventListener("click", function(){ location.href = "index.html"; });
document.getElementById("btn-signal").addEventListener("click", function(){
  renderSigList();
  document.getElementById("sheet-signal").classList.add("show");
});
document.getElementById("close-signal").addEventListener("click", function(){ document.getElementById("sheet-signal").classList.remove("show"); });
document.getElementById("sheet-signal").addEventListener("click", function(e){ if (e.target === this) this.classList.remove("show"); });
document.getElementById("btn-more").addEventListener("click", function(){ renderFavList(); document.getElementById("sheet-more").classList.add("show"); });
document.getElementById("close-more").addEventListener("click", function(){ document.getElementById("sheet-more").classList.remove("show"); });
document.getElementById("sheet-more").addEventListener("click", function(e){ if (e.target === this) this.classList.remove("show"); });
document.getElementById("btn-share").addEventListener("click", openShare);
document.getElementById("row-desktop").addEventListener("click", function(){ document.getElementById("sheet-more").classList.remove("show"); location.href = "../demo.html?force=1"; });
document.querySelectorAll(".nav-row").forEach(function(row){
  row.addEventListener("click", function(){
    var href = row.getAttribute("data-href");
    if (!href) return;
    document.getElementById("sheet-more").classList.remove("show");
    location.href = href;
  });
});
document.getElementById("close-share").addEventListener("click", function(){ document.getElementById("sheet-share").classList.remove("show"); });
document.getElementById("sheet-share").addEventListener("click", function(e){ if (e.target === this) this.classList.remove("show"); });
document.getElementById("btn-save-card").addEventListener("click", saveCard);
function renderFavList(){
  var el = document.getElementById("fav-list");
  if (!state.favs.length){ el.innerHTML = '<div class="empty">暂无自选，点击 ☆ 收藏</div>'; return; }
  el.innerHTML = "";
  state.favs.forEach(function(f){
    var row = document.createElement("div"); row.className = "sig-row";
    var nm = (f.name && f.name !== f.secid) ? f.name : (IDX_NAMES[f.secid] || f.secid);
    var s = document.createElement("span"); s.className = "s"; s.textContent = nm;
    var t = document.createElement("span"); t.className = "t"; t.textContent = String(f.secid).replace(/^\d+\./, "") + " · 点击查看";
    row.appendChild(s); row.appendChild(t);
    row.addEventListener("click", function(){ goto(f.secid, nm); document.getElementById("sheet-more").classList.remove("show"); });
    el.appendChild(row);
  });
}

/* ===== 双指缩放：横=K线根数(20~200)，纵=价格区间(0.5~3倍)，主图/副图联动 ===== */
(function(){
  var mainEl = document.querySelector(".chart-main");
  var touch = null;
  mainEl.addEventListener("touchstart", function(e){
    if (e.touches.length === 2){
      var t0 = e.touches[0], t1 = e.touches[1];
      touch = {
        dist: Math.hypot(t0.clientX - t1.clientX, t0.clientY - t1.clientY),
        vdist: Math.abs(t0.clientY - t1.clientY),
        vis: state.vis, zoom: state.zoom, axis: null
      };
      e.preventDefault();
    }
  }, { passive: false });
  mainEl.addEventListener("touchmove", function(e){
    if (touch && e.touches.length === 2){
      var t0 = e.touches[0], t1 = e.touches[1];
      var dx = Math.abs(t0.clientX - t1.clientX), dy = Math.abs(t0.clientY - t1.clientY);
      if (!touch.axis) touch.axis = (dy > dx * 1.2) ? "v" : "h";
      if (touch.axis === "h"){
        var d = Math.hypot(dx, dy);
        if (d > 0){
          var vis = Math.round(touch.vis * touch.dist / d);
          vis = Math.max(20, Math.min(200, vis));
          if (vis !== state.vis){ state.vis = vis; redraw(); }
        }
      } else {
        if (dy > 0){
          var zoom = Math.max(0.5, Math.min(3, touch.zoom * (touch.vdist || 1) / dy));
          if (Math.abs(zoom - state.zoom) > 0.02){ state.zoom = zoom; redraw(); }
        }
      }
      e.preventDefault();
    }
  }, { passive: false });
  function clearTouch(){ touch = null; }
  mainEl.addEventListener("touchend", clearTouch);
  mainEl.addEventListener("touchcancel", clearTouch);
})();

document.getElementById("btn-fav").textContent = (favFind(state.secid) >= 0) ? "★" : "☆";
document.addEventListener("visibilitychange", function(){ if (!document.hidden) refresh(); });
window.addEventListener("resize", function(){ redraw(); });
loadEnv();
refresh();
})();
