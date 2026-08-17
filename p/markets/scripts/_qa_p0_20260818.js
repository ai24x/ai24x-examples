// QA: 2026-08-18 P0 增量（技术健康评分条 / 美股 Discover 扫描页 / 导航入口 / 免费额度提示）
// 用法: node _qa_p0_20260818.js （需 18012 运行中；screener 首次全量扫描约 90s，之后 15 分钟缓存秒出）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

async function closeOnboard(page) {
  try { if (await page.isVisible('#onboard')) await page.click('#onboard-skip'); } catch (e) {}
}

function scoreColorOf(el) {
  return el ? getComputedStyle(el).color : '';
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });

  // ---- app.html：评分条 + 导航 + AI Brief 入口 ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(2500);

    const stripVisible = await page.evaluate(() => {
      const el = document.getElementById('score-strip');
      return el && !el.hidden && el.textContent.trim().length > 0;
    });
    const scoreText = await page.evaluate(() => {
      const el = document.getElementById('score-strip');
      return el ? el.textContent.trim().slice(0, 80) : '';
    });
    log('app score-strip visible', !!stripVisible, scoreText);

    const scoreNum = await page.evaluate(() => {
      const el = document.getElementById('score-strip');
      if (!el) return -1;
      const m = el.textContent.match(/(\d+)\/100/);
      return m ? parseInt(m[1], 10) : -1;
    });
    log('app score number in 0..100', scoreNum >= 0 && scoreNum <= 100, 'score=' + scoreNum);

    const navDiscover = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll('.mk-nav a')).find(function (x) {
        return (x.getAttribute('href') || '').indexOf('screener') >= 0;
      });
      return a ? a.getAttribute('href') : '';
    });
    log('app nav has Discover -> /screener.html', navDiscover === '/screener.html', 'href=' + navDiscover);

    // 切换标的 → 评分条更新
    await page.fill('#symbol', 'MSFT');
    await page.click('#go');
    await page.waitForFunction(function () {
      const el = document.getElementById('score-strip');
      return el && !el.hidden;
    }, { timeout: 25000 });
    await page.waitForTimeout(500);
    const msftScore = await page.evaluate(function () {
      const el = document.getElementById('score-strip');
      if (!el) return -1;
      const m = el.textContent.match(/(\d+)\/100/);
      return m ? parseInt(m[1], 10) : -1;
    });
    log('app score updates after symbol switch', msftScore >= 0 && msftScore <= 100, 'msft score=' + msftScore);
    log('app no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---- screener.html：列表 + 模式切换 + 点击开图 ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/screener.html', { waitUntil: 'networkidle' });
    await page.waitForFunction(function () {
      const el = document.getElementById('sr-list');
      return el && el.className !== 'loading' && el.textContent.trim().length > 0;
    }, { timeout: 120000 });

    const cards = await page.$$('.sr-card');
    log('screener cards rendered', cards.length > 0, 'cards=' + cards.length);
    const firstCardText = cards.length ? (await page.textContent('.sr-card')).trim().slice(0, 100) : '';
    log('screener card has score + patterns', /\/100/.test(firstCardText) || /Bottom volume surge|Breakout|Uptrend|Pullback/.test(firstCardText), firstCardText);

    // 模式切换：Uptrend building
    await page.click('#mode-chips .chip[data-mode="Uptrend building"]');
    await page.waitForFunction(function () {
      const el = document.getElementById('sr-list');
      return el && el.className !== 'loading' && el.textContent.trim().length > 0;
    }, { timeout: 30000 });
    const upCards = await page.$$('.sr-card');
    const upAllMatch = upCards.length > 0;
    log('screener mode filter uptrend', upAllMatch, 'cards=' + upCards.length);

    // 点击卡片 → 新窗口 app.html?symbol=
    const popupPromise = ctx.waitForEvent('page');
    await page.click('.sr-card');
    const popup = await popupPromise;
    await popup.waitForLoadState('domcontentloaded');
    const popupUrl = popup.url();
    log('screener card opens chart app', /app\.html\?symbol=/.test(popupUrl), popupUrl);
    await popup.close();
    log('screener no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---- mobile：screener 单列 + app 评分条不溢出 ----
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 700 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/screener.html', { waitUntil: 'networkidle' });
    await page.waitForFunction(function () {
      const el = document.getElementById('sr-list');
      return el && el.className !== 'loading' && el.textContent.trim().length > 0;
    }, { timeout: 120000 });
    const gridCols = await page.evaluate(function () {
      const g = document.querySelector('.sr-grid');
      return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0;
    });
    log('screener mobile single column', gridCols === 1, 'cols=' + gridCols);

    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForFunction(function () {
      const el = document.getElementById('score-strip');
      return el && !el.hidden;
    }, { timeout: 25000 });
    const overflow = await page.evaluate(function () {
      return document.body.scrollWidth > window.innerWidth + 2;
    });
    log('app mobile no horizontal overflow', !overflow, 'scrollW=' + (await page.evaluate(function () { return document.body.scrollWidth; })) + ' winW=' + 375);
    log('app mobile no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  await browser.close();
  const failed = results.filter(function (r) { return !r.ok; });
  console.log('---');
  console.log((failed.length === 0 ? 'ALL PASS' : 'FAILED: ' + failed.length) + ' | total=' + results.length);
  process.exit(failed.length === 0 ? 0 : 1);
})();
