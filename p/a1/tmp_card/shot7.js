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
      function r(el) { if (!el) return null; const b = el.getBoundingClientRect(); return { x: Math.round(b.x), w: Math.round(b.width) }; }
      const nav = document.querySelector('.nav-main');
      const links = Array.from(nav.querySelectorAll('a')).map(a => ({ t: a.textContent, x: Math.round(a.getBoundingClientRect().x), w: Math.round(a.getBoundingClientRect().width), active: a.className }));
      const inner = document.querySelector('.header-inner');
      const brand = document.querySelector('.brand');
      const actions = document.querySelector('.header-actions');
      return {
        inner: r(inner), nav: r(nav), brand: r(brand), actions: r(actions),
        links,
        navGap: getComputedStyle(nav).gap, navPad: getComputedStyle(nav).padding,
        navDisplay: getComputedStyle(nav).display,
        gridCols: getComputedStyle(inner).gridTemplateColumns
      };
    });
  }
  await browser.close();
  console.log(JSON.stringify(out, null, 1));
})();
