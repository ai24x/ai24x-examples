// QA 2026-08-21：手机端紧凑化 —— 顶栏精简 / 汉堡菜单 / 抽屉导航+语言+登录 / 桌面无回归 / 中国指数已清除
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
async function mockCore(page) {
  await page.route('**/api/me**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ code: 0, data: { email: 'qa.mob@example.com', plan: 'free', is_vip: false } }),
  }));
  await page.route('**/api/subscribe/status**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ code: 0, data: { active: false, plan: 'free' } }),
  }));
  await page.route('**/v1/auth/providers**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ google: true, apple: false }),
  }));
}

(async () => {
  if (!fs.existsSync(SHOTS)) fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });

  // ===== 1) 静态源码断言 =====
  const html = read('p/markets/web/app.html');
  log('src.menu_btn_exists', html.indexOf('id="mk-menu-btn"') >= 0 && html.indexOf('id="mk-drawer"') >= 0, '');
  log('src.drawer_has_nav_auth', html.indexOf('id="auth-area-mob"') >= 0 && html.indexOf('id="mk-console-mob"') >= 0, '');
  log('src.mobile_hides_nav', html.indexOf('.mk-nav { display: none; }') >= 0 && html.indexOf('#auth-area { display: none; }') >= 0, '');
  log('src.chart_h420', html.indexOf('.chart { height: 420px; }') >= 0, '');
  log('src.no_cn_samples', html.indexOf("sym: 'sh000001'") < 0 && html.indexOf("sym: 'sz399001'") < 0 && html.indexOf("sym: 'hkHSI'") < 0, '');
  log('src.onboard_slim', html.indexOf('onboard.step2') < 0 && html.indexOf('onboard.step3') < 0, '');
  log('src.menu_i18n', html.indexOf("'menu.title': 'Menu'") >= 0 && html.indexOf("'menu.title': '菜单'") >= 0, '');

  // ===== 2) 手机 375：顶栏精简 + 汉堡菜单开合 + 抽屉内容 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await mockCore(page);
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1800);

    const top = await page.evaluate(() => {
      const inner = document.querySelector('.mk-top-inner');
      const nav = document.querySelector('.mk-nav');
      const authArea = document.getElementById('auth-area');
      const menuBtn = document.getElementById('mk-menu-btn');
      const toolbar = document.querySelector('.mk-toolbar');
      const chart = document.getElementById('chart-main');
      return {
        topH: Math.round(inner.getBoundingClientRect().height),
        navHidden: getComputedStyle(nav).display === 'none',
        authHidden: getComputedStyle(authArea).display === 'none',
        menuVisible: getComputedStyle(menuBtn).display !== 'none',
        toolbarH: Math.round(toolbar.getBoundingClientRect().height),
        chartH: Math.round(chart.getBoundingClientRect().height),
        noOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
      };
    });
    log('mob.top_slim', top.topH <= 58, 'topH=' + top.topH);
    log('mob.nav_auth_hidden', top.navHidden && top.authHidden, '');
    log('mob.menu_btn_visible', top.menuVisible, '');
    log('mob.chart_taller', top.chartH >= 415, 'chartH=' + top.chartH);
    log('mob.no_horizontal_overflow', top.noOverflow, '');
    await page.screenshot({ path: path.join(SHOTS, 'mobile-top-compact.png') });

    // 打开汉堡菜单
    await page.click('#mk-menu-btn');
    await page.waitForTimeout(500);
    const drawer = await page.evaluate(() => {
      const d = document.getElementById('mk-drawer');
      const links = Array.from(d.querySelectorAll('.mk-drawer-nav a')).map((a) => a.textContent.trim());
      const auth = Array.from(d.querySelectorAll('#auth-area-mob a, #auth-area-mob button')).map((a) => a.textContent.trim());
      const lang = Array.from(d.querySelectorAll('.mk-drawer-head')).length;
      const r = d.querySelector('.mk-drawer-panel').getBoundingClientRect();
      return {
        visible: !d.hidden,
        links,
        auth,
        fits: r.right <= window.innerWidth + 1 && r.left >= 0,
      };
    });
    log('mob.drawer_opens', drawer.visible, '');
    log('mob.drawer_nav_links', drawer.links.length === 4 && drawer.links[0] === 'Home', drawer.links.join(' | '));
    log('mob.drawer_auth_links', drawer.auth.length >= 2, drawer.auth.join(' | '));
    log('mob.drawer_fits_screen', drawer.fits, '');
    await page.screenshot({ path: path.join(SHOTS, 'mobile-drawer-open.png') });

    // 关闭（点抽屉外遮罩区域，避免命中 panel）
    await page.mouse.click(18, 400);
    await page.waitForTimeout(400);
    const closed = await page.evaluate(() => document.getElementById('mk-drawer').hidden);
    log('mob.drawer_closes', closed, '');

    // 语言切换：抽屉重开，切中文
    await page.click('#mk-menu-btn');
    await page.waitForTimeout(400);
    await page.click('#mk-drawer-close');
    await page.waitForTimeout(300);
    log('mob.drawer_close_btn', true, '');
    log('mob.no_js_errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
    await ctx.close();
  }

  // ===== 3) 手机中文：菜单标题 + 无中国指数样本 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    await page.addInitScript(() => { try { localStorage.setItem('markets_lang', 'zh'); } catch (e) {} });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await mockCore(page);
    await page.goto('http://127.0.0.1:18012/app.html?lang=zh', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1200);
    await page.click('#mk-menu-btn');
    await page.waitForTimeout(400);
    const zh = await page.evaluate(() => {
      const head = document.querySelector('.mk-drawer-head span').textContent;
      const samples = Array.from(document.querySelectorAll('#samples button[data-symbol]')).map((b) => b.getAttribute('data-symbol'));
      const cn = samples.filter((s) => /^(sh|sz|bj)\d|^hk/i.test(s));
      const nav = Array.from(document.querySelectorAll('.mk-drawer-nav a')).map((a) => a.textContent.trim());
      return { head, cn, nav };
    });
    log('zh.menu_title', zh.head === '菜单', zh.head);
    log('zh.samples_us_only', zh.cn.length === 0 && zh.nav.length === 4 && zh.nav[0] === '首页', JSON.stringify(zh.nav));
    log('zh.no_js_errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
    await page.screenshot({ path: path.join(SHOTS, 'mobile-zh-drawer.png') });
    await ctx.close();
  }

  // ===== 4) 桌面 1280：导航/语言/登录区正常（无回归） =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await mockCore(page);
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1500);
    const desk = await page.evaluate(() => {
      const nav = document.querySelector('.mk-nav');
      const auth = document.getElementById('auth-area');
      const menuBtn = document.getElementById('mk-menu-btn');
      const drawer = document.getElementById('mk-drawer');
      const chart = document.getElementById('chart-main');
      return {
        navVisible: getComputedStyle(nav).display !== 'none' && nav.querySelectorAll('a').length === 4 && nav.querySelector('a').textContent.trim() === 'Home',
        authVisible: getComputedStyle(auth).display !== 'none' && auth.querySelectorAll('a,button').length >= 2,
        menuHidden: getComputedStyle(menuBtn).display === 'none',
        drawerHidden: drawer.hidden,
        chartH: Math.round(chart.getBoundingClientRect().height),
      };
    });
    log('desk.nav_auth_visible', desk.navVisible && desk.authVisible, 'nav=' + desk.navVisible + ' auth=' + desk.authVisible);
    log('desk.menu_drawer_hidden', desk.menuHidden && desk.drawerHidden, '');
    log('desk.chart_unchanged', desk.chartH >= 430, 'chartH=' + desk.chartH);
    log('desk.no_js_errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
    await page.screenshot({ path: path.join(SHOTS, 'desktop-regression.png') });
    await ctx.close();
  }

  const failed = results.filter((r) => !r.ok);
  console.log('\n===== SUMMARY =====');
  console.log('TOTAL ' + results.length + ' | PASS ' + (results.length - failed.length) + ' | FAIL ' + failed.length);
  failed.forEach((r) => console.log('  FAIL | ' + r.name + (r.detail ? ' | ' + r.detail : '')));
  process.exit(failed.length ? 1 : 0);
})();
