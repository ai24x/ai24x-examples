// QA 2026-08-20：套餐按钮醒目化 + 支付弹新窗不丢页 + 数据源内部信息清零
// 前置：markets 18012 已加载新 app.html（无需真实账号，假 cookie + 接口 mock）
const fs = require('fs');
const path = require('path');
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const ROOT = 'E:\\AI24X\\ai24x-website\\ai24x01';
const SHOTS = path.join(ROOT, 'p', 'markets', 'scripts', '_qa_shots_20260820');
const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}
function read(p) { return fs.readFileSync(path.join(ROOT, p), 'utf8'); }
async function closeOnboard(page) {
  try { if (await page.isVisible('#onboard')) await page.click('#onboard-skip'); } catch (e) {}
}

async function mockCore(page) {
  await page.route('**/api/me**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ code: 0, data: { email: 'qa.payui@example.com', plan: 'free', is_vip: false } }),
  }));
  await page.route('**/api/subscribe/status**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ code: 0, data: { active: false, plan: 'free' } }),
  }));
  await page.route('**/v1/billing/pay/status**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ token_pay_enabled: true, token_pay_mock_enabled: true,
      wechat: { ui_ready: true }, alipay: { ui_ready: true }, paypal: { ui_ready: true }, creem: { ui_ready: true } }),
  }));
  await page.route('**/v1/billing/paypal/order**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ out_trade_no: 'QA-PAYPAL-20260820', amount_usd: 24.9, pay_url: 'https://paypal.example.test/checkout?otn=QA-PAYPAL-20260820' }),
  }));
  await page.route('**/v1/billing/alipay/wap**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ out_trade_no: 'QA-ALIPAY-20260820', amount_usd: 24.9, pay_url: 'https://alipay.example.test/wap?otn=QA-ALIPAY-20260820' }),
  }));
}

function seedAuth(ctx) {
  return ctx.addCookies([
    { name: 'ai24x_auth_token', value: 'qa-fake-token-20260820', domain: '127.0.0.1', path: '/' },
    { name: 'ai24x_auth_user', value: encodeURIComponent('{"email":"qa.payui@example.com"}'), domain: '127.0.0.1', path: '/' },
  ]);
}

