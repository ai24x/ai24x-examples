// QA 2026-08-21：头部菜单精简（Home/Pricing/Help/Console，去 Google/Discover/Chart App）+ Discover VIP 门禁
const fs = require('fs');
const path = require('path');
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const ROOT = 'E:\\AI24X\\ai24x-website\\ai24x01';
const SHOTS = path.join(ROOT, 'p', 'markets', 'scripts', '_qa_shots_20260821');
const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}
function read(p) { return fs.readFileSync(path.join(ROOT, p), 'utf8'); }
async function closeOnboard(page) {
  try { if (await page.isVisible('#onboard')) await page.click('#onboard-skip'); } catch (e) {}
}

function mockSub(page, pro) {
  return page.route('**/api/subscribe/status**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ code: 0, data: { pro: pro, plan: pro ? 'monthly' : 'free' } }),
  }));
}
function mockScreener(page) {
  return page.route('**/api/screener**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ code: 0, data: { items: [{ symbol: 'AAPL', name: 'Apple', price: 311.3, chg_pct: -1.75, score: 66, pos60: 0.42, vol_ratio: 1.1, pct5: 2.1, pct20: 5.2 }], count: 1, scanned: 90, generated_at: '2026-08-21T00:00:00Z' } }),
  }));
}
function seedAuth(ctx, token) {
  if (!token) return;
  return ctx.addCookies([
    { name: 'ai24x_auth_token', value: token, domain: '127.0.0.1', path: '/' },
    { name: 'ai24x_auth_user', value: encodeURIComponent('{"email":"qa.nav@example.com"}'), domain: '127.0.0.1', path: '/' },
  ]);
}

