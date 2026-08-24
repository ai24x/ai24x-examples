// QA 2026-08-24：token-admin 订单用户标注 + 后台中文化（本地 8000）
// 前置：core(8000) 已重启加载 token_pay_service 新代码；iamlei888 本地可登
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const BASE = 'http://127.0.0.1:8000';
const KEY = 'iamlei888';
const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto(BASE + '/token-admin.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#gate.on', { timeout: 5000 });
  await page.fill('#apiBase', BASE);
  await page.fill('#ikey', KEY);
  await page.click('#btnEnter');
  await page.waitForSelector('#app.on', { timeout: 8000 });
  log('本地 iamlei888 进入后台', true, 'app.on');

  // 首页待履约/最近已支付用户列（默认面板即 p-dash）
  await page.waitForSelector('#p-dash.active', { timeout: 5000 });
  await page.waitForFunction(() => {
    const el = document.getElementById('dashPendingBody');
    return el && el.querySelectorAll('tr').length >= 1;
  }, { timeout: 8000 });
  const dashPendingUser = await page.$$eval('#dashPendingBody tr td:nth-child(2)', (els) => els.map((e) => e.textContent.trim()));
  log('首页待履约用户列', dashPendingUser.some((t) => /@|1[0-9]{10}|#[0-9]+/.test(t)), dashPendingUser.join('|').slice(0, 80));
  const dashPaidUser = await page.$$eval('#dashPaidBody tr td:nth-child(2)', (els) => els.map((e) => e.textContent.trim()));
  log('首页最近已支付用户列', dashPaidUser.length === 0 || dashPaidUser.some((t) => /@|1[0-9]{10}|#[0-9]+/.test(t)), dashPaidUser.join('|').slice(0, 80));

  // 支付与订单 -> Token 订单
  await page.click('.nav-l1[data-group-btn="g-pay"]');
  await page.waitForSelector('#p-orders.active', { timeout: 5000 });
  await page.waitForFunction(() => {
    const el = document.getElementById('ordBody');
    return el && el.querySelectorAll('tr').length >= 1;
  }, { timeout: 8000 });

  // 筛选下拉中文化
  const stOpts = await page.$$eval('#ordStatus option', (els) => els.map((e) => e.textContent.trim()));
  log('订单状态下拉中文', stOpts.includes('待支付') && stOpts.includes('已支付') && stOpts.includes('失败'), stOpts.join('/'));
  const chOpts = await page.$$eval('#ordChannel option', (els) => els.map((e) => e.textContent.trim()));
  log('订单通道下拉中文', chOpts.includes('微信') && chOpts.includes('支付宝') && chOpts.includes('PayPal') && chOpts.includes('模拟'), chOpts.join('/'));

  // 订单行用户列显示邮箱/手机号
  const userCellText = await page.$eval('#ordBody tr td:nth-child(2)', (el) => el.textContent);
  log('订单用户列含邮箱或手机号', /@|1[0-9]{10}|#[0-9]+/.test(userCellText), userCellText.trim());

  // 状态 pill 中文化
  const pillText = await page.$$eval('#ordBody .pill', (els) => els.map((e) => e.textContent.trim()));
  log('订单状态 pill 中文', pillText.every((t) => !/^(paid|pending|failed)$/.test(t)) && pillText.length > 0, pillText.join('/'));

  // Markets 总览最近订单用户列（#uid · plan）
  await page.click('.nav-l1[data-group-btn="g-prod"]');
  await page.waitForSelector('#p-prod-summary.active', { timeout: 5000 });
  await page.waitForFunction(() => {
    const el = document.getElementById('mkRecentBody');
    return el && el.querySelectorAll('tr').length >= 1;
  }, { timeout: 8000 });
  const mkRecentUser = await page.$$eval('#mkRecentBody tr td:nth-child(2)', (els) => els.map((e) => e.textContent.trim()));
  log('Markets 最近订单用户列', mkRecentUser.some((t) => /^#[a-zA-Z0-9_]+/.test(t)), mkRecentUser.join('|').slice(0, 80));

  // CSV 导出含 user_email/user_phone 列
  const csvResp = await page.evaluate(async (opts) => {
    const base = opts.base, key = opts.key;
    const r = await fetch(base + '/v1/admin/token/orders/export.csv?limit=3', {
      headers: { 'X-Admin-Key': key, 'X-SMS-Internal-Key': key },
    });
    return { status: r.status, text: await r.text() };
  }, { base: BASE, key: KEY });
  log('CSV 导出 200', csvResp.status === 200, 'status=' + csvResp.status);
  const headLine = String(csvResp.text).split(/\r?\n/)[0] || '';
  log('CSV 表头含 user_email/user_phone', headLine.includes('user_email') && headLine.includes('user_phone'), headLine);

  log('无页面 JS 报错', errors.length === 0, errors.slice(0, 3).join(' ; '));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log('TOTAL ' + results.length + ' PASS ' + (results.length - failed) + ' FAIL ' + failed);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error('QA ERROR: ' + (e && e.stack ? e.stack : e));
  process.exit(2);
});
