const { chromium } = require('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const errors = [];
  // ---- A: 无登录 brief 模式 ----
  const ctxA = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const pa = await ctxA.newPage();
  pa.on('pageerror', e => errors.push('A PAGEERROR: ' + e.message));
  pa.on('console', m => { if (m.type() === 'error') errors.push('A CONSOLE: ' + m.text()); });
  await pa.goto('http://127.0.0.1:18001/daily/?brief=1', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pa.waitForTimeout(6000);
  const a = await pa.evaluate(() => {
    const bar = document.getElementById('btn-bar');
    const bb = document.getElementById('brief-bar');
    const chips = Array.from(document.querySelectorAll('.brief-date')).map(c => c.textContent.trim());
    const active = (document.querySelector('.brief-date.active') || {}).textContent || '';
    const report = document.getElementById('report').textContent.trim().slice(0, 120);
    return {
      title: document.title,
      barDisplay: bar ? getComputedStyle(bar).display : 'missing',
      briefHidden: bb ? bb.hidden : 'missing',
      chips,
      active,
      reportHead: report
    };
  });
  console.log('A(brief anon):', JSON.stringify(a, null, 1));
  // click 2nd chip
  if (a.chips.length >= 2) {
    await pa.click('.brief-date:nth-child(2)');
    await pa.waitForTimeout(2500);
    const a2 = await pa.evaluate(() => {
      const active = (document.querySelector('.brief-date.active') || {}).textContent || '';
      const r = document.getElementById('report').textContent.trim().slice(0, 60);
      return { active, reportHead: r };
    });
    console.log('A click2nd:', JSON.stringify(a2));
  }
  await ctxA.close();
  // ---- B: VIP 工具台模式 ----
  const lr = await fetch('http://127.0.0.1:18011/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone: '18968701913', password: 'iamlei' }) });
  const lj = await lr.json();
  const token = lj.token || '';
  const ctxB = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctxB.addInitScript(t => { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, token);
  const pb = await ctxB.newPage();
  pb.on('pageerror', e => errors.push('B PAGEERROR: ' + e.message));
  await pb.goto('http://127.0.0.1:18001/daily/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pb.waitForTimeout(6000);
  const b = await pb.evaluate(() => {
    const run = document.getElementById('btn-run');
    const brief = document.getElementById('btn-brief');
    const hist = Array.from(document.querySelectorAll('.hist-item')).map(h => h.textContent.trim().slice(0, 30));
    return {
      runVisible: run ? getComputedStyle(run).display !== 'none' : 'missing',
      briefVisible: brief ? getComputedStyle(brief).display !== 'none' : 'missing',
      briefBarHidden: document.getElementById('brief-bar') ? document.getElementById('brief-bar').hidden : 'missing',
      reportHead: document.getElementById('report').textContent.trim().slice(0, 80),
      histCount: hist.length,
      histSample: hist[0] || ''
    };
  });
  console.log('B(vip tool):', JSON.stringify(b, null, 1));
  await ctxB.close();
  // ---- C: 375px 手机 brief ----
  const ctxC = await browser.newContext({ viewport: { width: 375, height: 667 } });
  const pc = await ctxC.newPage();
  pc.on('pageerror', e => errors.push('C PAGEERROR: ' + e.message));
  await pc.goto('http://127.0.0.1:18001/daily/?brief=1', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pc.waitForTimeout(6000);
  const c = await pc.evaluate(() => ({ sw: window.innerWidth, docW: document.documentElement.scrollWidth, bodyW: document.body.scrollWidth }));
  console.log('C(mobile 375):', JSON.stringify(c));
  await ctxC.close();
  await browser.close();
  console.log('ERRORS:', JSON.stringify(errors));
})().catch(e => { console.error('SMOKE FAIL:', e.message); process.exit(1); });