(async () => {
  if (!fs.existsSync(SHOTS)) fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });

  // ===== 1) 静态源码断言 =====
  const html = read('p/markets/web/app.html');
  log('src.plan_cards_visible', html.indexOf('class="sub-plans"') >= 0 && html.indexOf('id="btn-sub-week"') >= 0 && html.indexOf('id="btn-sub-month"') >= 0 && html.indexOf('id="btn-sub-year"') >= 0, '');
  log('src.month_rec_badge', html.indexOf('class="sub-plan is-rec"') >= 0 && html.indexOf('data-i18n="sub.popular"') >= 0, '');
  log('src.plan_prices', html.indexOf('>$9.9<span') >= 0 && html.indexOf('>$24.9<span') >= 0 && html.indexOf('>$199<span') >= 0, '');
  log('src.footer_neutral_en', html.indexOf('Sources: Tencent') < 0 && html.indexOf('Eastmoney') < 0 && html.indexOf('Sina') < 0, '');
  log('src.footer_neutral_zh', html.indexOf('腾讯（主源）') < 0 && html.indexOf('东财') < 0, '');
  log('src.no_page_jump_checkout', html.indexOf('location.href = j.data.pay_url') < 0 && html.indexOf('function doCheckout') < 0, '');
  log('src.new_window_checkout', html.indexOf("window.open('about:blank', '_blank')") >= 0 && html.indexOf('checkoutWin.location.href = r.pay_url') >= 0, '');
  log('src.fallback_open_link', html.indexOf('id="payhub-open"') >= 0 && html.indexOf('target="_blank"') >= 0, '');
  log('src.payhub_sub_uses_new_key', html.indexOf("t('sub.' + planKey + 'T')") >= 0, '');

  const privacy = read('p/markets/web/privacy.html');
  log('src.privacy_no_provider_names', privacy.indexOf('Tencent') < 0 && privacy.indexOf('Eastmoney') < 0 && privacy.indexOf('Sina') < 0, '');
  const seoFiles = fs.readdirSync(path.join(ROOT, 'p', 'markets', 'web', 'seo')).filter((f) => f.endsWith('.html'));
  let seoBad = 0;
  for (const f of seoFiles) {
    const s = read(path.join('p', 'markets', 'web', 'seo', f));
    if (/source api:|tencent|eastmoney|sina/i.test(s)) seoBad++;
  }
  log('src.seo_no_internal_source', seoBad === 0, seoFiles.length + ' pages, bad=' + seoBad);
  const gen = read('p/markets/scripts/seo_gen.py');
  log('src.seo_gen_template_neutral', gen.indexOf('aggregated market data') >= 0 && gen.indexOf("source {data['source']}") < 0, '');

  // ===== 2) 桌面：套餐按钮醒目 + 弹窗不跳页 + alipay 弹新窗 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await seedAuth(ctx);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await mockCore(page);
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(900);
    await page.evaluate(() => document.getElementById('sub').scrollIntoView({ block: 'center' }));
    await page.waitForTimeout(400);

    const plan = await page.evaluate(() => {
      const ids = ['btn-sub-week', 'btn-sub-month', 'btn-sub-year'];
      const out = {};
      ids.forEach((id) => {
        const el = document.getElementById(id);
        const r = el.getBoundingClientRect();
        out[id] = {
          visible: r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight,
          text: el.textContent.replace(/\s+/g, ' ').trim(),
          isRec: el.classList.contains('is-rec'),
          badge: el.querySelector('.badge') ? el.querySelector('.badge').textContent : '',
          price: el.querySelector('.plan-price') ? el.querySelector('.plan-price').textContent : '',
        };
      });
      return out;
    });
    log('ui.three_plan_cards_visible', plan['btn-sub-week'].visible && plan['btn-sub-month'].visible && plan['btn-sub-year'].visible, JSON.stringify(plan).slice(0, 240));
    log('ui.month_card_highlighted', plan['btn-sub-month'].isRec && plan['btn-sub-month'].badge === 'POPULAR', 'badge=' + plan['btn-sub-month'].badge);
    log('ui.prices_rendered', plan['btn-sub-week'].price.indexOf('$9.9') >= 0 && plan['btn-sub-month'].price.indexOf('$24.9') >= 0 && plan['btn-sub-year'].price.indexOf('$199') >= 0, '');
    await page.screenshot({ path: path.join(SHOTS, 'desktop-sub-plans.png') });

    const urlBefore = page.url();
    await page.click('#btn-sub-month');
    await page.waitForTimeout(900);
    const hub = await page.evaluate(() => {
      const modal = document.getElementById('payhub');
      const btns = Array.from(document.querySelectorAll('#payhub-channels .payhub-btn'));
      return {
        visible: !modal.hidden,
        title: document.getElementById('payhub-title').textContent,
        sub: document.getElementById('payhub-sub').textContent,
        channels: btns.map((b) => b.textContent.trim()),
      };
    });
    log('ui.payhub_opens_no_nav', hub.visible && page.url() === urlBefore, page.url());
    log('ui.payhub_title_month', hub.title.indexOf('Pro') >= 0 && hub.sub.indexOf('Monthly') >= 0, hub.title + ' | ' + hub.sub);
    log('ui.four_channels', hub.channels.length >= 4, hub.channels.join(' | '));
    await page.screenshot({ path: path.join(SHOTS, 'desktop-payhub-modal.png') });

    // 点 Alipay → 新窗口打开支付页，主页面 URL 不变
    await page.click('#payhub-channels .payhub-btn:nth-child(2)');
    await page.waitForTimeout(1600);
    const afterAlipay = await page.evaluate(() => ({
      url: location.href,
      hint: document.getElementById('payhub-hint').textContent,
      openLinkHidden: document.getElementById('payhub-open').hidden,
      openLinkHref: document.getElementById('payhub-open').href,
    }));
    log('ui.alipay_main_page_kept', afterAlipay.url === urlBefore, afterAlipay.url);
    log('ui.alipay_hint_opened', afterAlipay.hint.indexOf('new window') >= 0, afterAlipay.hint.slice(0, 90));
    log('ui.alipay_fallback_link', afterAlipay.openLinkHidden === false && afterAlipay.openLinkHref.indexOf('alipay.example.test') >= 0, afterAlipay.openLinkHref);
    await page.screenshot({ path: path.join(SHOTS, 'desktop-alipay-new-window.png') });

    const footer = await page.textContent('footer.mk-footer');
    log('ui.footer_no_internal_sources', footer.indexOf('Tencent') < 0 && footer.indexOf('Eastmoney') < 0 && footer.indexOf('Sina') < 0 && footer.indexOf('15-minute delayed') >= 0, footer.slice(0, 110));
    log('ui.no_js_errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
    await ctx.close();
  }

  // ===== 3) 手机 375：按钮可见无横向溢出 + 弹窗不跳页 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    await seedAuth(ctx);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await mockCore(page);
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(800);
    await page.evaluate(() => document.getElementById('sub').scrollIntoView({ block: 'center' }));
    await page.waitForTimeout(400);
    const mob = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.sub-plan')).map((c) => {
        const r = c.getBoundingClientRect();
        return r.width > 0 && r.left >= 0 && r.right <= window.innerWidth + 1;
      });
      return {
        noHorizOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
        cardCount: cards.length,
        cardsFit: cards.every(Boolean),
      };
    });
    log('mob.no_horizontal_overflow', mob.noHorizOverflow, 'scrollWidth check');
    log('mob.plan_cards_fit', mob.cardCount === 3 && mob.cardsFit, 'cards=' + mob.cardCount);
    await page.screenshot({ path: path.join(SHOTS, 'mobile-sub-plans.png') });
    const urlBefore = page.url();
    await page.click('#btn-sub-year');
    await page.waitForTimeout(800);
    const mHub = await page.evaluate(() => {
      const modal = document.getElementById('payhub');
      const r = modal.getBoundingClientRect();
      return { visible: !modal.hidden, fits: r.left >= 0 && r.right <= window.innerWidth, url: location.href };
    });
    log('mob.payhub_opens_keeps_page', mHub.visible && mHub.fits && mHub.url === urlBefore, '');
    log('mob.no_js_errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
    await ctx.close();
  }

  const failed = results.filter((r) => !r.ok);
  console.log('\n===== SUMMARY =====');
  console.log('TOTAL ' + results.length + ' | PASS ' + (results.length - failed.length) + ' | FAIL ' + failed.length);
  failed.forEach((r) => console.log('  FAIL | ' + r.name + (r.detail ? ' | ' + r.detail : '')));
  process.exit(failed.length ? 1 : 0);
})();