(async () => {
  if (!fs.existsSync(SHOTS)) fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });

  // ===== 1) 静态源码断言 =====
  const index = read('p/markets/web/index.html');
  const indexHeader = index.slice(index.indexOf('<header'), index.indexOf('</header>'));
  log('src.index_nav_slim', indexHeader.indexOf('Markets</a>') < 0 && indexHeader.indexOf('Discover') < 0 && indexHeader.indexOf('Chart App') < 0 && index.indexOf('social-login') < 0 && indexHeader.indexOf('Home</a>') >= 0, '');
  log('src.index_nav_home_url', index.indexOf('href="https://www.ai24x.com/index.html"') >= 0, '');
  const app = read('p/markets/web/app.html');
  log('src.app_nav_slim', app.indexOf('data-i18n="nav.markets"') < 0 && app.indexOf('data-i18n="nav.discover"') < 0 && app.indexOf('data-i18n="nav.home"') >= 0, '');
  const scr = read('p/markets/web/screener.html');
  log('src.screener_nav_slim', scr.indexOf('nav.discover') < 0 && scr.indexOf('nav.chart') < 0 && scr.indexOf('nav.home') >= 0, '');
  log('src.screener_gate_exists', scr.indexOf('id="sr-gate"') >= 0 && scr.indexOf('gate.upBtn') >= 0 && scr.indexOf('checkVip()') >= 0, '');
  const main = read('p/markets/api/server/app/main.py');
  log('src.screener_api_vip', main.indexOf('billing.is_pro(uid)') >= 0 && main.indexOf('vip_required') >= 0, '');
  const pricing = read('p/markets/web/pricing.html');
  const pricingHeader = pricing.slice(pricing.indexOf('<header'), pricing.indexOf('</header>'));
  log('src.pricing_nav_slim', pricingHeader.indexOf('Chart app') < 0 && pricingHeader.indexOf('https://www.ai24x.com/index.html') >= 0, '');

  // ===== 2) markets 首页桌面：导航 4 项 + 无 Google + 无 Discover/Chart App =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const nav = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('.nav-main a')).map((a) => ({ t: a.textContent.trim(), h: a.getAttribute('href') }));
      const actions = Array.from(document.querySelectorAll('.header-actions a')).map((a) => a.textContent.trim());
      return { links, actions, hasGoogle: document.body.innerHTML.indexOf('Continue with Google') >= 0 };
    });
    log('ui.index_nav_4', nav.links.length === 4, JSON.stringify(nav.links.map((l) => l.t)));
    log('ui.index_nav_home_first', nav.links[0] && nav.links[0].t === 'Home' && nav.links[0].h.indexOf('www.ai24x.com/index.html') >= 0, JSON.stringify(nav.links[0]));
    log('ui.index_actions_3', nav.actions.length === 3, nav.actions.join(' | '));
    log('ui.index_no_google', !nav.hasGoogle, '');
    log('ui.index_no_js_errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
    await page.screenshot({ path: path.join(SHOTS, 'desktop-index-header.png') });
    await ctx.close();
  }

  // ===== 3) markets 首页手机 375：无横向溢出 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18012/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    const m = await page.evaluate(() => ({ noOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1, navW: document.querySelector('.nav-main').scrollWidth, innerW: window.innerWidth }));
    log('mob.index_no_horizontal_overflow', m.noOverflow, 'navW=' + m.navW + ' innerW=' + m.innerW);
    await page.screenshot({ path: path.join(SHOTS, 'mobile-index-header.png') });
    await ctx.close();
  }

  // ===== 4) app.html 桌面 nav + 抽屉 nav（Home/Pricing/Help/Console） =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1000);
    const nav = await page.evaluate(() => Array.from(document.querySelectorAll('.mk-nav a')).map((a) => a.textContent.trim()));
    log('ui.app_desktop_nav', nav.length === 4 && nav[0] === 'Home' && nav.indexOf('Discover') < 0 && nav.indexOf('Markets') < 0, nav.join(' | '));
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(600);
    await page.click('#mk-menu-btn');
    await page.waitForTimeout(400);
    const drawer = await page.evaluate(() => Array.from(document.querySelectorAll('.mk-drawer-nav a')).map((a) => a.textContent.trim()));
    log('ui.app_drawer_nav', drawer.length === 4 && drawer[0] === 'Home' && drawer.indexOf('Discover') < 0, drawer.join(' | '));
    await ctx.close();
  }

  // ===== 5) screener.html：未登录 → 登录引导 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18012/screener.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(900);
    const gate = await page.evaluate(() => {
      const g = document.getElementById('sr-gate');
      const list = document.getElementById('sr-list');
      return { gateOn: g && g.style.display !== 'none', title: document.getElementById('gate-title').textContent, btn: document.getElementById('gate-btn').textContent, listOn: list && list.style.display !== 'none' };
    });
    log('vip.login_gate_shown', gate.gateOn && gate.title.indexOf('Sign in') >= 0 && gate.btn === 'Sign in' && !gate.listOn, JSON.stringify(gate));
    await page.screenshot({ path: path.join(SHOTS, 'screener-login-gate.png') });
    await ctx.close();
  }

  // ===== 6) screener.html：登录免费 → 升级引导 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    await seedAuth(ctx, 'qa-free-token');
    const page = await ctx.newPage();
    await mockSub(page, false);
    await mockScreener(page);
    await page.goto('http://127.0.0.1:18012/screener.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const gate = await page.evaluate(() => {
      const g = document.getElementById('sr-gate');
      const btn = document.getElementById('gate-btn');
      return { gateOn: g && g.style.display !== 'none', title: document.getElementById('gate-title').textContent, btnHref: btn ? btn.href : '', listOn: document.getElementById('sr-list').style.display !== 'none' };
    });
    log('vip.upgrade_gate_shown', gate.gateOn && gate.title.indexOf('Pro feature') >= 0 && gate.btnHref.indexOf('console.html#billing') >= 0 && !gate.listOn, JSON.stringify(gate));
    await page.screenshot({ path: path.join(SHOTS, 'screener-upgrade-gate.png') });
    await ctx.close();
  }

  // ===== 7) screener.html：VIP → 正常扫描 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    await seedAuth(ctx, 'qa-vip-token');
    const page = await ctx.newPage();
    await mockSub(page, true);
    await mockScreener(page);
    await page.goto('http://127.0.0.1:18012/screener.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    const ok = await page.evaluate(() => {
      const gate = document.getElementById('sr-gate');
      const list = document.getElementById('sr-list');
      return { gateOff: gate.style.display === 'none', listShown: list.style.display !== 'none' && list.textContent.indexOf('AAPL') >= 0 };
    });
    log('vip.screener_runs', ok.gateOff && ok.listShown, JSON.stringify(ok));
    await page.screenshot({ path: path.join(SHOTS, 'screener-vip-ok.png') });
    await ctx.close();
  }

  const failed = results.filter((r) => !r.ok);
  console.log('\n===== SUMMARY =====');
  console.log('TOTAL ' + results.length + ' | PASS ' + (results.length - failed.length) + ' | FAIL ' + failed.length);
  failed.forEach((r) => console.log('  FAIL | ' + r.name + (r.detail ? ' | ' + r.detail : '')));
  process.exit(failed.length ? 1 : 0);
})();
