const { chromium } = require('C:/Users/Admin/node_modules/playwright-core');
(async () => {
  const out = {};
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  for (const pg of ['index.html', 'daily/index.html']) {
    await page.goto('http://127.0.0.1:18001/' + pg + '?i=CL2KDLGR', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    out[pg] = await page.evaluate(() => {
      const actions = document.querySelector('.header-actions');
      function r(el) { const b = el.getBoundingClientRect(); return { x: Math.round(b.x), w: Math.round(b.width), disp: getComputedStyle(el).display }; }
      const kids = Array.from(actions.children).map(c => ({ cls: c.className, ...r(c) }));
      const auth = document.getElementById('auth-actions');
      const authKids = auth ? Array.from(auth.children).map(c => ({ cls: c.className, txt: c.textContent.trim(), ...r(c) })) : null;
      return { actions: r(actions), kids, authKids };
    });
  }
  await browser.close();
  console.log(JSON.stringify(out, null, 1));
})();
