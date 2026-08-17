// QA 2026-08-17：菜单去行情官（首页保留） + 首页 RSI 移除 + VIP 订阅引导（markets 首页/App/console）
const fs = require('fs');
const path = require('path');
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const ROOT = 'E:\\AI24X\\ai24x-website\\ai24x01';
const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}
function read(p) { return fs.readFileSync(path.join(ROOT, p), 'utf8'); }

async function closeOnboard(page) {
  try { if (await page.isVisible('#onboard')) await page.click('#onboard-skip'); } catch (e) {}
}

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });

  // ===== 1) markets 首页（18012）：hero 升级 CTA + 引导卡 + 无 RSI =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/', { waitUntil: 'networkidle' });
    const body = await page.textContent('body');
    const heroCtas = await page.evaluate(() =>
      Array.from(document.querySelectorAll('.hero-cta a')).map((a) => a.getAttribute('href') + '::' + a.textContent)
    );
    log('home.hero_has_upgrade_cta', heroCtas.some((s) => s.indexOf('/app.html#sub') >= 0 && s.indexOf('Upgrade') >= 0), heroCtas.join(' | '));
    log('home.no_rsi_text', body.indexOf('RSI') < 0 && body.indexOf('rsi') < 0, '');
    log('home.go_pro_steps', body.indexOf('Go Pro in 3 steps') >= 0 && body.indexOf('$24.9/month') >= 0 && body.indexOf('$199/year') >= 0, '');
    log('home.how_works_mentions_signin', body.indexOf('sign in to unlock') >= 0 || body.indexOf('sign in') >= 0, '');
    log('home.no_js_errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ===== 2) markets app.html：未登录无引导条 / 登录免费用户有引导条 + 订阅步骤 =====
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    const anonBanner = await page.evaluate(() => document.getElementById('free-banner').classList.contains('show'));
    const subSteps = await page.textContent('#sub');
    log('app.anon_no_free_banner', !anonBanner, '');
    log('app.sub_steps_hint', subSteps.indexOf('How it works: 1') >= 0 || subSteps.indexOf('开通流程') >= 0, '');
    await ctx.close();
  }
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    await ctx.addCookies([
      { name: 'ai24x_auth_token', value: 'fake-token-for-qa', domain: '127.0.0.1', path: '/' },
      { name: 'ai24x_auth_user', value: encodeURIComponent('{"email":"qa@test.dev"}'), domain: '127.0.0.1', path: '/' },
    ]);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1200);
    const banner = await page.evaluate(() => {
      const fb = document.getElementById('free-banner');
      return { show: fb.classList.contains('show'), text: (document.getElementById('fb-text') || {}).textContent || '' };
    });
    const upgradeVisible = await page.evaluate(() => (document.getElementById('auth-upgrade') || { style: {} }).style.display);
    log('app.logged_free_banner_shows', banner.show, 'text=' + banner.text.slice(0, 70));
    log('app.logged_upgrade_visible', upgradeVisible === 'inline', 'display=' + upgradeVisible);
    // 点 Upgrade 引导条 → 滚动到 #sub
    await page.click('#fb-upgrade');
    await page.waitForTimeout(900);
    const nearSub = await page.evaluate(() => {
      const sub = document.getElementById('sub');
      if (!sub) return false;
      const r = sub.getBoundingClientRect();
      return r.top < window.innerHeight && r.bottom > 0;
    });
    log('app.banner_upgrade_scrolls_to_sub', nearSub, '');
    // 关闭引导条 → 消失（本会话不再显示）
    await page.click('#fb-close');
    await page.waitForTimeout(300);
    const closed = await page.evaluate(() => !document.getElementById('free-banner').classList.contains('show'));
    log('app.banner_dismiss_works', closed, '');
    log('app.logged_no_js_errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ===== 3) www console + shell/locales 静态断言 =====
  {
    const consoleHtml = read('web/console.html');
    const consoleJs = read('web/js/console.js');
    const shellJs = read('web/js/shell.js');
    const locales = read('web/config/locales.js');
    const marketsIndex = read('p/markets/web/index.html');
    const appHtml = read('p/markets/web/app.html');
    log('shell.nav_home_kept_markets_removed', shellJs.indexOf('nav("index.html", "nav.home", "home")') >= 0 && shellJs.indexOf('"nav.markets"') < 0, '');
    log('shell.fixNavActive_has_home', shellJs.indexOf('home') >= 0 && /fixNavActive/.test(shellJs), '');
    log('locales.nav_home_exists', locales.indexOf('"nav.home"') >= 0, '');
    log('locales.console_billsep_keys', locales.indexOf('page.console.billSep.title') >= 0 && locales.indexOf('page.console.markets.upgrade') >= 0, '');
    log('console.markets_card_status', consoleHtml.indexOf('markets-sub-line') >= 0 && consoleHtml.indexOf('markets-sub-cta') >= 0, '');
    log('console.billing_sep_banner', consoleHtml.indexOf('page.console.billSep.title') >= 0, '');
    log('console.js_load_markets_sub', consoleJs.indexOf('function loadMarketsSub') >= 0 && consoleJs.indexOf('markets.ai24x.com/api/subscribe/status') >= 0, '');
    log('app.html_no_rsi', appHtml.indexOf('RSI') < 0 && appHtml.indexOf('rsi') < 0, '');
    log('index.html_no_rsi', marketsIndex.indexOf('RSI') < 0 && marketsIndex.indexOf('rsi') < 0, '');

    // 版本号纪律：shell/locales 全站 f，console.js f，无旧版残留
    let shellOld = 0, shellNew = 0, locOld = 0, locNew = 0, conNew = 0;
    const walk = (dir) => {
      for (const name of fs.readdirSync(dir)) {
        const p = path.join(dir, name);
        const st = fs.statSync(p);
        if (st.isDirectory()) { if (name !== 'node_modules' && name !== '.git') walk(p); continue; }
        if (!/\.html$/i.test(name)) continue;
        const src = fs.readFileSync(p, 'utf8');
        if (src.indexOf('shell.js?v=20260818c') >= 0) shellOld++;
        if (src.indexOf('shell.js?v=20260818f') >= 0) shellNew++;
        if (src.indexOf('locales.js?v=20260818d') >= 0) locOld++;
        if (src.indexOf('locales.js?v=20260818f') >= 0) locNew++;
        if (src.indexOf('console.js?v=20260818f') >= 0) conNew++;
      }
    };
    walk(path.join(ROOT, 'web'));
    log('version.shell_unified_f', shellOld === 0 && shellNew >= 40, 'old=' + shellOld + ' new=' + shellNew);
    log('version.locales_unified_f', locOld === 0 && locNew >= 40, 'old=' + locOld + ' new=' + locNew);
    log('version.console_f', conNew === 1, 'new=' + conNew);
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== FAILED ' + failed + ' ===');
  await browser.close();
})();
