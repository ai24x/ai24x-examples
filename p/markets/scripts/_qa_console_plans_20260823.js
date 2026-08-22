// QA 2026-08-23：console overview 套餐卡片 + Upgrade 统一跳 Plans（billing）下单 + pricing 按钮统一跳 Plans
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

const PRODUCTS_MOCK = {
  ok: true,
  pay: { enabled: true, mock_allowed: true, wechat_ready: false, alipay_ready: false, paypal_ready: true, creem_ready: false, crypto_ready: false },
  products: [
    {
      product: 'markets', title: 'AI24X Markets Pro', title_zh: 'AI24X 行情官 · 国际版 Pro',
      desc: 'desc', desc_zh: 'desc', url: 'https://markets.ai24x.com',
      plans: [
        { plan: 'weekly', title: 'Pro Weekly', title_zh: 'AI24X Markets Pro · 周卡', price_usd: 9.9, price_label: '$9.9/week', price_label_zh: '$9.9/周', days: 7, perk: '7-day Pro', perk_zh: '7 天完整 Pro 功能' },
        { plan: 'monthly', title: 'Pro Monthly', title_zh: 'AI24X Markets Pro · 月卡', price_usd: 24.9, price_label: '$24.9/month', price_label_zh: '$24.9/月', days: 30, perk: '30-day Pro', perk_zh: '30 天 Pro' },
        { plan: 'yearly', title: 'Pro Yearly', title_zh: 'AI24X Markets Pro · 年卡', price_usd: 199.0, price_label: '$199/year', price_label_zh: '$199/年', days: 365, perk: 'Best value', perk_zh: '最划算' },
      ],
    },
    {
      product: 'token', title: 'Token API', title_zh: 'Token 接口开发',
      desc: 'desc', desc_zh: 'desc', url: 'https://open.ai24x.com',
      plans: [
        { plan: 'token_pack_10k', title: 'Starter', title_zh: '入门包', price_usd: '0.02', price_yuan: '0.14', credit_tokens: 1000000, validity_days: 365 },
      ],
    },
  ],
};

