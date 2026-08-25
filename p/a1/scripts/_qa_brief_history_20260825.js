const { chromium } = require('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const results = [], errors = [];
  // A: 匿名 brief
  const ctxA = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const pa = await ctxA.newPage();
  pa.on('pageerror', e => errors.push('A PAGEERROR: ' + e.message));
  pa.on('console', m => { if (m.type() === 'error') errors.push('A CONSOLE: ' + m.text()); });
  await pa.goto('http://127.0.0.1:18001/daily/?brief=1', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pa.waitForTimeout(6000);
  const a = await pa.evaluate(() => {
    const box = document.getElementById('history');
    return {
      text: box ? box.textContent.trim().slice(0, 200) : 'missing',
      itemCount: box ? box.querySelectorAll('.hist-item').length : 0,
      loading: box ? box.textContent.includes('\u52a0\u8f7d\u4e2d') : false
    };
  });
  console.log('A(brief anon):', JSON.stringify(a));
  results.push(['anon-history-loaded', a.itemCount >= 10 && !a.loading]);
  await ctxA.close();
  // B: VIP brief
  const lr = await fetch('http://127.0.0.1:18011/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone: '18968701913', password: 'iamlei' }) });
  const lj = await lr.json();
  const token = lj.token || '';
  const ctxB = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctxB.addInitScript(t => { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, token);
  const pb = await ctxB.newPage();
  pb.on('pageerror', e => errors.push('B PAGEERROR: ' + e.message));
  pb.on('console', m => { if (m.type() === 'error') errors.push('B CONSOLE: ' + m.text()); });
  await pb.goto('http://127.0.0.1:18001/daily/?brief=1', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pb.waitForTimeout(6000);
  const b = await pb.evaluate(() => {
    const box = document.getElementById('history');
    return {
      itemCount: box ? box.querySelectorAll('.hist-item').length : 0,
      loading: box ? box.textContent.includes('\u52a0\u8f7d\u4e2d') : false,
      firstLink: box && box.querySelector('.hist-item a') ? box.querySelector('.hist-item a').getAttribute('href') : ''
    };
  });
  console.log('B(brief vip):', JSON.stringify(b));
  results.push(['vip-history-loaded', b.itemCount >= 10 && !b.loading && /view\.html\?date=/.test(b.firstLink)]);
  await ctxB.close();
  console.log('RESULTS:', JSON.stringify(results));
  console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
  await browser.close();
  process.exit(results.every(r => r[1]) && errors.length === 0 ? 0 : 1);
})();
