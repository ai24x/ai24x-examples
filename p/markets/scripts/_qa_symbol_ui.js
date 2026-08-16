// QA 2026-08-16：中文名解析 / 错误不泄漏数据源 / 刷新停留上次标的 / 页脚去新浪
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

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

async function waitChart(page, timeout) {
  await page.waitForFunction(() => {
    const el = document.getElementById('chart-main');
    return el && (el.querySelector('canvas') || /loading/i.test(''));
  }, { timeout: timeout || 30000 });
  await page.waitForTimeout(1200);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });

  // ---- 1) 刷新停留：搜索 NVDA 后 reload，应留在 NVDA ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await waitChart(page);
    await page.fill('#symbol', 'NVDA');
    await page.click('#go');
    await page.waitForFunction(() => (document.getElementById('symbol') || {}).value === 'NVDA', { timeout: 30000 });
    await waitChart(page);
    const stored = await page.evaluate(() => localStorage.getItem('markets_last_symbol'));
    log('localStorage saved NVDA', stored === 'NVDA', 'stored=' + stored);
    await page.reload({ waitUntil: 'networkidle' });
    await closeOnboard(page);
    await waitChart(page);
    const afterReload = await page.inputValue('#symbol');
    const errEmpty = ((await page.textContent('#err')) || '').trim() === '';
    log('reload stays on NVDA', afterReload === 'NVDA' && errEmpty, 'sym=' + afterReload);
    log('reload no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---- 2) 中文名搜索 冠科美博 → 出图（解析到 APLM） ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.fill('#symbol', '冠科美博');
    await page.click('#go');
    await page.waitForFunction(() => {
      const el = document.getElementById('chart-main');
      return el && el.querySelector('canvas');
    }, { timeout: 40000 });
    await page.waitForTimeout(1000);
    const errTxt = ((await page.textContent('#err')) || '').trim();
    const mk = await page.evaluate(() => window.__mkChart());
    log('冠科美博 renders chart', mk.mainBars >= 100, 'bars=' + mk.mainBars);
    log('冠科美博 no error', errTxt === '', 'err=' + errTxt.slice(0, 80));
    await ctx.close();
  }

  // ---- 3) 不存在标的不泄漏 sina / all sources failed ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.fill('#symbol', 'ZZZZZZ');
    await page.click('#go');
    await page.waitForFunction(() => {
      const t = (document.getElementById('err') || {}).textContent || '';
      return t.trim().length > 0 && !/loading/i.test(t);
    }, { timeout: 40000 });
    const errTxt = await page.textContent('#err');
    const clean = !/sina/i.test(errTxt) && !/all sources failed/i.test(errTxt) && !/circuit open/i.test(errTxt);
    log('error clean (no sina / all sources)', clean, errTxt.trim().slice(0, 120));
    const footer = await page.textContent('footer');
    log('footer no Sina', !/Sina/i.test(footer), footer.trim().slice(0, 100));
    await ctx.close();
  }

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(failed.length === 0 ? '=== ALL PASS ===' : '=== ' + failed.length + ' FAILED ===');
  process.exit(failed.length === 0 ? 0 : 1);
})();
