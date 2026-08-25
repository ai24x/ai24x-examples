const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');
const fs = require('fs');
const path = require('path');

let pass = 0, fail = 0;
const errs = [];
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('PASS ' + name); }
  else { fail++; console.log('FAIL ' + name + (extra ? ' :: ' + extra : '')); }
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
  });

  // www 公共页头部 CTA（pricing 无需登录）
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on('pageerror', (e) => errs.push('www pricing pageerror: ' + e.message));
    await page.goto('http://127.0.0.1:8000/pricing.html', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.header-upgrade', { timeout: 5000 });
    const txt = (await page.textContent('.header-upgrade')).trim();
    ok('www: header cta text Upgrade to Pro', /Upgrade to Pro/.test(txt), txt);
    const href = await page.locator('.header-upgrade').getAttribute('href');
    ok('www: header cta href -> billing', /console\.html#billing/.test(href), href);
    await page.close();
  }

  // www console 页头部 CTA（登录守卫前也渲染 shell）
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on('pageerror', (e) => errs.push('www console pageerror: ' + e.message));
    await page.goto('http://127.0.0.1:8000/console.html', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.header-upgrade', { timeout: 5000 });
    const txt = (await page.textContent('.header-upgrade')).trim();
    ok('www console: header cta text Upgrade to Pro', /Upgrade to Pro/.test(txt), txt);
    await page.close();
  }

  // markets 首页 pill 桌面
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on('pageerror', (e) => errs.push('markets index desktop pageerror: ' + e.message));
    await page.goto('http://127.0.0.1:18012/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.upgrade-pill', { timeout: 5000 });
    const txt = (await page.textContent('.upgrade-pill')).trim();
    ok('markets index: pill text Upgrade to Pro', /Upgrade to Pro/.test(txt), txt);
    const href = await page.locator('.upgrade-pill').getAttribute('href');
    ok('markets index: pill href app#sub', href === '/app.html#sub', href);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    ok('markets index: no horizontal overflow', !overflow);
    await page.close();
  }

  // markets 首页 pill 手机
  {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
    page.on('pageerror', (e) => errs.push('markets index mobile pageerror: ' + e.message));
    await page.goto('http://127.0.0.1:18012/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.upgrade-pill', { timeout: 5000 });
    const txt = (await page.textContent('.upgrade-pill')).trim();
    ok('markets index mobile: pill text', /Upgrade to Pro/.test(txt), txt);
    const pillVisible = await page.isVisible('.upgrade-pill');
    ok('markets index mobile: pill visible', pillVisible);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    ok('markets index mobile: no horizontal overflow', !overflow);
    await page.close();
  }

  // locales 键
  {
    const locales = fs.readFileSync(path.join(__dirname, '..', '..', '..', 'web', 'config', 'locales.js'), 'utf8');
    ok('locales: nav.goPro zh', locales.includes('"nav.goPro": "升级 Pro"'));
    ok('locales: nav.goPro en', locales.includes('"nav.goPro": "Upgrade to Pro"'));
    ok('locales: nav.vipUpgrade removed', !locales.includes('"nav.vipUpgrade"'));
  }

  await browser.close();
  console.log('----');
  console.log('RESULT ' + pass + ' pass / ' + fail + ' fail');
  if (errs.length) {
    console.log('PAGEERRORS:');
    errs.slice(0, 10).forEach((e) => console.log('  ' + e));
  }
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('QA_CRASH ' + e); process.exit(2); });
