// QA 2026-08-17：www 注册/登录页 Google/Apple 一键登录统一（桌面 + 手机 + OAuth 回跳 + 版本号）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

let failed = 0;
function check(name, ok, extra) {
  if (!ok) failed++;
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (extra ? ' | ' + extra : ''));
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });

  // ---------- register 桌面：Google 显示 / Apple 隐藏（mock google only） ----------
  {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: false }) })
    );
    await page.goto('http://127.0.0.1:8000/register.html?lang=en&x=q1', { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    const st = await page.evaluate(() => {
      const panel = document.getElementById('oauth-panel');
      const g = document.getElementById('btn-oauth-google');
      const a = document.getElementById('btn-oauth-apple');
      const gcs = g ? getComputedStyle(g) : null;
      return {
        panelDisplay: panel ? getComputedStyle(panel).display : 'no-panel',
        gDisplay: gcs ? gcs.display : 'no-g',
        gHref: g ? g.getAttribute('href') : '',
        gText: g ? g.textContent.trim() : '',
        gSvg: g ? !!g.querySelector('svg') : false,
        gIco: g ? (g.querySelector('svg') ? g.querySelector('svg').getAttribute('width') : '') : '',
        aDisplay: a ? getComputedStyle(a).display : 'no-a',
      };
    });
    check('register.oauth_panel_visible', st.panelDisplay !== 'none', st.panelDisplay);
    check('register.google_visible', st.gDisplay !== 'none', st.gDisplay + ' | ' + st.gText);
    check('register.google_href', st.gHref.indexOf('/v1/auth/google/login?next=') >= 0, st.gHref);
    check('register.google_icon', st.gSvg && st.gIco === '18', st.gIco);
    check('register.apple_hidden', st.aDisplay === 'none', st.aDisplay);
    check('register.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await page.close();
  }

  // ---------- register 手机 375px：按钮全宽可见 ----------
  {
    const mob = await browser.newContext({ viewport: { width: 375, height: 740 } });
    const page = await mob.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: true }) })
    );
    await page.goto('http://127.0.0.1:8000/register.html?lang=en&x=q2', { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    const st = await page.evaluate(() => {
      const g = document.getElementById('btn-oauth-google');
      const a = document.getElementById('btn-oauth-apple');
      const r = g ? g.getBoundingClientRect() : null;
      const ar = a ? a.getBoundingClientRect() : null;
      return {
        gW: r ? Math.round(r.width) : 0,
        gDisplay: g ? getComputedStyle(g).display : 'no-g',
        aDisplay: a ? getComputedStyle(a).display : 'no-a',
        aW: ar ? Math.round(ar.width) : 0,
        viewport: window.innerWidth,
      };
    });
    check('mobile.register.google_visible', st.gDisplay !== 'none', st.gDisplay);
    check('mobile.register.google_fullwidth', st.gW > 300 && st.gW <= 375, 'gW=' + st.gW);
    check('mobile.register.apple_visible', st.aDisplay !== 'none', st.aDisplay + ' aW=' + st.aW);
    check('mobile.register.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await mob.close();
  }

  // ---------- login 桌面：Google + Apple 均显示 ----------
  {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: true }) })
    );
    await page.goto('http://127.0.0.1:8000/login.html?lang=en&x=q3', { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    const st = await page.evaluate(() => {
      const g = document.getElementById('btn-oauth-google');
      const a = document.getElementById('btn-oauth-apple');
      return {
        gDisplay: g ? getComputedStyle(g).display : 'no-g',
        gHref: g ? g.getAttribute('href') : '',
        gSvg: g ? !!g.querySelector('svg') : false,
        aDisplay: a ? getComputedStyle(a).display : 'no-a',
        aHref: a ? a.getAttribute('href') : '',
        aSvg: a ? !!a.querySelector('svg') : false,
      };
    });
    check('login.google_visible', st.gDisplay !== 'none', st.gDisplay);
    check('login.google_href', st.gHref.indexOf('/v1/auth/google/login?next=') >= 0, st.gHref);
    check('login.google_icon', st.gSvg, '');
    check('login.apple_visible', st.aDisplay !== 'none', st.aDisplay);
    check('login.apple_href', st.aHref.indexOf('/v1/auth/apple/login?next=') >= 0, st.aHref);
    check('login.apple_icon', st.aSvg, '');
    check('login.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await page.close();
  }

  // ---------- api.js 全局会话同步：cookie → localStorage（任意页面加载恢复 OAuth 登录态） ----------
  {
    const page = await ctx.newPage();
    await ctx.addCookies([
      { name: 'ai24x_auth_token', value: 'sync-cookie-token', url: 'http://127.0.0.1:8000' },
      { name: 'ai24x_auth_user', value: encodeURIComponent(JSON.stringify({ id: 1, email: 'oauth@example.com' })), url: 'http://127.0.0.1:8000' },
    ]);
    await page.goto('http://127.0.0.1:8000/index.html?lang=en&x=q4', { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    const st = await page.evaluate(() => ({
      token: localStorage.getItem('ai24x_auth_token') || '',
      user: localStorage.getItem('ai24x_auth_user') || '',
    }));
    check('sync.cookie_to_localstorage', st.token === 'sync-cookie-token', st.token);
    check('sync.user_saved', st.user.indexOf('oauth@example.com') >= 0, st.user);
    await ctx.clearCookies();
    await page.close();
  }

  // ---------- console 恢复 OAuth 会话：cookie 登录态不被踢回 login ----------
  {
    const page = await ctx.newPage();
    await ctx.addCookies([
      { name: 'ai24x_auth_token', value: 'console-oauth-token', url: 'http://127.0.0.1:8000' },
      { name: 'ai24x_auth_user', value: encodeURIComponent(JSON.stringify({ id: 1, email: 'console@example.com' })), url: 'http://127.0.0.1:8000' },
    ]);
    await page.route('**/api/me', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, data: { id: 1, email: 'console@example.com' } }) })
    );
    await page.route('**/v1/billing/balance', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ balance_usd: 0, balance_tokens: 0, plan: 'free', is_vip_active: false, is_value_pack_active: false, shared_enabled: true, shared_remain_tokens: 0, shared_daily_token_cap: 100000, email: 'console@example.com' }) })
    );
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: false }) })
    );
    await page.goto('http://127.0.0.1:8000/console.html?lang=en&x=q6', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const st = await page.evaluate(() => ({
      href: location.href,
      token: localStorage.getItem('ai24x_auth_token') || '',
      signedIn: !!document.querySelector('.auth-user, #auth-user, [data-page="console"] .auth-user'),
      bodyHasLogin: (document.body.innerText || '').indexOf('Log in') >= 0,
    }));
    check('console.oauth_session_restored', st.href.indexOf('login.html') === -1 && st.token === 'console-oauth-token', st.href);
    await ctx.clearCookies();
    await page.close();
  }

  // ---------- register OAuth 回跳：cookie → localStorage → 跳 next ----------
  {
    const page = await ctx.newPage();
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: false }) })
    );
    await ctx.addCookies([
      { name: 'ai24x_auth_token', value: 'oauth-test-token', url: 'http://127.0.0.1:8000' },
      { name: 'ai24x_auth_user', value: 'user%40example.com', url: 'http://127.0.0.1:8000' },
    ]);
    await page.goto('http://127.0.0.1:8000/register.html?next=index.html#oauth=1', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const st = await page.evaluate(() => ({
      href: location.href,
      token: localStorage.getItem('ai24x_auth_token') || '',
      user: localStorage.getItem('ai24x_auth_user') || '',
    }));
    check('register.oauth_redirect', st.href.indexOf('index.html') >= 0, st.href);
    check('register.oauth_token_saved', st.token === 'oauth-test-token', st.token);
    check('register.oauth_user_saved', st.user === 'user@example.com', st.user);
    await ctx.clearCookies();
    await page.close();
  }

  // ---------- 全站 locales 版本：d 统一、c 残留 0 ----------
  {
    const pages = [
      'http://127.0.0.1:8000/register.html?x=q5',
      'http://127.0.0.1:8000/login.html?x=q5',
      'http://127.0.0.1:8000/index.html?x=q5',
      'http://127.0.0.1:8000/pricing.html?x=q5',
      'http://127.0.0.1:8000/help.html?x=q5',
    ];
    let allJ = true, anyC = false;
    for (const u of pages) {
      const res = await (await fetch(u)).text();
      if (!res.includes('locales.js?v=20260818j')) allJ = false;
      if (res.includes('locales.js?v=20260818c')) anyC = true;
    }
    check('www.locales_v18j_uniform', allJ, pages.join(','));
    check('www.locales_old_c_residual', !anyC, '');
  }

  await browser.close();
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== ' + failed + ' FAILED ===');
  process.exit(failed === 0 ? 0 : 1);
})();
