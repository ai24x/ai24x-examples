const { chromium } = require('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const errors = [];
  const results = [];
  // ---- A: gd.html 桌面版「今日简报」按钮 ----
  const ctxA = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const pa = await ctxA.newPage();
  pa.on('pageerror', e => errors.push('A PAGEERROR: ' + e.message));
  pa.on('console', m => { if (m.type() === 'error') errors.push('A CONSOLE: ' + m.text()); });
  await pa.goto('http://127.0.0.1:18001/gd.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pa.waitForTimeout(4000);
  const a = await pa.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('a.btn')).find(x => x.textContent.includes('\u4eca\u65e5\u7b80\u62a5'));
    const r = btn ? btn.getBoundingClientRect() : null;
    return {
      found: !!btn,
      href: btn ? btn.getAttribute('href') : '',
      visible: r ? r.width > 0 && r.height > 0 : false,
      rect: r ? { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } : null,
      bodyOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
    };
  });
  results.push(['gd-desktop-brief-btn', a.found && a.visible && a.href === '/daily/?brief=1']);
  console.log('A(gd desktop):', JSON.stringify(a, null, 1));
  await ctxA.close();
  // ---- B: m/gd.html 手机版 375px 入口 ----
  const ctxB = await browser.newContext({ viewport: { width: 375, height: 812 } });
  const pb = await ctxB.newPage();
  pb.on('pageerror', e => errors.push('B PAGEERROR: ' + e.message));
  pb.on('console', m => { if (m.type() === 'error') errors.push('B CONSOLE: ' + m.text()); });
  await pb.goto('http://127.0.0.1:18001/m/gd.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await pb.waitForTimeout(4000);
  const b = await pb.evaluate(() => {
    const link = Array.from(document.querySelectorAll('a')).find(x => x.textContent.includes('\u4eca\u65e5\u7b80\u62a5'));
    const r = link ? link.getBoundingClientRect() : null;
    const topbar = document.querySelector('.topbar');
    const tb = topbar ? topbar.getBoundingClientRect() : null;
    return {
      found: !!link,
      href: link ? link.getAttribute('href') : '',
      visible: r ? r.width > 0 && r.height > 0 : false,
      topbarH: tb ? Math.round(tb.height) : 0,
      bodyOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      docW: document.documentElement.scrollWidth,
      vw: document.documentElement.clientWidth
    };
  });
  results.push(['m-gd-brief-link', b.found && b.visible && b.href === '/daily/?brief=1' && !b.bodyOverflow]);
  console.log('B(m/gd 375px):', JSON.stringify(b, null, 1));
  await ctxB.close();
  // ---- 汇总 ----
  console.log('RESULTS:', JSON.stringify(results));
  console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
  await browser.close();
  process.exit(results.every(r => r[1]) && errors.length === 0 ? 0 : 1);
})();
