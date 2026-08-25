const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const BASE = 'http://127.0.0.1:18012';
let pass = 0, fail = 0;
const errors = [];
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('PASS ' + name); }
  else { fail++; console.log('FAIL ' + name + (extra ? ' :: ' + extra : '')); }
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
  });

  // 1. index.html desktop
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on('pageerror', (e) => errors.push('index-desktop pageerror: ' + e.message));
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#mk-hw-fab', { timeout: 5000 });
    ok('index: fab visible', await page.isVisible('#mk-hw-fab'));
    await page.click('#mk-hw-fab');
    await page.waitForSelector('#mk-hw-panel:not([hidden])', { timeout: 3000 });
    ok('index: panel opens', true);
    const title = await page.textContent('#mk-hw-panel h4');
    ok('index: panel title', /How can we help/.test(title), title);
    const faqCount = await page.locator('.mk-hw-faq-item').count();
    ok('index: faq items 4', faqCount === 4, String(faqCount));
    const linkCount = await page.locator('.mk-hw-link').count();
    ok('index: quick links 4', linkCount === 4, String(linkCount));
    const pricingHref = await page.locator('.mk-hw-link', { hasText: 'Pricing' }).getAttribute('href');
    ok('index: pricing local', pricingHref === '/pricing.html', pricingHref);
    const helpHref = await page.locator('.mk-hw-link', { hasText: 'Help Center' }).getAttribute('href');
    ok('index: help env-aware local', helpHref.indexOf('127.0.0.1:8000') >= 0, helpHref);
    // toggle first FAQ
    await page.click('.mk-hw-faq-q');
    ok('index: faq answer opens', await page.locator('.mk-hw-faq-item.is-open .mk-hw-faq-a').isVisible());
    await page.keyboard.press('Escape');
    ok('index: esc closes', await page.isHidden('#mk-hw-panel'));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    ok('index: no horizontal overflow', !overflow);
    await page.close();
  }

  // 2. app.html desktop
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on('pageerror', (e) => errors.push('app-desktop pageerror: ' + e.message));
    await page.goto(BASE + '/app.html', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#mk-hw-fab', { timeout: 5000 });
    await page.evaluate(() => { const b = document.querySelector('#onboard-skip'); if (b) b.click(); });
    await page.waitForSelector('#onboard', { state: 'hidden', timeout: 5000 }).catch(() => {});
    ok('app: fab visible', await page.isVisible('#mk-hw-fab'));
    await page.click('#mk-hw-fab');
    await page.waitForSelector('#mk-hw-panel:not([hidden])', { timeout: 3000 });
    ok('app: panel opens', true);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    ok('app: no horizontal overflow', !overflow);
    await page.close();
  }

  // 3. app.html mobile — fab lifted above bottom action bar
  {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
    page.on('pageerror', (e) => errors.push('app-mobile pageerror: ' + e.message));
    await page.goto(BASE + '/app.html', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#mk-hw-fab', { timeout: 5000 });
    await page.evaluate(() => { const b = document.querySelector('#onboard-skip'); if (b) b.click(); });
    await page.waitForSelector('#onboard', { state: 'hidden', timeout: 5000 }).catch(() => {});
    await page.waitForSelector('.mb-bar', { timeout: 5000 });
    const fabBottom = await page.evaluate(() => getComputedStyle(document.querySelector('#mk-hw-fab')).bottom);
    ok('app: mobile fab lifted above mb-bar', /78px/.test(fabBottom), fabBottom);
    const mbBarTop = await page.evaluate(() => {
      const r = document.querySelector('.mb-bar').getBoundingClientRect();
      return r.top;
    });
    const fabBottomGeo = await page.evaluate(() => {
      const r = document.querySelector('#mk-hw-fab').getBoundingClientRect();
      return r.bottom;
    });
    ok('app: fab above mb-bar geometrically', fabBottomGeo <= mbBarTop + 2, 'fabBottom=' + fabBottomGeo + ' mbBarTop=' + mbBarTop);
    await page.click('#mk-hw-fab');
    await page.waitForSelector('#mk-hw-panel:not([hidden])', { timeout: 3000 });
    const panelRect = await page.evaluate(() => {
      const r = document.querySelector('#mk-hw-panel').getBoundingClientRect();
      return { left: r.left, right: r.right, width: r.width, vw: window.innerWidth };
    });
    ok('app: mobile panel fits viewport', panelRect.left >= 0 && panelRect.right <= panelRect.vw + 1,
      JSON.stringify(panelRect));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    ok('app-mobile: no horizontal overflow', !overflow);
    await page.close();
  }

  // 4. index.html mobile
  {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
    page.on('pageerror', (e) => errors.push('index-mobile pageerror: ' + e.message));
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#mk-hw-fab', { timeout: 5000 });
    await page.click('#mk-hw-fab');
    await page.waitForSelector('#mk-hw-panel:not([hidden])', { timeout: 3000 });
    const rect = await page.evaluate(() => {
      const r = document.querySelector('#mk-hw-panel').getBoundingClientRect();
      return { left: r.left, right: r.right, vw: window.innerWidth };
    });
    ok('index-mobile: panel fits', rect.left >= 0 && rect.right <= rect.vw + 1, JSON.stringify(rect));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    ok('index-mobile: no horizontal overflow', !overflow);
    await page.close();
  }

  // 5. zh language
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.goto(BASE + '/app.html', { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => localStorage.setItem('markets_lang', 'zh'));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#mk-hw-fab', { timeout: 5000 });
    await page.evaluate(() => { const b = document.querySelector('#onboard-skip'); if (b) b.click(); });
    await page.waitForSelector('#onboard', { state: 'hidden', timeout: 5000 }).catch(() => {});
    await page.click('#mk-hw-fab');
    await page.waitForSelector('#mk-hw-panel:not([hidden])', { timeout: 3000 });
    const zhTitle = await page.textContent('#mk-hw-panel h4');
    ok('zh: panel localized', /需要帮忙吗/.test(zhTitle), zhTitle);
    const zhLink = await page.locator('.mk-hw-link', { hasText: '账户与套餐' }).count();
    ok('zh: links localized', zhLink === 1, String(zhLink));
    await page.close();
  }

  await browser.close();
  console.log('----');
  console.log('RESULT ' + pass + ' pass / ' + fail + ' fail');
  if (errors.length) {
    console.log('PAGEERRORS (' + errors.length + '):');
    errors.slice(0, 10).forEach((e) => console.log('  ' + e));
  }
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('QA_CRASH ' + e); process.exit(2); });
