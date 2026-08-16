// QA: 2026-08-16 优化回归（RSI移除/成交量/首屏根数/WETOUR建议/语言切换/登录排版）
// 注意：K 线默认根数保持 250（雷总 2026-08-16 验收口径），勿改回 500。
// 用法: set NODE_PATH=...\node_modules && node _qa_opt.js （需 18012 运行中）
const { chromium } = require('playwright-core');

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

async function closeOnboard(page) {
  try {
    if (await page.isVisible('#onboard')) await page.click('#onboard-skip');
  } catch (e) {}
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });

  // ---- Desktop ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1500);

    const mk = await page.evaluate(() => window.__mkChart());
    log('desktop no rsi chart', !(await page.$('#chart-rsi')), '');
    log('desktop volume visible', await page.isVisible('#chart-vol'), '');
    log('desktop volume rendered', (await page.$$('#chart-vol canvas')).length > 0, 'canvases=' + (await page.$$('#chart-vol canvas')).length);
    log('desktop total bars=500', mk.mainBars === 500, 'bars=' + mk.mainBars);
    log('desktop visible ~6m', mk.visibleMain >= 120 && mk.visibleMain <= 170, 'visibleMain=' + mk.visibleMain);
    log('desktop no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));

    const firstBtn = await page.textContent('#samples button[data-symbol="^DJI"]');
    log('samples Dow Jones first', firstBtn.trim() === 'Dow Jones', 'label=' + firstBtn.trim());

    await page.fill('#symbol', 'WETOUR');
    await page.click('#go');
    await page.waitForFunction(() => {
      const t = (document.getElementById('err') || {}).textContent || '';
      return /Did you mean/.test(t);
    }, { timeout: 25000 });
    const errText = await page.textContent('#err');
    log('WETOUR did-you-mean shown', /Did you mean/.test(errText), errText.trim().slice(0, 120));
    const suggBtn = await page.$('#err button[data-suggest="WETO"]');
    if (suggBtn) {
      await suggBtn.click();
      await page.waitForFunction(() => {
        return (document.getElementById('symbol') || {}).value === 'WETO' &&
          ((document.getElementById('err') || {}).textContent || '').trim() === '';
      }, { timeout: 25000 });
      const symVal = await page.inputValue('#symbol');
      log('suggestion click loads WETO', symVal === 'WETO', 'sym=' + symVal);
    } else {
      log('suggestion click loads WETO', false, 'no suggest button');
    }

    await page.click('#lang-switch button[data-lang="zh"]');
    await page.waitForTimeout(1200);
    const title = await page.title();
    const dowLabel = await page.textContent('#samples button[data-symbol="^DJI"]');
    const placeholder = await page.getAttribute('#symbol', 'placeholder');
    log('zh title', title.includes('行情'), title);
    log('zh sample label', dowLabel.trim() === '道琼斯', dowLabel.trim());
    log('zh placeholder', placeholder.includes('代码'), placeholder);

    await ctx.addCookies([
      { name: 'ai24x_auth_token', value: 'fake', url: 'http://127.0.0.1:18012' },
      { name: 'ai24x_auth_user', value: encodeURIComponent(JSON.stringify({ email: 'lei@itxin.com' })), url: 'http://127.0.0.1:18012' },
    ]);
    await page.reload({ waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1200);
    const authHtml = await page.evaluate(() => {
      const el = document.getElementById('auth-area');
      return el ? el.innerText : '';
    });
    const authLinks = await page.$$('#auth-area .auth-link, #auth-area .auth-btn');
    log('signed-in auth area pills', authLinks.length === 2 && /lei@itxin\.com/.test(authHtml), authHtml.trim().replace(/\n/g, ' ').slice(0, 100));
    log('desktop signed-in no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---- Mobile ----
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1500);

    const mk = await page.evaluate(() => window.__mkChart());
    log('mobile no rsi chart', !(await page.$('#chart-rsi')), '');
    log('mobile volume visible', await page.isVisible('#chart-vol'), '');
    log('mobile total bars=500', mk.mainBars === 500, 'bars=' + mk.mainBars);
    log('mobile visible ~3m', mk.visibleMain >= 55 && mk.visibleMain <= 90, 'visibleMain=' + mk.visibleMain);
    log('mobile no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));

    await page.click('#lang-switch button[data-lang="zh"]');
    await page.waitForTimeout(1000);
    log('mobile zh title', (await page.title()).includes('行情'), await page.title());

    await page.fill('#symbol', 'WETOUR');
    await page.click('#go');
    await page.waitForFunction(() => {
      const t = (document.getElementById('err') || {}).textContent || '';
      return /你是不是想查/.test(t);
    }, { timeout: 25000 });
    log('mobile WETOUR did-you-mean zh', true, (await page.textContent('#err')).trim().slice(0, 100));
    log('mobile no JS errors after search', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log('SUMMARY: ' + (results.length - failed.length) + '/' + results.length + ' passed');
  process.exit(failed.length ? 1 : 0);
})().catch((e) => {
  console.error('QA crashed:', e);
  process.exit(2);
});
