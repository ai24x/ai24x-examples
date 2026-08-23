// QA 2026-08-17：www Markets 主打重构（导航/定价/产品/首页）+ markets 深链订阅 + Google/Apple 按钮
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

  // ---------- www：pricing 导航 + 卡片 + 开发者区 ----------
  {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:8000/pricing.html?x=q1', { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);

    const nav = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('.nav-main a')).map((a) => ({
        href: a.getAttribute('href'),
        text: (a.textContent || '').trim(),
      }));
      const dropBtn = document.querySelector('.nav-drop-btn');
      const menu = document.querySelector('.nav-drop-menu');
      return {
        links,
        dropBtnText: dropBtn ? dropBtn.textContent.trim() : null,
        menuLinks: menu ? Array.from(menu.querySelectorAll('a')).map((a) => a.getAttribute('href')) : [],
      };
    });
    check('nav.home_first', nav.links[0] && nav.links[0].href && nav.links[0].href.indexOf('index.html') >= 0 && nav.links[0].text === 'Home', JSON.stringify(nav.links.slice(0, 3)));
    const devLink = nav.links.find((l) => l.href && l.href.indexOf('open.ai24x.com') >= 0);
    check('nav.no_developer', !devLink && !nav.dropBtnText, devLink ? devLink.text : 'no-dev-link');
    check('nav.no_dropdown', !nav.dropBtnText && nav.menuLinks.length === 0, nav.dropBtnText + ' | ' + nav.menuLinks.join(','));
    check('nav.no_token_entries', !nav.links.some((l) => (l.text || '').indexOf('Console') >= 0 || (l.text || '').indexOf('Markets') >= 0 || (l.text || '').indexOf('行情官') >= 0), JSON.stringify(nav.links.map((l) => l.text)));
    check('nav.signup_present', nav.links.some((l) => l.href && l.href.indexOf('register.html') >= 0 && l.text === 'Sign up'), JSON.stringify(nav.links.map((l) => l.text)));
    check('nav.about_login_present', nav.links.some((l) => l.text === 'About') && nav.links.some((l) => l.text === 'Log in'), JSON.stringify(nav.links.map((l) => l.text)));

    const body = await page.evaluate(() => {
      const txt = (sel) => (document.querySelector(sel) || {}).textContent || '';
      const hrefs = Array.from(document.querySelectorAll('a[href*="console.html"]')).map((a) => a.getAttribute('href'));
      return {
        free: txt('.plan-card h3') || '',
        prices: document.body.innerText.match(/\$9\.9|\$24\.9|\$199/g) || [],
        upgradeHrefs: hrefs.filter((h) => h && /^console\.html\?plan=(weekly|monthly|yearly)#billing$/.test(h)),
        devSection: !!document.getElementById('devSection'),
        tokenGrid: !!document.getElementById('tokenPlansGrid'),
        devOpenLink: Array.from(document.querySelectorAll('#devSection a')).map((a) => a.getAttribute('href')),
      };
    });
    check('pricing.free_card', body.free === 'Free', body.free);
    check('pricing.prices', body.prices.length >= 3 && body.prices.indexOf('$9.9') >= 0 && body.prices.indexOf('$24.9') >= 0 && body.prices.indexOf('$199') >= 0, body.prices.join(','));
    check('pricing.upgrade_deeplinks', body.upgradeHrefs.length >= 3 && body.upgradeHrefs.some((h) => h.indexOf('plan=yearly') >= 0), body.upgradeHrefs.join(' | '));
    check('pricing.dev_section', body.devSection && !body.tokenGrid && body.devOpenLink.some((h) => h && h.indexOf('127.0.0.1:18080') >= 0), body.devOpenLink.join(','));
    check('pricing.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await page.close();
  }

  // ---------- www：官网仅英文（?lang=zh 不再生效） ----------
  {
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:8000/pricing.html?lang=zh&x=q2', { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    const en = await page.evaluate(() => ({
      nav: Array.from(document.querySelectorAll('.nav-main a')).map((a) => a.textContent.trim()).filter(Boolean).slice(0, 6),
      langSelect: !!document.getElementById('lang-select'),
      devTitle: (document.querySelector('#devSection h2') || {}).textContent || '',
    }));
    check('en.nav_home', en.nav[0] === 'Home', en.nav.join('|'));
    check('en.no_lang_selector', !en.langSelect, '');
    check('en.dev_title', en.devTitle.indexOf('open.ai24x.com') >= 0, en.devTitle);
    await page.close();
  }

  // ---------- www：index / product / help ----------
  {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:8000/index.html?lang=en&x=q3', { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    const idx = await page.evaluate(() => {
      const hero = document.querySelector('.hero-cta a.btn-primary');
      const fleet = document.body.innerText.indexOf('Powered by the AI24X autonomous agent fleet') >= 0;
      return { heroHref: hero ? hero.getAttribute('href') : null, heroText: hero ? hero.textContent.trim() : '', fleet };
    });
    check('index.hero_start_free', idx.heroHref === 'http://127.0.0.1:18012/app.html' && idx.heroText === 'Start free', idx.heroHref + ' ' + idx.heroText);
    check('index.fleet_line', idx.fleet, '');
    check('index.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 150));
    await page.close();
  }
  {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:8000/product.html?lang=en&x=q4', { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    const prod = await page.evaluate(() => {
      const h3s = Array.from(document.querySelectorAll('.product-entry h3, section h3')).map((h) => h.textContent.trim());
      const marketsCard = Array.from(document.querySelectorAll('.card')).find((c) => (c.textContent || '').indexOf('markets.ai24x.com') >= 0);
      return { h3s, marketsCardFull: !!marketsCard && marketsCard.getAttribute('style') && marketsCard.getAttribute('style').indexOf('1/-1') >= 0 };
    });
    check('product.markets_fullwidth', prod.marketsCardFull, '');
    check('product.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 150));
    await page.close();
  }
  {
    const res = await (await fetch('http://127.0.0.1:8000/help.html?lang=en&x=q5')).text();
    check('help.price_fixed', res.includes('$24.9/month or $199/year') && !res.includes('$14.9'), '');
  }

  // ---------- markets app：深链订阅高亮 + Google/Apple 按钮（模拟 providers） ----------
  {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.route('**/v1/auth/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google: true, apple: true }) })
    );
    await page.goto('http://127.0.0.1:18012/app.html?plan=yearly#sub', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    let highlight = '';
    try {
      await page.waitForFunction(() => {
        const b = document.getElementById('btn-sub-year');
        return b && b.style.boxShadow && b.style.boxShadow.indexOf('--accent') >= 0;
      }, { timeout: 6000 });
      highlight = 'ok';
    } catch (e) {}
    const mk = await page.evaluate(() => {
      const social = Array.from(document.querySelectorAll('.social-login a')).map((a) => ({ text: a.textContent.trim(), href: a.getAttribute('href') }));
      const subPanel = document.getElementById('sub');
      const btnYear = document.getElementById('btn-sub-year');
      const rect = subPanel ? subPanel.getBoundingClientRect() : null;
      return {
        social,
        hash: location.hash,
        plan: new URLSearchParams(location.search).get('plan'),
        highlight: btnYear ? btnYear.style.boxShadow : '',
        subInViewport: !!(rect && rect.top >= -50 && rect.top < window.innerHeight),
      };
    });
    check('markets.social_buttons', mk.social.length >= 2 && mk.social.some((s) => s.text === 'Google') && mk.social.some((s) => s.text === 'Apple'), JSON.stringify(mk.social));
    check('markets.deeplink_state', mk.plan === 'yearly' && (mk.hash === '#sub' || mk.hash === ''), mk.plan + ' ' + mk.hash);
    check('markets.year_highlight', highlight === 'ok', highlight);
    check('markets.sub_in_viewport', mk.subInViewport, '');
    check('markets.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await page.close();
  }

  // ---------- core /v1/auth/providers 真实端点 ----------
  {
    const r = await fetch('http://127.0.0.1:8000/v1/auth/providers');
    const j = await r.json();
    check('core.providers_endpoint', r.status === 200 && typeof j.google === 'boolean' && typeof j.apple === 'boolean', JSON.stringify(j));
  }

  await browser.close();
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== ' + failed + ' FAILED ===');
  process.exit(failed === 0 ? 0 : 1);
})();
