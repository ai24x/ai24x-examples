const { chromium } = require('C:/Users/Admin/node_modules/playwright-core');
(async () => {
  const out = {};
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  for (const pg of ['index.html', 'gd.html', 'daily/index.html', 'daily/view.html']) {
    await page.goto('http://127.0.0.1:18001/' + pg + '?i=CL2KDLGR', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    const info = await page.evaluate(() => {
      const wrap = document.querySelector('.page-main .wrap') || document.querySelector('main.wrap');
      const cs = wrap ? getComputedStyle(wrap) : null;
      const main = document.querySelector('.page-main');
      const mcs = main ? getComputedStyle(main) : null;
      const cssLinks = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href);
      return {
        wrapClass: wrap && wrap.className,
        wrapMaxW: cs && cs.maxWidth, wrapPadT: cs && cs.paddingTop,
        mainPadT: mcs && mcs.paddingTop, mainClass: main && main.className
      };
    });
    out[pg] = info;
  }
  // fetch actual base.css served
  const resp = await ctx.request.get('http://127.0.0.1:18001/css/base.css');
  const cssText = await resp.text();
  const idx = cssText.indexOf('.wrap {');
  out.baseCssWrap = cssText.slice(idx, idx + 120);
  await browser.close();
  console.log(JSON.stringify(out));
})();
