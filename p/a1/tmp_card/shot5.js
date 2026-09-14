const { chromium } = require('C:/Users/Admin/node_modules/playwright-core');
(async () => {
  const out = {};
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const pages = ['index.html', 'gd.html', 'daily/index.html'];
  for (const pg of pages) {
    await page.goto('http://127.0.0.1:18001/' + pg + '?i=CL2KDLGR', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.site-header', { timeout: 15000 });
    await page.waitForTimeout(1500);
    const m = await page.evaluate(() => {
      const h = document.querySelector('.site-header');
      const inner = document.querySelector('.header-inner');
      const main = document.querySelector('.page-main');
      const wrap = document.querySelector('.page-main .wrap') || document.querySelector('main.wrap');
      const nav = document.querySelector('.nav-main');
      function r(el) { if (!el) return null; const b = el.getBoundingClientRect(); return { x: Math.round(b.x), w: Math.round(b.width), y: Math.round(b.y), h: Math.round(b.height) }; }
      return {
        header: r(h), inner: r(inner), nav: r(nav),
        main: r(main), wrap: r(wrap),
        mainTop: main ? Math.round(main.getBoundingClientRect().top) : null,
        headerBottom: h ? Math.round(h.getBoundingClientRect().bottom) : null
      };
    });
    out[pg] = m;
    await page.screenshot({ path: 'E:/AI24X/ai24x-website/ai24x01/p/a1/tmp_card/top_' + pg.replace('/', '_') + '.png', clip: { x: 0, y: 0, width: 1440, height: 420 } });
  }
  await browser.close();
  console.log(JSON.stringify(out));
})();
