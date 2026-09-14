// 截图：右上角升级入口 + Overview 面板（无快捷购买）+ Billing 套餐面板
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
  const OUT = path.join(__dirname, '_shots_console_unify');
  const fs = require('fs');
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

  // www 首页：右上角升级 VIP 入口
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:8000/index.html?x=shot', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const up = await page.evaluate(() => {
      const el = document.querySelector('.header-upgrade');
      return el ? { text: el.textContent, href: el.getAttribute('href'), target: el.getAttribute('target') } : null;
    });
    console.log('UPGRADE_PILL', JSON.stringify(up));
    await page.screenshot({ path: path.join(OUT, 'www_header_upgrade.png') });
    await ctx.close();
  }

  // console Overview：已登录 + mock API，验证无快捷按钮、CTA 切套餐
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
    const page = await ctx.newPage();
    await page.addInitScript(() => {
      try {
        localStorage.setItem('ai24x_auth_token', 'fake-token-shot');
        localStorage.setItem('ai24x_auth_user', '{"email":"shot@qa.dev"}');
      } catch (e) {}
    });
    await page.route('**/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, balance_usd: 5, user: { email: 'shot@qa.dev' }, plans: [], rows: [] }) })
    );
    await page.route('**/v1/billing/products', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        ok: true,
        pay: { enabled: true, mock_allowed: true, wechat_ready: true, alipay_ready: true, paypal_ready: true, creem_ready: false, crypto_ready: false },
        products: [
          { product: 'markets', title: 'AI24X Markets Pro', title_zh: 'AI24X 行情官 · 国际版 Pro', desc: 'US stocks, ETFs & indices with charts and AI commentary.', desc_zh: '美股/ETF/指数行情图表与 AI 点评。', url: 'https://markets.ai24x.com', plans: [
            { plan: 'weekly', title: 'Pro Weekly', title_zh: 'AI24X Markets Pro · 周卡', price_label: '$9.9/week', price_label_zh: '$9.9/周', days: 7, perk: 'Unlimited AI briefs · 50-symbol watchlist', perk_zh: 'AI 点评不限次 · 自选 50 只' },
            { plan: 'monthly', title: 'Pro Monthly', title_zh: 'AI24X Markets Pro · 月卡', price_label: '$24.9/month', price_label_zh: '$24.9/月', days: 30, perk: 'Unlimited AI briefs · 50-symbol watchlist', perk_zh: 'AI 点评不限次 · 自选 50 只' },
            { plan: 'yearly', title: 'Pro Yearly', title_zh: 'AI24X Markets Pro · 年卡', price_label: '$199/year', price_label_zh: '$199/年', days: 365, perk: 'Save 33% · Unlimited AI briefs', perk_zh: '省 33% · AI 点评不限次' },
          ]},
          { product: 'token', title: 'Token API', title_zh: 'Token 接口开发', desc: 'API credits for developers.', desc_zh: '开发者接口额度。', url: 'https://open.ai24x.com', plans: [
            { plan: 'token_pack_10k', title: 'Starter', title_zh: '入门包', price_usd: '0.02', price_yuan: '0.14', credit_tokens: 1000000, validity_days: 365 },
            { plan: 'token_pack_100k', title: 'Builder', title_zh: '开发包', price_usd: '0.20', price_yuan: '1.44', credit_tokens: 60000000, validity_days: 365 },
          ]},
        ],
      }) })
    );
    await page.goto('http://127.0.0.1:8000/console.html?lang=en&x=shot#overview', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1800);
    const ov = await page.evaluate(() => ({
      hasQuick: !!document.getElementById('btn-ov-week') || !!document.getElementById('btn-ov-month') || !!document.getElementById('btn-ov-year'),
      ctaTag: (document.getElementById('markets-sub-cta') || {}).tagName,
      ctaPanel: (document.getElementById('markets-sub-cta') || {}).getAttribute ? document.getElementById('markets-sub-cta').getAttribute('data-console-panel') : null,
    }));
    console.log('OVERVIEW', JSON.stringify(ov));
    await page.screenshot({ path: path.join(OUT, 'console_overview_desktop.png') });

    // 点 CTA → Billing 面板截图
    await page.click('#markets-sub-cta');
    await page.waitForTimeout(900);
    const onBilling = await page.evaluate(() => document.getElementById('panel-billing').classList.contains('is-active'));
    console.log('CTA_TO_BILLING', onBilling);
    await page.screenshot({ path: path.join(OUT, 'console_billing_desktop.png') });
    await ctx.close();
  }

  // console Overview mobile
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
    const page = await ctx.newPage();
    await page.addInitScript(() => {
      try {
        localStorage.setItem('ai24x_auth_token', 'fake-token-shot');
        localStorage.setItem('ai24x_auth_user', '{"email":"shot@qa.dev"}');
      } catch (e) {}
    });
    await page.route('**/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, balance_usd: 5, user: { email: 'shot@qa.dev' }, plans: [], rows: [] }) })
    );
    await page.route('**/v1/billing/products', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, pay: { enabled: true, mock_allowed: true }, products: [] }) })
    );
    await page.goto('http://127.0.0.1:8000/console.html?lang=en&x=shot#overview', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1800);
    await page.screenshot({ path: path.join(OUT, 'console_overview_mobile.png') });
    await page.click('[data-console-panel="billing"]');
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(OUT, 'console_billing_mobile.png') });
    await ctx.close();
  }

  // markets 首页顶部：Google 登录图标
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: false }) })
    );
    await page.goto('http://127.0.0.1:18012/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const social = await page.evaluate(() => {
      const g = document.querySelector('#social-login a[title="Continue with Google"]');
      return g ? { text: g.textContent.trim(), href: g.getAttribute('href') } : null;
    });
    console.log('MARKETS_INDEX_SOCIAL', JSON.stringify(social));
    await page.screenshot({ path: path.join(OUT, 'markets_index_header_social.png') });
    await ctx.close();
  }

  // markets app 底部订阅引导：未登录 → 注册；已登录 → 用户中心
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
    const page = await ctx.newPage();
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: false }) })
    );
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1400);
    const ctaAnon = await page.evaluate(() => {
      const c = document.getElementById('band-cta');
      const b = document.getElementById('sub-band');
      return { href: c ? c.getAttribute('href') : '', text: c ? c.textContent : '', bandTop: b ? b.getBoundingClientRect().top : 0 };
    });
    console.log('BAND_ANON', JSON.stringify(ctaAnon));
    await page.evaluate(() => document.getElementById('sub-band').scrollIntoView());
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT, 'app_band_anon.png') });
    await ctx.close();
  }
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
    await ctx.addCookies([
      { name: 'ai24x_auth_token', value: 'fake-token-shot2', domain: '127.0.0.1', path: '/' },
      { name: 'ai24x_auth_user', value: encodeURIComponent('{"email":"shot2@qa.dev"}'), domain: '127.0.0.1', path: '/' },
    ]);
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    const ctaPro = await page.evaluate(() => {
      const c = document.getElementById('band-cta');
      return { href: c ? c.getAttribute('href') : '', text: c ? c.textContent : '' };
    });
    console.log('BAND_LOGGED', JSON.stringify(ctaPro));
    await page.evaluate(() => document.getElementById('sub-band').scrollIntoView());
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT, 'app_band_logged.png') });
    await ctx.close();
  }

  await browser.close();
  console.log('SHOTS_DONE', OUT);
})().catch((e) => { console.error(e); process.exit(2); });