async function bootConsole(page, url) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.addInitScript(() => {
    try {
      localStorage.setItem('ai24x_auth_token', 'fake-token-console-qa');
      localStorage.setItem('ai24x_auth_user', '{"email":"qa@console.dev"}');
    } catch (e) {}
  });
  // 兜底最先注册（Playwright 后注册优先，避免吞掉下方特定接口的 mock）
  await page.route('**/v1/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  );
  await page.route('**/v1/billing/balance', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, balance_usd: 12.3, email: 'qa@console.dev', plan: 'free' }) })
  );
  await page.route('**/v1/billing/products', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PRODUCTS_MOCK) })
  );
  await page.route('**/v1/billing/orders*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, rows: [] }) })
  );
  await page.route('**/v1/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, user: { email: 'qa@console.dev' } }) })
  );
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2200);
  return errors;
}

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = await bootConsole(page, 'http://127.0.0.1:8000/console.html#overview');

  // 1) overview 套餐卡片：免费 + 周/月/年 4 张，月卡带推荐徽标
  const ov = await page.evaluate(() => {
    const grid = document.getElementById('marketsPlansGrid');
    if (!grid) return { grid: false };
    const cards = grid.querySelectorAll('.mplan');
    const free = grid.querySelector('.mplan .mplan-free-cta');
    const rec = grid.querySelector('.mplan.is-rec .mplan-rec');
    const prices = Array.from(grid.querySelectorAll('.mplan-price')).map((e) => e.textContent.replace(/\s+/g, ' ').trim());
    return {
      grid: true, count: cards.length,
      hasFree: !!free && free.textContent.length > 0,
      recLabel: rec ? rec.textContent : '',
      prices: prices,
      monthlyRec: !!grid.querySelector('.mplan.is-rec'),
    };
  });
  log('ov.grid_renders', ov.grid && ov.count === 4, JSON.stringify({ count: ov.count }));
  log('ov.free_card', ov.hasFree, '');
  log('ov.monthly_recommended', ov.monthlyRec && ov.recLabel.length > 0, 'rec=' + ov.recLabel);
  log('ov.prices_ok', ov.prices.some((t) => t.indexOf('$9.9') >= 0) && ov.prices.some((t) => t.indexOf('$24.9') >= 0) && ov.prices.some((t) => t.indexOf('$199') >= 0), JSON.stringify(ov.prices));

  // 2) Upgrade CTA = 站内锚点 #billing（不再跳外站）
  const cta = await page.evaluate(() => {
    const el = document.getElementById('markets-sub-cta');
    return { tag: el ? el.tagName : '', href: el ? el.getAttribute('href') : '', cls: el ? el.className : '' };
  });
  log('ov.upgrade_cta_internal', cta.tag === 'A' && cta.href === '#billing' && cta.cls.indexOf('go-markets-plans') >= 0, JSON.stringify(cta));
  await page.click('#markets-sub-cta');
  await page.waitForTimeout(500);
  const switched = await page.evaluate(() => ({
    billingOn: !document.getElementById('panel-billing').hasAttribute('hidden'),
    overviewOff: document.getElementById('panel-overview').hasAttribute('hidden'),
  }));
  log('ov.upgrade_switches_to_billing', switched.billingOn && switched.overviewOff, JSON.stringify(switched));

  // 3) 回 overview，点月卡「选择并下单」→ 支付方式弹窗
  await page.click('[data-console-panel="overview"]');
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    const grid = document.getElementById('marketsPlansGrid');
    const rec = grid.querySelector('.mplan.is-rec');
    if (rec) rec.querySelector('.btn').click();
  });
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
  log('ov.card_opens_chooser', chooser.open && chooser.title.indexOf('Pro Monthly') >= 0 && chooser.channels >= 1, JSON.stringify(chooser));
  await page.click('#modal-pay .ui-modal-actions [data-close-modal="modal-pay"]');
  await page.waitForTimeout(300);

  // 4) 深链 console.html?plan=monthly#billing → billing 面板 + 对应行高亮（不自动弹窗）
  const page2 = await ctx.newPage();
  const errors2 = await bootConsole(page2, 'http://127.0.0.1:8000/console.html?plan=monthly#billing');
  const deep = await page2.evaluate(() => {
    const billingOn = !document.getElementById('panel-billing').hasAttribute('hidden');
    const row = document.querySelector('#productsList [data-plan="monthly"]');
    const modal = document.getElementById('modal-pay');
    return {
      billingOn: billingOn,
      rowFound: !!row,
      rowHighlighted: row ? row.style.outlineWidth === '2px' : false,
      modalOpen: !!(modal && modal.classList.contains('is-open')),
      modalTitle: document.getElementById('modal-pay-title') ? document.getElementById('modal-pay-title').textContent : '',
      marketsRows: document.querySelectorAll('.product-card[data-product="markets"] .product-plan-row').length,
    };
  });
  log('deep.billing_panel_open', deep.billingOn, '');
  log('deep.row_highlighted', deep.rowFound && deep.rowHighlighted && deep.marketsRows === 3, JSON.stringify(deep));
  log('deep.auto_opens_chooser', deep.modalOpen && deep.modalTitle.indexOf('Pro Monthly') >= 0, 'title=' + deep.modalTitle);
  await page2.close();

  // 5) pricing.html 按钮统一跳 console Plans
  const page3 = await ctx.newPage();
  const perrors = [];
  page3.on('pageerror', (e) => perrors.push(String(e)));
  await page3.goto('http://127.0.0.1:8000/pricing.html', { waitUntil: 'networkidle' });
  await page3.waitForTimeout(1200);
  const pricing = await page3.evaluate(() => {
    const hrefs = Array.from(document.querySelectorAll('a[href*="console.html"], a[href*="markets.ai24x.com"]')).map((a) => a.getAttribute('href'));
    const planLinks = hrefs.filter((h) => /^console\.html\?plan=(weekly|monthly|yearly)#billing$/.test(h));
    const leftover = hrefs.filter((h) => h.indexOf('markets.ai24x.com/app.html#sub') >= 0);
    return { planLinks, leftover };
  });
  log('pricing.buttons_to_console', pricing.planLinks.length >= 4, JSON.stringify(pricing.planLinks));
  log('pricing.no_markets_sub_leftover', pricing.leftover.length === 0, JSON.stringify(pricing.leftover));
  log('pricing.no_js_errors', perrors.length === 0, perrors.slice(0, 3).join('; '));
  await page3.close();

  // 6) 375px 手机宽度：无横向溢出、无 JS 报错
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('http://127.0.0.1:8000/console.html#overview', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1800);
  const mobile = await page.evaluate(() => ({
    sw: document.documentElement.scrollWidth,
    cw: document.documentElement.clientWidth,
    gridCols: getComputedStyle(document.getElementById('marketsPlansGrid')).gridTemplateColumns,
  }));
  log('mobile.no_horizontal_overflow', mobile.sw <= mobile.cw + 2, JSON.stringify(mobile));
  log('mobile.grid_single_col', mobile.gridCols.split(' ').length === 1, mobile.gridCols);
  log('mobile.no_js_errors', errors.length === 0, errors.slice(0, 3).join('; '));

  const failed = results.filter((r) => !r.ok).length;
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== FAILED ' + failed + ' ===');
  await browser.close();
})();
