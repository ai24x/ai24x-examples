const { chromium } = require('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const lr = await fetch('http://127.0.0.1:18011/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone: '18968701913', password: 'iamlei' }) });
  const lj = await lr.json();
  const token = lj.token || '';
  const results = [], errors = [];
  // A: desktop
  const ctxA = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctxA.addInitScript(t => { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, token);
  const pa = await ctxA.newPage();
  pa.on('pageerror', e => errors.push('A PAGEERROR: ' + e.message));
  pa.on('console', m => { if (m.type() === 'error') errors.push('A CONSOLE: ' + m.text()); });
  await pa.goto('http://127.0.0.1:18001/gd.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pa.waitForTimeout(6000);
  const a = await pa.evaluate(() => {
    const body = document.body.textContent || '';
    return {
      starPicks: body.includes('⭐ 今日精选 · 上涨途中+股性活跃'),
      obsRank: body.includes('🔍 重点观察 · 板块排行'),
      noDup: (body.match(/今日精选/g) || []).length >= 1
    };
  });
  console.log('A(desktop):', JSON.stringify(a));
  results.push(['desktop-star-picks', a.starPicks]);
  results.push(['desktop-obs-rank', a.obsRank]);
  await ctxA.close();
  // B: mobile
  const ctxB = await browser.newContext({ viewport: { width: 375, height: 812 } });
  await ctxB.addInitScript(t => { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, token);
  const pb = await ctxB.newPage();
  pb.on('pageerror', e => errors.push('B PAGEERROR: ' + e.message));
  pb.on('console', m => { if (m.type() === 'error') errors.push('B CONSOLE: ' + m.text()); });
  await pb.goto('http://127.0.0.1:18001/m/gd.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pb.waitForTimeout(6000);
  const b = await pb.evaluate(() => {
    const body = document.body.textContent || '';
    return {
      starFilter: body.includes('⭐ 今日 AI 筛选') || body.includes('⭐ 昨日 AI 筛选'),
      obsRank: body.includes('🔍 板块排行'),
      docW: document.documentElement.scrollWidth,
      vw: document.documentElement.clientWidth
    };
  });
  console.log('B(mobile):', JSON.stringify(b));
  results.push(['mobile-star-filter', b.starFilter]);
  results.push(['mobile-obs-rank', b.obsRank]);
  results.push(['mobile-no-overflow', b.docW <= b.vw]);
  await ctxB.close();
  console.log('RESULTS:', JSON.stringify(results));
  console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
  await browser.close();
  process.exit(results.every(r => r[1]) && errors.length === 0 ? 0 : 1);
})();
