const { chromium } = require('C:/Users/Admin/node_modules/playwright-core');
(async () => {
  const out = {};
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on('pageerror', e => (out.pageErrors = out.pageErrors || []).push(String(e).slice(0, 200)));
  await page.goto('http://127.0.0.1:18001/daily/index.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  out.css = await page.evaluate(() => Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href));
  out.cardPad = await page.evaluate(() => { const c = document.querySelector('.page-main .card'); const cs = getComputedStyle(c); return { pt: cs.paddingTop, pl: cs.paddingLeft, radius: cs.borderRadius }; });
  out.h2Main = await page.evaluate(() => { const el = document.querySelector('#report h2.h2-main'); return el ? el.textContent.trim() : null; });
  await page.screenshot({ path: 'E:/AI24X/ai24x-website/ai24x01/p/a1/tmp_card/daily_desktop2.png', fullPage: false });
  await browser.close();
  console.log(JSON.stringify(out));
})();
