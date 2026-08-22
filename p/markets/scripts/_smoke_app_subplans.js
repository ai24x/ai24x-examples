// 冒烟：markets app.html 订阅面板动态套餐（本地 18012）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');
(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('http://127.0.0.1:18012/app.html#sub', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const week = await page.textContent('#btn-sub-week .plan-price');
  const month = await page.textContent('#btn-sub-month .plan-price');
  const year = await page.textContent('#btn-sub-year .plan-price');
  const visible = await page.$$eval('#sub .sub-plan', (els) => els.filter((e) => e.style.display !== 'none').length);
  console.log('prices: ' + week.trim() + ' | ' + month.trim() + ' | ' + year.trim() + ' | visible=' + visible);
  console.log('errors: ' + JSON.stringify(errors));
  await browser.close();
})();
