// QA 2026-08-17：Markets 周套餐 $9.9/周 —— 后端 PLANS + console Overview/Billing 统一开通 + 充值改名套餐 + markets app 订阅面板
const fs = require('fs');
const path = require('path');
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const ROOT = path.resolve(__dirname, '../../..');
const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

(async () => {
  // ===== 1) 静态断言 =====
  const billingSrc = fs.readFileSync(path.join(ROOT, 'p/markets/api/server/app/billing.py'), 'utf8');
  const hasWeeklyPlan = /"weekly":\s*\{\s*"usd":\s*9\.9,\s*"days":\s*7/.test(billingSrc);
  log('backend.plans_weekly', hasWeeklyPlan, '');

  const appSrc = fs.readFileSync(path.join(ROOT, 'p/markets/web/app.html'), 'utf8');
  log('app.btn_sub_week', appSrc.indexOf('btn-sub-week') >= 0, '');
  log('app.i18n_week', appSrc.indexOf("'sub.week': 'Upgrade · $9.9/week'") >= 0 && appSrc.indexOf("'sub.week': '升级 · $9.9/周'") >= 0, '');
  log('app.flashplan_weekly', /map\s*=\s*\{ weekly:\s*'week'/.test(appSrc), '');
  log('app.checkout_weekly_bind', appSrc.indexOf("doCheckout('weekly')") >= 0, '');

  const pricingSrc = fs.readFileSync(path.join(ROOT, 'p/markets/web/pricing.html'), 'utf8');
  log('pricing.weekly', pricingSrc.indexOf('$9.9') >= 0 && pricingSrc.indexOf('grid-4') >= 0, '');
  const indexSrc = fs.readFileSync(path.join(ROOT, 'p/markets/web/index.html'), 'utf8');
  log('index.weekly_mention', indexSrc.indexOf('$9.9/week') >= 0, '');

  const locales = fs.readFileSync(path.join(ROOT, 'web/config/locales.js'), 'utf8');
  log('locales.nav_billing_zh', locales.indexOf('"page.console.nav.billing": "套餐"') >= 0, '');
  log('locales.nav_billing_en', locales.indexOf('"page.console.nav.billing": "Plans"') >= 0, '');
  log('locales.week_zh_en', locales.indexOf('"page.console.marketsPro.week": "升级 · $9.9/周"') >= 0 && locales.indexOf('"page.console.marketsPro.week": "Upgrade · $9.9/week"') >= 0, '');

  const consoleSrc = fs.readFileSync(path.join(ROOT, 'web/console.html'), 'utf8');
  log('console.ov_buttons', consoleSrc.indexOf('btn-ov-week') >= 0 && consoleSrc.indexOf('btn-ov-month') >= 0 && consoleSrc.indexOf('btn-ov-year') >= 0, '');
  log('console.bill_week', consoleSrc.indexOf('btn-mk-week') >= 0, '');
  log('console.checkout_msg_class', consoleSrc.indexOf('mk-checkout-msg') >= 0, '');

  // 版本号全站统一 j，无 g/h/i 残留
  let oldG = 0, oldH = 0, oldI = 0, newJ = 0, htmlCount = 0;
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir)) {
      const p = path.join(dir, name);
      const st = fs.statSync(p);
      if (st.isDirectory()) { if (name !== 'node_modules' && name !== '.git') walk(p); continue; }
      if (!/\.html$/i.test(name)) continue;
      htmlCount++;
      const s = fs.readFileSync(p, 'utf8');
      if (/(?:locales|console|shell)\.js\?v=20260818g/.test(s)) oldG++;
      if (/(?:locales|console|shell)\.js\?v=20260818h/.test(s)) oldH++;
      if (/(?:locales|console|shell)\.js\?v=20260818i/.test(s)) oldI++;
      const m = s.match(/(?:locales|console|shell)\.js\?v=20260818j/g);
      if (m) newJ += m.length;
    }
  };
  walk(path.join(ROOT, 'web'));
  log('version.unified_j', oldG === 0 && oldH === 0 && oldI === 0 && newJ >= 70, 'pages=' + htmlCount + ' jRefs=' + newJ + ' i=' + oldI + ' g=' + oldG + ' h=' + oldH);

  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });

  // ===== 2) console（8000）：导航改名 + Overview/Billing 开通周套餐 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    await page.addInitScript(() => {
      try {
        localStorage.setItem('ai24x_auth_token', 'fake-token-weekly-qa');
        localStorage.setItem('ai24x_auth_user', '{"email":"qa@weekly.dev"}');
      } catch (e) {}
    });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.route('**/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, balance_usd: 5, user: { email: 'qa@weekly.dev' }, plans: [], rows: [] }) })
    );
    let postedPlan = null;
    await page.route('**/api/subscribe/checkout', (route) => {
      try { postedPlan = JSON.parse(route.request().postData() || '{}').plan || null; } catch (e) {}
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: -1, msg: 'qa_mock_no_pay' }) });
    });

    // 官网仅英文：导航统一「Plans」（zh 参数不再生效）
    await page.goto('http://127.0.0.1:8000/console.html?lang=zh#overview', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1600);
    const navZh = await page.evaluate(() => {
      const b = document.querySelector('.console-nav-item[data-console-panel="billing"]');
      return b ? b.textContent.trim() : '';
    });
    log('console.nav_plans_en', navZh === 'Plans', 'nav=' + navZh);

    // Overview 周套餐按钮 → POST weekly
    const ovHas = await page.evaluate(() => {
      return {
        week: !!document.getElementById('btn-ov-week'),
        month: !!document.getElementById('btn-ov-month'),
        year: !!document.getElementById('btn-ov-year'),
        msg: !!document.querySelector('.mk-checkout-msg'),
      };
    });
    log('console.overview_plan_buttons', ovHas.week && ovHas.month && ovHas.year && ovHas.msg, JSON.stringify(ovHas));
    postedPlan = null;
    await page.click('#btn-ov-week');
    await page.waitForTimeout(800);
    log('console.overview_week_checkout', postedPlan === 'weekly', 'plan=' + postedPlan);

    // Billing 面板周套餐按钮 → POST weekly
    await page.click('[data-console-panel="billing"]');
    await page.waitForTimeout(800);
    const billHas = await page.evaluate(() => {
      const panel = document.getElementById('panel-billing');
      const t = panel ? panel.textContent : '';
      return { week: !!document.getElementById('btn-mk-week'), zhNav: t.indexOf('套餐') >= 0 || t.indexOf('Plans') >= 0 };
    });
    log('console.billing_week_button', billHas.week, JSON.stringify(billHas));
    postedPlan = null;
    await page.click('#btn-mk-week');
    await page.waitForTimeout(800);
    log('console.billing_week_checkout', postedPlan === 'weekly', 'plan=' + postedPlan);
    log('console.no_js_errors', errors.length === 0, errors.slice(0, 3).join('; '));

    // en：导航 Plans
    await page.goto('http://127.0.0.1:8000/console.html?lang=en#overview', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const navEn = await page.evaluate(() => {
      const b = document.querySelector('.console-nav-item[data-console-panel="billing"]');
      return b ? b.textContent.trim() : '';
    });
    log('console.nav_en_plans', navEn === 'Plans', 'nav=' + navEn);
    await ctx.close();
  }

  // ===== 3) markets app（18012）：订阅面板周套餐 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await ctx.addCookies([
      { name: 'ai24x_auth_token', value: 'fake-token-app-qa', url: 'http://127.0.0.1:18012' },
      { name: 'ai24x_auth_user', value: encodeURIComponent(JSON.stringify({ email: 'qa@weekly.dev' })), url: 'http://127.0.0.1:18012' },
    ]);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    let postedPlan = null;
    await page.route('**/api/subscribe/checkout', (route) => {
      try { postedPlan = JSON.parse(route.request().postData() || '{}').plan || null; } catch (e) {}
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: -1, msg: 'qa_mock_no_pay' }) });
    });
    await page.goto('http://127.0.0.1:18012/app.html#sub', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    const has = await page.evaluate(() => ({
      week: !!document.getElementById('btn-sub-week'),
      month: !!document.getElementById('btn-sub-month'),
      year: !!document.getElementById('btn-sub-year'),
      label: (document.getElementById('btn-sub-week') || {}).textContent || '',
    }));
    log('app.sub_panel_week', has.week && has.month && has.year && has.label.indexOf('9.9') >= 0, JSON.stringify(has));
    postedPlan = null;
    await page.click('#btn-sub-week');
    await page.waitForTimeout(800);
    log('app.week_checkout', postedPlan === 'weekly', 'plan=' + postedPlan);
    log('app.no_js_errors', errors.length === 0, errors.slice(0, 3).join('; '));
    await ctx.close();
  }

  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== FAILED ' + failed + ' ===');
  process.exit(failed === 0 ? 0 : 1);
})().catch((e) => {
  console.error(e);
  process.exit(2);
});
