// QA 2026-08-23：console.html#billing Plans 栏目 BYOK 套餐（展示 + 跳 open.ai24x.com，不走站内下单）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    try {
      localStorage.setItem('ai24x_auth_token', 'fake-token-console-qa');
      localStorage.setItem('ai24x_auth_user', '{"email":"qa@console.dev"}');
    } catch (e) {}
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));

  // 兜底 mock 已登录接口；/v1/billing/products 用真实后端（含 byok）
  await page.route('**/v1/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  );
  await page.route('**/v1/billing/products', (route) => route.continue());
  await page.route('**/v1/billing/balance', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, balance_usd: 12.3, email: 'qa@console.dev', plan: 'free' }) })
  );
  await page.route('**/v1/billing/orders*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, rows: [] }) })
  );
  await page.route('**/v1/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, user: { email: 'qa@console.dev' } }) })
  );

  await page.goto('http://127.0.0.1:8000/console.html#billing?x=byok', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);

  const view = await page.evaluate(() => {
    const box = document.getElementById('productsList');
    if (!box) return null;
    const cards = Array.from(box.querySelectorAll('.product-card'));
    const byokCard = cards.find((c) => c.getAttribute('data-product') === 'byok');
    const byokRows = byokCard ? Array.from(byokCard.querySelectorAll('.product-plan-row')) : [];
    const byokActs = byokRows.map((r) => {
      const a = r.querySelector('.product-plan-act a');
      const btn = r.querySelector('.product-plan-act button');
      return {
        plan: r.getAttribute('data-plan'),
        text: r.querySelector('.product-plan-info strong') ? r.querySelector('.product-plan-info strong').textContent : '',
        extra: r.querySelector('.product-plan-info .sub') ? r.querySelector('.product-plan-info .sub').textContent : '',
        href: a ? a.getAttribute('href') : null,
        target: a ? a.getAttribute('target') : null,
        hasButton: !!btn,
        isRec: r.classList.contains('is-recommended'),
      };
    });
    const marketsRows = cards.find((c) => c.getAttribute('data-product') === 'markets')
      ? cards.find((c) => c.getAttribute('data-product') === 'markets').querySelectorAll('.product-plan-row').length
      : 0;
    const tokenRows = cards.find((c) => c.getAttribute('data-product') === 'token')
      ? cards.find((c) => c.getAttribute('data-product') === 'token').querySelectorAll('.product-plan-row').length
      : 0;
    return {
      cardProducts: cards.map((c) => c.getAttribute('data-product')),
      byokRows,
      byokActs,
      marketsRows,
      tokenRows,
    };
  });

  log('byok.three_products', !!view && view.cardProducts.join(',') === 'markets,token,byok', view ? view.cardProducts.join(',') : 'no box');
  log('byok.two_plan_rows', !!view && view.byokRows.length === 2, view ? 'rows=' + view.byokRows.length : '');
  log('byok.plan_names', !!view && view.byokActs[0] && view.byokActs[0].text === 'Pro Monthly' && view.byokActs[1] && view.byokActs[1].text === 'Pro Yearly',
    view ? (view.byokActs[0] || {}).text + ',' + (view.byokActs[1] || {}).text : '');
  log('byok.prices', !!view && view.byokActs[0] && view.byokActs[0].extra.indexOf('$9.9/month') >= 0 && view.byokActs[1] && view.byokActs[1].extra.indexOf('$99/year') >= 0,
    view ? (view.byokActs[0] || {}).extra + ' | ' + (view.byokActs[1] || {}).extra : '');
  log('byok.external_link', !!view && view.byokActs.every((x) => x.href === 'http://127.0.0.1:18080/pricing.html' && x.target === '_blank' && !x.hasButton),
    view ? JSON.stringify(view.byokActs.map((x) => x.href)) : '');
  log('byok.year_recommended', !!view && view.byokActs[1] && view.byokActs[1].isRec === true && view.byokActs[0].isRec === false, '');
  log('byok.markets_rows', !!view && view.marketsRows === 3, 'markets=' + (view ? view.marketsRows : ''));
  log('byok.token_rows', !!view && view.tokenRows === 6, 'token=' + (view ? view.tokenRows : ''));
  log('byok.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));

  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== ' + failed + ' FAILED ===');
  process.exit(failed === 0 ? 0 : 1);
})().catch((e) => {
  console.error('QA CRASH', e);
  process.exit(1);
});
