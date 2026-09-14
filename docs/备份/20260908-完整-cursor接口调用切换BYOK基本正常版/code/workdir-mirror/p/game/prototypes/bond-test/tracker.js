// P0-1 试玩埋点 tracker v1（2026-08-13，游戏官）
// 事件上报中台 POST /events（原型挂载于 game-core /playtest 同源）
(function () {
  'use strict';
  var SID_KEY = 'p01pt_sid';
  var Q_KEY = 'p01pt_q';
  var API = '/events';
  var uid = localStorage.getItem(SID_KEY);
  if (!uid) {
    uid = 'u' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    try { localStorage.setItem(SID_KEY, uid); } catch (e) {}
  }
  function extra() {
    var q = {};
    try {
      location.search.replace(/[?&]([^=&]+)=([^&]*)/g, function (m, k, v) { q[k] = decodeURIComponent(v); });
    } catch (e) {}
    return { sid: uid, src: q.from || q.src || 'direct', vw: window.innerWidth, vh: window.innerHeight };
  }
  function queue() { try { return JSON.parse(localStorage.getItem(Q_KEY) || '[]'); } catch (e) { return []; } }
  function flush() {
    var q = queue();
    if (!q.length) return;
    try { localStorage.setItem(Q_KEY, '[]'); } catch (e) {}
    var body = { events: q.map(function (it) { return { event: it.e, params: it.p }; }) };
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(API, new Blob([JSON.stringify(body)], { type: 'application/json' }));
      } else {
        fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), keepalive: true }).catch(function () {});
      }
    } catch (err) {}
  }
  function push(e, params) {
    var q = queue();
    try {
      q.push({ e: e, p: Object.assign({}, extra(), params || {}), t: Date.now() });
      localStorage.setItem(Q_KEY, JSON.stringify(q));
    } catch (err) { return; }
    if (q.length >= 5) flush();
  }
  window.__gcTrack = push;
  push('page_visit', {});
  var hid = false;
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden' && !hid) { hid = true; flush(); }
  });
  window.addEventListener('pagehide', flush);
  setTimeout(function () { if (queue().length) flush(); }, 3000);
})();