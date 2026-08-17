// QA 2026-08-17：console 页 Markets Pro 卡片 + Billing 区分横幅（mock core API，真实调 markets 订阅状态）
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

  await page.route('**/v1/billing/balance', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, balance_usd: 12.3, email: 'qa@console.dev', plan: 'free' }) })
  );
  await page.route('**/v1/billing/plans', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, plans: [] }) })
  );
  await page.route('**/v1/billing/orders*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, rows: [] }) })
  );
  await page.route('**/v1/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, user: { email: 'qa@console.dev' } }) })
  );
  // 其余 core 接口统一空响应，避免 401 踢登录
  await page.route('**/v1/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  );

  await page.goto('http://127.0.0.1:8000/console.html#billing', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);

  const onBilling = await page.evaluate(() => !document.getElementById('panel-billing').hasAttribute('hidden'));
  const sepVisible = await page.evaluate(() => {
    const panel = document.getElementById('panel-billing');
    return panel.textContent.indexOf('Two systems') >= 0 || panel.textContent.indexOf('两套体系') >= 0;
  });
  const sepCta = await page.evaluate(() => {
    const a = Array.from(document.querySelectorAll('#panel-billing a'));
    return a.some((x) => x.getAttribute('href') === 'https://markets.ai24x.com/app.html#sub');
  });
  const marketsCard = await page.evaluate(() => {
    const line = document.getElementById('markets-sub-line');
    return {
      exists: !!line,
      status: (document.getElementById('markets-sub-status') || {}).textContent || '',
      cta: (document.getElementById('markets-sub-cta') || { textContent: '' }).textContent,
    };
  });
  log('console.billing_panel_open', onBilling, '');
  log('console.billing_sep_banner_visible', sepVisible && sepCta, '');
  log('console.markets_sub_line_renders', marketsCard.exists && marketsCard.status.length > 0, 'status=' + marketsCard.status.slice(0, 70));
  log('console.markets_cta_present', marketsCard.cta.length > 0, 'cta=' + marketsCard.cta);
  log('console.no_js_errors', errors.length === 0, errors.slice(0, 3).join('; '));

  // Overview 面板也有 Markets 卡
  await page.click('[data-console-panel="overview"]');
  await page.waitForTimeout(600);
  const ov = await page.evaluate(() => {
    const card = document.getElementById('panel-overview');
    return card.textContent.indexOf('AI24X Markets') >= 0 && !!document.getElementById('markets-sub-line');
  });
  log('console.overview_markets_card', ov, '');

  const failed = results.filter((r) => !r.ok).length;
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== FAILED ' + failed + ' ===');
  await browser.close();
})();
