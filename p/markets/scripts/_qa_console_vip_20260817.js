// QA 2026-08-17：console 页统一产品套餐（选项目 → 选套餐 → 选支付方式）+ markets 订阅状态条
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

  // 兜底最先注册（Playwright 后注册优先，避免吞掉下方特定接口的 mock）
  await page.route('**/v1/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  );
  await page.route('**/v1/billing/balance', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, balance_usd: 12.3, email: 'qa@console.dev', plan: 'free' }) })
  );
  await page.route('**/v1/billing/products', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      ok: true,
      pay: { enabled: true, mock_allowed: true, wechat_ready: false, alipay_ready: false, paypal_ready: false, creem_ready: false, crypto_ready: false },
      products: [
        { product: 'markets', title: 'AI24X Markets Pro', title_zh: 'AI24X 行情官 · 国际版 Pro', desc: 'desc', desc_zh: 'desc', url: 'https://markets.ai24x.com', plans: [
          { plan: 'weekly', title: 'Pro Weekly', title_zh: 'AI24X Markets Pro · 周卡', price_label: '$9.9/week', price_label_zh: '$9.9/周', days: 7, perk: 'p', perk_zh: 'p' },
          { plan: 'monthly', title: 'Pro Monthly', title_zh: 'AI24X Markets Pro · 月卡', price_label: '$24.9/month', price_label_zh: '$24.9/月', days: 30, perk: 'p', perk_zh: 'p' },
          { plan: 'yearly', title: 'Pro Yearly', title_zh: 'AI24X Markets Pro · 年卡', price_label: '$199/year', price_label_zh: '$199/年', days: 365, perk: 'p', perk_zh: 'p' },
        ]},
        { product: 'token', title: 'Token API', title_zh: 'Token 接口开发', desc: 'desc', desc_zh: 'desc', url: 'https://open.ai24x.com', plans: [
          { plan: 'token_pack_10k', title: 'Starter', title_zh: '入门包', price_usd: '0.02', price_yuan: '0.14', credit_tokens: 1000000, validity_days: 365 },
        ]},
      ],
    }) })
  );
  await page.route('**/v1/billing/orders*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, rows: [] }) })
  );
  await page.route('**/v1/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, user: { email: 'qa@console.dev' } }) })
  );
  await page.goto('http://127.0.0.1:8000/console.html#billing', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);

  const onBilling = await page.evaluate(() => !document.getElementById('panel-billing').hasAttribute('hidden'));
  const productsView = await page.evaluate(() => {
    const box = document.getElementById('productsList');
    if (!box) return { cards: 0, rows: 0, firstProduct: '', hasOpenLink: false, marketsRows: 0, tokenRows: 0 };
    const cards = box.querySelectorAll('.product-card');
    const rows = box.querySelectorAll('.product-plan-row');
    const marketsRows = box.querySelectorAll('.product-card[data-product="markets"] .product-plan-row').length;
    const tokenRows = box.querySelectorAll('.product-card[data-product="token"] .product-plan-row').length;
    const firstCard = cards.length ? cards[0].getAttribute('data-product') : '';
    const hasOpenLink = !!Array.from(box.querySelectorAll('a')).find((a) => a.getAttribute('href') === 'https://open.ai24x.com');
    return { cards: cards.length, rows: rows.length, firstProduct: firstCard, hasOpenLink, marketsRows, tokenRows };
  });
  const marketsSub = await page.evaluate(() => {
    const statusEls = document.querySelectorAll('.markets-sub-status');
    return {
      statusCount: statusEls.length,
      status: statusEls.length ? statusEls[0].textContent : '',
      cta: (document.getElementById('markets-bill-cta') || { textContent: '' }).textContent,
      lineVisible: !document.getElementById('markets-bill-line') || document.getElementById('markets-bill-line').style.display !== 'none',
    };
  });
  log('console.billing_panel_open', onBilling, '');
  log('console.products_render', productsView.cards === 2 && productsView.rows >= 4, JSON.stringify(productsView));
  log('console.markets_first', productsView.firstProduct === 'markets' && productsView.marketsRows === 3 && productsView.tokenRows >= 1, JSON.stringify(productsView));
  log('console.token_open_link', productsView.hasOpenLink, '');
  log('console.markets_bill_line_renders', marketsSub.statusCount >= 2 && marketsSub.status.length > 0, 'count=' + marketsSub.statusCount + ' status=' + marketsSub.status.slice(0, 70));
  log('console.markets_cta_present', marketsSub.cta.length > 0, 'cta=' + marketsSub.cta);
  log('console.no_js_errors', errors.length === 0, errors.slice(0, 3).join('; '));

  // 点套餐 → 弹窗统一列支付方式
  await page.click('.product-card[data-product="markets"] .product-plan-row[data-plan="monthly"] .btn');
  await page.waitForTimeout(500);
  const chooser = await page.evaluate(() => {
    const root = document.getElementById('modal-pay');
    const chEl = document.getElementById('modal-pay-channels');
    return {
      open: !!(root && root.classList.contains('is-open')),
      title: document.getElementById('modal-pay-title') ? document.getElementById('modal-pay-title').textContent : '',
      channels: chEl ? chEl.querySelectorAll('button[data-pay-channel]').length : 0,
    };
  });
  log('console.plan_chooser_modal', chooser.open && chooser.title.indexOf('Pro Monthly') >= 0 && chooser.channels >= 1, JSON.stringify(chooser));
  await page.click('#modal-pay .ui-modal-actions [data-close-modal="modal-pay"]');
  await page.waitForTimeout(300);

  // Overview 面板也有 Markets 卡
  await page.click('[data-console-panel="overview"]');
  await page.waitForTimeout(600);
  const ov = await page.evaluate(() => {
    const card = document.getElementById('panel-overview');
    const cta = document.getElementById('markets-sub-cta');
    return {
      card: card.textContent.indexOf('AI24X Markets') >= 0 && !!document.getElementById('markets-sub-line'),
      noQuick: !document.getElementById('btn-ov-week') && !document.getElementById('btn-ov-month') && !document.getElementById('btn-ov-year'),
      ctaToBilling: !!cta && cta.tagName === 'A' && cta.getAttribute('href') === '#billing' && cta.className.indexOf('go-markets-plans') >= 0,
    };
  });
  log('console.overview_markets_card', ov.card && ov.noQuick && ov.ctaToBilling, JSON.stringify(ov));

  const failed = results.filter((r) => !r.ok).length;
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== FAILED ' + failed + ' ===');
  await browser.close();
})();
