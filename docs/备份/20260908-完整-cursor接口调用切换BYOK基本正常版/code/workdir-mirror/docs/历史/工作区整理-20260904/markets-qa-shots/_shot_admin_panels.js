// 临时截图：运营后台「产品运营」面板（供老板本地过目）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1500, height: 940 } });
  await page.goto('http://127.0.0.1:8000/token-admin.html', { waitUntil: 'domcontentloaded' });
  await page.fill('#apiBase', 'http://127.0.0.1:8000');
  await page.fill('#ikey', 'local-dev-admin-1f9c3e7a5b2d8c4a6e0f');
  await page.click('#btnEnter');
  await page.waitForSelector('#app.on', { timeout: 8000 });
  await page.click('.nav-l1[data-group-btn="g-prod"]');
  await page.waitForFunction(() => {
    const el = document.getElementById('mkStats');
    return el && el.children.length >= 6;
  }, { timeout: 8000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: 'p/markets/scripts/_shot_admin_markets_overview.png' });
  await page.click('#subnav .subnav-item[data-panel="p-prod-orders"]');
  await page.waitForFunction(() => {
    const el = document.getElementById('mkOrdBody');
    return el && el.rows.length > 0;
  }, { timeout: 8000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: 'p/markets/scripts/_shot_admin_markets_orders.png' });
  await browser.close();
  console.log('screenshots saved');
})().catch((e) => { console.error(e); process.exit(1); });
