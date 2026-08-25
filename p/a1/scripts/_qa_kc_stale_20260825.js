const { chromium } = require('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const lr = await fetch('http://127.0.0.1:18011/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone: '18968701913', password: 'iamlei' }) });
  const lj = await lr.json();
  const token = lj.token || '';
  // 以接口返回的 asof/date 为基准（数据新鲜度由后端口径决定，不硬编码日期）
  const sr = await (await fetch('http://127.0.0.1:18011/api/bj/screener?market=kc', { headers: { Authorization: 'Bearer ' + token } })).json();
  const asof = sr.asof || sr.date || '';
  const scanDate = sr.date || '';
  const results = [];
  const errors = [];
  // ---- A: 桌面 gd.html 科创主线 ----
  const ctxA = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctxA.addInitScript(t => { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, token);
  const pa = await ctxA.newPage();
  pa.on('pageerror', e => errors.push('A PAGEERROR: ' + e.message));
  pa.on('console', m => { if (m.type() === 'error') errors.push('A CONSOLE: ' + m.text()); });
  await pa.goto('http://127.0.0.1:18001/gd.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pa.waitForTimeout(5000);
  // 切到科创主线 tab
  const clicked = await pa.evaluate(() => {
    const tabs = Array.from(document.querySelectorAll('[data-market], .bj-tab, .tabs button, button'));
    const kc = tabs.find(b => (b.getAttribute('data-market') || b.textContent || '').includes('kc') || b.textContent.includes('\u79d1\u521b\u4e3b\u7ebf'));
    if (kc) { kc.click(); return true; }
    return false;
  });
  await pa.waitForTimeout(5000);
  const a = await pa.evaluate(({ asof, scanDate }) => {
    const body = document.body.textContent || '';
    const hasData = body.includes('\u6570\u636e\u622a\u81f3 ' + asof + ' \u6536\u76d8');
    const hasTodayPick = body.includes('\u4eca\u65e5\u7cbe\u9009');
    const hasOldLabel = body.includes('\u4e0a\u4e00\u4ea4\u6613\u65e5\u7b5b\u9009') || body.includes('\u4e0a\u4e00\u4ea4\u6613\u65e5\uff08');
    const sec = Array.from(document.querySelectorAll('.bj-section')).map(x => x.textContent.trim().slice(0, 60));
    const note = Array.from(document.querySelectorAll('.notice.stale')).map(x => x.textContent.trim().slice(0, 90));
    return { clicked: 'clicked-kc', asof: asof, scanDate: scanDate, hasData, hasTodayPick, hasOldLabel, sections: sec, notes: note };
  }, { asof, scanDate });
  console.log('A(gd kc):', JSON.stringify(a, null, 1));
  results.push(['kc-data-label', a.hasData && a.hasTodayPick]);
  results.push(['kc-no-old-label', !a.hasOldLabel]);
  await ctxA.close();
  // ---- B: 手机 m/gd.html ----
  const ctxB = await browser.newContext({ viewport: { width: 375, height: 812 } });
  await ctxB.addInitScript(t => { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, token);
  const pb = await ctxB.newPage();
  pb.on('pageerror', e => errors.push('B PAGEERROR: ' + e.message));
  pb.on('console', m => { if (m.type() === 'error') errors.push('B CONSOLE: ' + m.text()); });
  await pb.goto('http://127.0.0.1:18001/m/gd.html?i=CL2KDLGR&market=kc', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pb.waitForTimeout(6000);
  const b = await pb.evaluate(({ asof }) => {
    const meta = (document.getElementById('meta') || {}).textContent || '';
    return {
      hasData: meta.includes('\u6570\u636e\u622a\u81f3 ' + asof),
      hasOld: meta.includes('\u4e0a\u4e00\u4ea4\u6613\u65e5'),
      docW: document.documentElement.scrollWidth,
      vw: document.documentElement.clientWidth
    };
  }, { asof });
  console.log('B(m/gd):', JSON.stringify(b, null, 1));
  results.push(['m-kc-data-label', b.hasData && !b.hasOld]);
  results.push(['m-no-overflow', b.docW <= b.vw]);
  await ctxB.close();
  console.log('RESULTS:', JSON.stringify(results));
  console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
  await browser.close();
  process.exit(results.every(r => r[1]) && errors.length === 0 ? 0 : 1);
})();
