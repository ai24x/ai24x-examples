// QA 2026-08-23：Plans/页面外链本地环境感知——二级域名跳转统一改当前环境（本地 18012/18080），生产保持原样
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

// 生产路径单测：正则替换后拼回生产域名应保持不变
function prodPath(url, base) {
  if (/^https?:\/\/markets\.ai24x\.com(?:\/|$)/.test(url)) {
    return base + url.replace(/^https?:\/\/markets\.ai24x\.com/, '').replace(/^\//, '');
  }
  if (/^https?:\/\/open\.ai24x\.com(?:\/|$)/.test(url)) {
    return base + url.replace(/^https?:\/\/open\.ai24x\.com/, '').replace(/^\//, '');
  }
  return url;
}
log('unit.prod_markets_root', prodPath('https://markets.ai24x.com', 'https://markets.ai24x.com/') === 'https://markets.ai24x.com/');
log('unit.prod_markets_deep', prodPath('https://markets.ai24x.com/app.html#sub', 'https://markets.ai24x.com/') === 'https://markets.ai24x.com/app.html#sub');
log('unit.prod_open_root', prodPath('https://open.ai24x.com', 'https://open.ai24x.com/') === 'https://open.ai24x.com/');
log('unit.prod_open_deep', prodPath('https://open.ai24x.com/models/vip-picks.html', 'https://open.ai24x.com/') === 'https://open.ai24x.com/models/vip-picks.html');

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

  // 1) console #billing Plans：产品卡外链本地化
  await page.goto('http://127.0.0.1:8000/console.html#billing?x=envlink', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  const view = await page.evaluate(() => {
    const box = document.getElementById('productsList');
    if (!box) return null;
    const cards = Array.from(box.querySelectorAll('.product-card'));
    const get = (pid, sel) => {
      const c = cards.find((x) => x.getAttribute('data-product') === pid);
      if (!c) return null;
      const el = c.querySelector(sel);
      return el ? el.getAttribute('href') : null;
    };
    const freeBtn = document.querySelector('#marketsPlansGrid .mplan-free-cta');
    const byokCta = (() => {
      const c = cards.find((x) => x.getAttribute('data-product') === 'byok');
      if (!c) return null;
      const a = c.querySelector('.product-plan-act a');
      return a ? a.getAttribute('href') : null;
    })();
    return {
      products: cards.map((c) => c.getAttribute('data-product')).join(','),
      marketsOpen: get('markets', '.open-product'),
      tokenOpen: get('token', '.open-product'),
      byokOpen: get('byok', '.open-product'),
      byokCta,
      freeBtn: freeBtn ? freeBtn.getAttribute('href') : null,
      footerDev: document.querySelector('.footer-bottom a[data-i18n="footer.link.developer"]') ? document.querySelector('.footer-bottom a[data-i18n="footer.link.developer"]').getAttribute('href') : null,
    };
  });
  log('console.products', !!view && view.products === 'markets,token,byok', view ? view.products : 'no box');
  log('console.markets_open_local', !!view && view.marketsOpen === 'http://127.0.0.1:18012/', view ? view.marketsOpen : '');
  log('console.token_open_local', !!view && view.tokenOpen === 'http://127.0.0.1:18080/', view ? view.tokenOpen : '');
  log('console.byok_open_local', !!view && view.byokOpen === 'http://127.0.0.1:18080/pricing.html', view ? view.byokOpen : '');
  log('console.byok_cta_local', !!view && view.byokCta === 'http://127.0.0.1:18080/pricing.html', view ? view.byokCta : '');
  log('console.free_btn_local_app', !!view && view.freeBtn === 'http://127.0.0.1:18012/app.html', view ? view.freeBtn : '');
  log('console.footer_dev_local', !!view && view.footerDev === 'http://127.0.0.1:18080/', view ? view.footerDev : '');

  // 2) pricing.html：BYOK 卡 + 开发者区 data-open 本地化
  await page.goto('http://127.0.0.1:8000/pricing.html?x=envlink', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  const pr = await page.evaluate(() => {
    const q = (sel) => {
      const el = document.querySelector(sel);
      return el ? el.getAttribute('href') : null;
    };
    return {
      byokCta: q('#byokSection .btn-primary'),
      devCta: q('a[data-i18n="page.pricing.devCta"]'),
      freeCta: q('a[data-i18n="page.pricing.freeCta"]'),
    };
  });
  log('pricing.byok_cta_local', pr.byokCta === 'http://127.0.0.1:18080/pricing.html', pr.byokCta);
  log('pricing.dev_cta_local', pr.devCta === 'http://127.0.0.1:18080/', pr.devCta);
  log('pricing.free_cta_local', pr.freeCta === 'http://127.0.0.1:18012/', pr.freeCta);

  // 3) product.html：markets 深链保留路径 + open 本地化
  await page.goto('http://127.0.0.1:8000/product.html?x=envlink', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  const pd = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a[data-markets], a[data-open]'));
    return links.map((a) => a.getAttribute('href'));
  });
  log('product.markets_deep_local', pd.some((h) => h === 'http://127.0.0.1:18012/app.html#sub'), pd.join(' | '));
  log('product.open_local', pd.some((h) => h === 'http://127.0.0.1:18080/'), pd.join(' | '));

  // 4) 首页 hero CTA 本地化
  await page.goto('http://127.0.0.1:8000/index.html?x=envlink', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  const ix = await page.evaluate(() => {
    const el = document.querySelector('a[data-i18n="page.index.hero.cta.free"]');
    return el ? el.getAttribute('href') : null;
  });
  log('index.hero_free_local', ix === 'http://127.0.0.1:18012/app.html', ix);

  // 5) models/guides 跳转 stub → 本地 18080
  await page.goto('http://127.0.0.1:8000/models/index.html?x=envlink', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  log('stub.models_local_redirect', page.url().indexOf('http://127.0.0.1:18080') === 0, page.url());
  await page.goto('http://127.0.0.1:8000/guides/index.html?x=envlink', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  log('stub.guides_local_redirect', page.url().indexOf('http://127.0.0.1:18080') === 0, page.url());

  log('no_page_errors', errors.length === 0, errors.slice(0, 3).join(' ; '));

  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log('SUMMARY ' + (results.length - failed) + '/' + results.length + ' PASS');
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error('QA ERROR', e);
  process.exit(2);
});
