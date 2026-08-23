// QA 2026-08-23：www pricing.html BYOK 套餐区（桌面 / 中文 / 手机，无 JS 错误）
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

  // ---------- 桌面 EN ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:8000/pricing.html?lang=en&x=b1', { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    const en = await page.evaluate(() => {
      const sec = document.querySelector('#byokSection');
      const cards = Array.from(sec ? sec.querySelectorAll('.plan-card') : []);
      const prices = cards.map((c) => (c.querySelector('.plan-price strong') || {}).textContent || '');
      const ctas = cards.map((c) => {
        const a = c.querySelector('.plan-actions a');
        return a ? a.getAttribute('href') : '';
      });
      const rec = cards.map((c) => c.classList.contains('is-rec'));
      const badges = cards.map((c) => (c.querySelector('.plan-rec-badge') || {}).textContent || '');
      return {
        hasSec: !!sec,
        cardCount: cards.length,
        prices,
        ctas,
        rec,
        badges,
        heading: (sec ? sec.querySelector('h2') : null) ? sec.querySelector('h2').textContent.trim() : '',
      };
    });
    check('byok.section_present', en.hasSec);
    check('byok.two_cards', en.cardCount === 2, 'cards=' + en.cardCount);
    check('byok.prices_9_9_99', en.prices.join(',') === '$9.9,$99', en.prices.join(','));
    check('byok.ctas_open_pricing', en.ctas.every((h) => h && h.indexOf('/pricing.html') >= 0 && h.indexOf('127.0.0.1') >= 0), en.ctas.join('|'));
    check('byok.yearly_recommended', en.rec.join(',') === 'false,true' && en.badges[1] === 'Save 17%', en.rec.join(',') + '|' + en.badges.join(','));
    check('byok.en_heading', en.heading === 'BYOK smart gateway · open.ai24x.com', en.heading);
    check('byok.no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await ctx.close();
  }

  // ---------- www 合规：强制英文（?lang=zh 不再生效，2026-08-17 红线） ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:8000/pricing.html?lang=zh&x=b2', { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    const en2 = await page.evaluate(() => {
      const sec = document.querySelector('#byokSection');
      const h2 = sec ? sec.querySelector('h2') : null;
      const cards = Array.from(sec ? sec.querySelectorAll('.plan-card') : []);
      const titles = cards.map((c) => (c.querySelector('h3') || {}).textContent || '');
      return {
        heading: h2 ? h2.textContent.trim() : '',
        titles,
        langSelect: !!document.getElementById('lang-select'),
      };
    });
    check('byok.force_en_heading', en2.heading === 'BYOK smart gateway · open.ai24x.com', en2.heading);
    check('byok.force_en_titles', en2.titles.join(',') === 'BYOK Pro · Monthly,BYOK Pro · Yearly', en2.titles.join(','));
    check('byok.force_en_no_lang_selector', !en2.langSelect, '');
    check('byok.force_en_no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await ctx.close();
  }

  // ---------- 手机 375px ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:8000/pricing.html?lang=en&x=b3', { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    const m = await page.evaluate(() => {
      const sec = document.querySelector('#byokSection');
      return {
        hasSec: !!sec,
        scrollW: document.documentElement.scrollWidth,
        clientW: document.documentElement.clientWidth,
        cardCount: sec ? sec.querySelectorAll('.plan-card').length : 0,
      };
    });
    check('byok.mobile_section', m.hasSec && m.cardCount === 2, 'cards=' + m.cardCount);
    check('byok.mobile_no_hscroll', m.scrollW <= m.clientW, 'scroll=' + m.scrollW + ' client=' + m.clientW);
    check('byok.mobile_no_js_errors', errors.length === 0, errors.join(' || ').slice(0, 200));
    await ctx.close();
  }

  await browser.close();
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== ' + failed + ' FAILED ===');
  process.exit(failed === 0 ? 0 : 1);
})().catch((e) => {
  console.error('QA CRASH', e);
  process.exit(1);
});
