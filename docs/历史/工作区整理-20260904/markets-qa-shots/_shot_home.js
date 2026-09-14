// 截图 2026-08-16：www 深色主页 + markets 首页（琥珀灯塔）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });

  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const themeCls = await page.evaluate(() => document.body.className);
    console.log('www body class=' + themeCls + ' bg=' + bg);
    await page.screenshot({ path: 'p\\markets\\docs\\shot_www_dark_home.png', fullPage: true });
    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18012/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const gold = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--gold').trim());
    console.log('markets --gold=' + gold);
    await page.screenshot({ path: 'p\\markets\\docs\\shot_markets_home_amber.png', fullPage: true });
    await ctx.close();
  }

  await browser.close();
  console.log('done');
})();
