// QA 2026-08-22：运营后台「产品运营」面板 + 管理密钥门禁（本地 8000）
// 前置：core(8000) nssm 已配 ADMIN_API_KEY；密钥读 %TEMP%\ai24x_admin_qa.env
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');
const fs = require('fs');
const path = require('path');

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

function adminKey() {
  const p = path.join(process.env.TEMP || '.', 'ai24x_admin_qa.env');
  const txt = fs.readFileSync(p, 'utf-8');
  const m = txt.match(/^ADMIN_API_KEY=(.+)$/m);
  return m ? m[1].trim() : '';
}

(async () => {
  const key = adminKey();
  if (!key) { console.log('FAIL | missing ADMIN_API_KEY in QA env'); process.exit(1); }
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto('http://127.0.0.1:8000/token-admin.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#gate.on', { timeout: 5000 });
  log('gate visible', await page.isVisible('#gate'), 'login gate shown');
  const gateTitle = await page.textContent('#gate h1');
  log('gate brand = AI24X 运营后台', gateTitle.includes('AI24X 运营后台'), gateTitle.trim());

  await page.fill('#apiBase', 'http://127.0.0.1:8000');
  await page.fill('#ikey', key);
  await page.click('#btnEnter');
  await page.waitForSelector('#app.on', { timeout: 8000 });
  log('enter workbench with admin key', true, 'app.on');

  // 侧栏品牌 + 产品运营分组
  const brand = await page.textContent('.sidebar .brand');
  log('sidebar brand = AI24X 运营后台', brand.includes('AI24X 运营后台'), brand.trim());
  const prodBtn = await page.$('.nav-l1[data-group-btn="g-prod"]');
  log('nav group 产品运营 exists', !!prodBtn, prodBtn ? await prodBtn.textContent() : '');

  // 进入产品运营 -> Markets 总览
  await page.click('.nav-l1[data-group-btn="g-prod"]');
  await page.waitForSelector('#p-prod-summary.active', { timeout: 5000 });
  await page.waitForFunction(() => {
    const el = document.getElementById('mkStats');
    return el && el.children.length >= 6;
  }, { timeout: 8000 });
  const stats = await page.$$('#mkStats .stat');
  log('Markets 总览 6 张统计卡', stats.length >= 6, 'count=' + stats.length);
  const statText = await page.textContent('#mkStats');
  log('总览含 有效订阅/累计收入', /有效订阅/.test(statText) && /累计收入/.test(statText), statText.slice(0, 80));
  const planRows = await page.$$('#mkPlansBody tr');
  log('套餐分布行 >= 3', planRows.length >= 3, 'rows=' + planRows.length);
  const recentRows = await page.$$('#mkRecentBody tr');
  log('最近订单行 >= 1', recentRows.length >= 1, 'rows=' + recentRows.length);

  // Markets 订阅
  await page.click('#subnav .subnav-item[data-panel="p-prod-subs"]');
  await page.waitForFunction(() => {
    const el = document.getElementById('mkSubBody');
    return el && el.rows.length > 0;
  }, { timeout: 8000 });
  const subRows = await page.$$('#mkSubBody tr');
  log('Markets 订阅列表有数据', subRows.length > 0, 'rows=' + subRows.length);
  const subText = await page.textContent('#mkSubBody');
  log('订阅含 auth_ 用户', /auth_/.test(subText), subText.slice(0, 80));

  // 订阅筛选：plan=monthly
  await page.selectOption('#mkSubPlan', 'monthly');
  await page.click('#btnMkSubLoad');
  await page.waitForTimeout(800);
  const subFilterText = await page.textContent('#mkSubBody');
  log('订阅筛选 monthly 生效', /monthly/.test(subFilterText) && !/weekly|yearly/.test(subFilterText), subFilterText.slice(0, 80));

  // Markets 订单
  await page.click('#subnav .subnav-item[data-panel="p-prod-orders"]');
  await page.waitForFunction(() => {
    const el = document.getElementById('mkOrdBody');
    return el && el.rows.length > 0;
  }, { timeout: 8000 });
  const ordRows = await page.$$('#mkOrdBody tr');
  log('Markets 订单列表有数据', ordRows.length > 0, 'rows=' + ordRows.length);
  const ordMeta = await page.textContent('#mkOrdMeta');
  log('订单 meta 含 共 N 条', /共 \d+ 条/.test(ordMeta), ordMeta.trim());

  // Markets 套餐目录（可编辑保存）
  await page.click('#subnav .subnav-item[data-panel="p-prod-plans"]');
  await page.waitForFunction(() => {
    const el = document.getElementById('mkPlansCatalog');
    return el && el.rows.length >= 3;
  }, { timeout: 8000 });
  const catText = await page.textContent('#mkPlansCatalog');
  log('套餐目录 周/月/年', /weekly/.test(catText) && /monthly/.test(catText) && /yearly/.test(catText), catText.slice(0, 120));
  const mkInputs = await page.$$('#mkPlansCatalog .mk-usd');
  log('Markets 套餐可编辑（USD 输入框>=3）', mkInputs.length >= 3, 'count=' + mkInputs.length);
  page.on('dialog', (d) => d.accept());
  const monthlyRow = await page.$('#mkPlansCatalog tr[data-plan="monthly"]');
  const monthlyUsd = await monthlyRow.$('.mk-usd');
  await monthlyUsd.fill('25.5');
  await page.click('#btnMkPlansSave');
  await page.waitForFunction(() => {
    const row = document.querySelector('#mkPlansCatalog tr[data-plan="monthly"] .mk-usd');
    return row && row.value === '25.5';
  }, { timeout: 8000 });
  log('Markets 套餐保存生效（monthly=25.5）', true, 'monthly usd saved');
  const monthlyRow2 = await page.$('#mkPlansCatalog tr[data-plan="monthly"]');
  const monthlyUsd2 = await monthlyRow2.$('.mk-usd');
  await monthlyUsd2.fill('24.9');
  await page.click('#btnMkPlansSave');
  await page.waitForFunction(() => {
    const row = document.querySelector('#mkPlansCatalog tr[data-plan="monthly"] .mk-usd');
    return row && row.value === '24.9';
  }, { timeout: 8000 });
  log('Markets 套餐还原默认（monthly=24.9）', true, 'reverted');

  // Open BYOK 套餐（可编辑保存）
  await page.click('#subnav .subnav-item[data-panel="p-prod-open"]');
  await page.waitForFunction(() => {
    const el = document.getElementById('openPlansBody');
    return el && el.rows.length >= 2;
  }, { timeout: 8000 });
  const openRows = await page.$$('#openPlansBody tr');
  log('Open BYOK 套餐列表 >= 2', openRows.length >= 2, 'rows=' + openRows.length);
  const monthRow = await page.$('#openPlansBody tr[data-plan="byok_pro_month"]');
  const opUsd = await monthRow.$('.op-usd');
  await opUsd.fill('9.5');
  await page.click('#btnOpenPlansSave');
  await page.waitForFunction(() => {
    const row = document.querySelector('#openPlansBody tr[data-plan="byok_pro_month"] .op-usd');
    return row && row.value === '9.5';
  }, { timeout: 8000 });
  log('Open BYOK 套餐保存生效（byok_pro_month=9.5）', true, 'byok usd saved');
  const monthRow2 = await page.$('#openPlansBody tr[data-plan="byok_pro_month"]');
  const opUsd2 = await monthRow2.$('.op-usd');
  await opUsd2.fill('9.9');
  await page.click('#btnOpenPlansSave');
  await page.waitForFunction(() => {
    const row = document.querySelector('#openPlansBody tr[data-plan="byok_pro_month"] .op-usd');
    return row && row.value === '9.9';
  }, { timeout: 8000 });
  log('Open BYOK 套餐还原默认（byok_pro_month=9.9）', true, 'reverted');

  // Token 托管套餐：已从「支付与订单」移到「产品运营」，标题改名
  const tokenNav = await page.$('.nav-group[data-group="g-prod"] .nav-item[data-panel="p-plans"]');
  log('Token 托管套餐在 产品运营 分组', !!tokenNav, tokenNav ? (await tokenNav.textContent()).trim().slice(0, 30) : '');
  const payPlansNav = await page.$('.nav-group[data-group="g-pay"] .nav-item[data-panel="p-plans"]');
  log('支付与订单 不再有 价表管理', !payPlansNav, 'removed');
  await page.click('#subnav .subnav-item[data-panel="p-plans"]');
  await page.waitForFunction(() => {
    const h = document.querySelector('#p-plans h2');
    return h && h.textContent.indexOf('Token 托管套餐') >= 0;
  }, { timeout: 8000 });
  const plansTitle = await page.textContent('#p-plans h2');
  log('Token 托管套餐 面板标题', /Token 托管套餐/.test(plansTitle), plansTitle.trim());

  // 顶栏子菜单切换
  await page.click('#subnav .subnav-item[data-panel="p-prod-summary"]');
  await page.waitForSelector('#p-prod-summary.active', { timeout: 5000 });
  log('子菜单切回 Markets 总览', true);

  // 旧会话残留（短信内部密钥）→ 应回门禁并给友好提示，而不是裸「禁止访问」
  {
    const p2 = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await p2.goto('http://127.0.0.1:8000/token-admin.html', { waitUntil: 'domcontentloaded' });
    await p2.evaluate(() => {
      sessionStorage.setItem('ai24x_token_admin_v1', JSON.stringify({ base: 'http://127.0.0.1:8000', key: 'iamlei888' }));
      localStorage.setItem('ai24x_token_admin_nav_group', 'g-prod');
    });
    await p2.reload({ waitUntil: 'domcontentloaded' });
    await p2.waitForFunction(() => {
      var g = document.getElementById('gateMsg');
      return g && g.textContent.indexOf('会话已失效') >= 0;
    }, { timeout: 8000 });
    const gmText = await p2.textContent('#gateMsg');
    const gateCls = await p2.getAttribute('#gate', 'class');
    log('旧会话残留回门禁', /login-wrap\s+on/.test(gateCls || '') && /会话已失效/.test(gmText), gmText.slice(0, 60));
    log('旧会话提示不含裸禁止访问', gmText.indexOf('禁止访问') < 0, gmText.slice(0, 60));
    await p2.close();
  }

  // 手工填错密钥 → 门禁友好提示
  {
    const p3 = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await p3.goto('http://127.0.0.1:8000/token-admin.html', { waitUntil: 'domcontentloaded' });
    await p3.fill('#apiBase', 'http://127.0.0.1:8000');
    await p3.fill('#ikey', 'iamlei888');
    await p3.click('#btnEnter');
    await p3.waitForFunction(() => {
      var g = document.getElementById('gateMsg');
      return g && g.textContent.indexOf('密钥不正确或已失效') >= 0;
    }, { timeout: 8000 });
    const g3 = await p3.textContent('#gateMsg');
    log('错误密钥提示友好', /ADMIN_API_KEY/.test(g3), g3.slice(0, 60));
    await p3.close();
  }

  const realErrors = errors.filter((e) => !/favicon/i.test(e) && !/net::ERR/i.test(e));
  log('无 JS 报错', realErrors.length === 0, realErrors.slice(0, 3).join(' || '));

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log('---');
  console.log('TOTAL=' + results.length + ' PASS=' + (results.length - failed.length) + ' FAIL=' + failed.length);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error('QA crashed: ' + e); process.exit(2); });
