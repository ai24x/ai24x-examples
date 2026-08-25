const API = 'http://127.0.0.1:18011';
(async () => {
  const lr = await fetch(API + '/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone: '18968701913', password: 'iamlei' }) });
  const token = (await lr.json()).token;
  const h = { Authorization: 'Bearer ' + token };
  const market = process.argv[2] || 'kc';
  const force = process.argv[3] !== 'no-force';
  const st = await (await fetch(API + '/api/bj/screener/start?market=' + market + (force ? '&force=1' : ''), { headers: h })).json();
  console.log('start:', JSON.stringify(st));
  // poll progress
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 5000));
    let pr;
    try { pr = await (await fetch(API + '/api/bj/screener/progress?market=' + market, { headers: h })).json(); } catch (e) { continue; }
    if (pr && pr.running === false) break;
    if (i % 6 === 0) console.log('progress:', JSON.stringify(pr).slice(0, 160));
  }
  const d = await (await fetch(API + '/api/bj/screener?market=' + market, { headers: h })).json();
  console.log('date:', d.date, 'asof:', d.asof, 'stale:', d.stale, 'stale_from:', d.stale_from, 'fine:', d.fine, 'scanned:', d.scanned);
  const picks = d.picks || [];
  picks.forEach(p => {
    const pp = p.patterns || {};
    console.log('PICK', p.rank, p.name, p.code, 'tier=' + p.tier, 'final=' + p.final,
      'ztWeek=' + (pp.ztWeek ? 1 : 0),
      'firstWeek=' + (pp.firstWeek ? 1 : 0),
      'firstBoardRight=' + (pp.firstBoardRight ? 1 : 0),
      'ztPullback=' + (pp.ztPullback ? 1 : 0),
      'pullback2=' + (pp.pullback2 ? 1 : 0),
      'limitQuality=' + (p.limitQuality || '-'),
      'tags=' + JSON.stringify((pp)))
      ;
  });
  const all = (d.runners || []).map(r => {
    const pp = r.patterns || {};
    return { name: r.name, code: r.code, ztWeek: !!pp.ztWeek, final: r.final };
  });
  const ztN = all.filter(x => x.ztWeek).length;
  console.log('runners total:', all.length, 'ztWeek runners:', ztN);
})();
