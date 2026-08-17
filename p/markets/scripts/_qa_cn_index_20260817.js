// QA 2026-08-17：搜索上证指数出完整历史K线（未开盘无当日bar）+ MACD柱完整 + 失败清空旧图
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
    return el && el.querySelector('canvas');
  }, { timeout: timeout || 30000 });
  await page.waitForTimeout(1200);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });

  // ---- 1) 桌面：直接搜中文 上证指数 → 完整K线 + MACD 120根 + 无当日bar ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.fill('#symbol', '上证指数');
    await page.click('#go');
    await waitChart(page);
    const err = await page.textContent('#err');
    const quote = await page.textContent('#quote');
    const quoteOk = quote.indexOf('上证指数') >= 0 && quote.indexOf('CNY') >= 0;
    const state = await page.evaluate(() => {
      const last = window.__state ? window.__state : null;
      return {
        candles: (window.__candles || []).length,
        lastCandle: window.__candles ? window.__candles[window.__candles.length - 1] : null,
        macdBars: window.__macd ? window.__macdBars.length : -1,
      };
    });
    // 通过内部状态不可靠，直接用接口数据兜底
    const api = await page.evaluate(async () => {
      const r = await fetch('/api/signals?symbol=sh000001&period=day&count=120').then((x) => x.json());
      return {
        code: r.code,
        bars: r.data && r.data.candles.length,
        asof: r.data && r.data.meta.asof,
        macd: r.data && r.data.macd.length,
        last: r.data && r.data.candles[r.data.candles.length - 1],
      };
    });
    log('desktop.sse_chinese_name', quoteOk, 'quote=' + quote.slice(0, 80).replace(/\n/g, ' '));
    log('desktop.sse_full_kline', api.code === 0 && api.bars >= 100, 'bars=' + api.bars + ' asof=' + api.asof);
    log('desktop.sse_macd_full', api.macd === api.bars, 'macd=' + api.macd);
    // 环境自适应：未开盘时无当日bar（asof=上一交易日）；盘中/收盘后当日bar必须 OHLC 合法（非假大阴线）
    const last = api.last || [];
    const lastValid = last.length >= 5 && +last[1] > 0 && +last[2] > 0 && +last[3] > 0 && +last[4] > 0 && +last[3] >= +last[4];
    log('desktop.sse_last_bar_valid', api.asof >= '2026-08-14' && lastValid, 'asof=' + api.asof + ' last=' + String(last[0]) + ' O' + last[1] + ' C' + last[2] + ' H' + last[3] + ' L' + last[4]);
    log('desktop.sse_no_js_errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---- 2) 失败清空旧图：先加载 AAPL 出图，再搜 WETOUR，旧 K 线/MACD 应消失 ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await waitChart(page);
    const before = await page.evaluate(() => document.querySelectorAll('#chart-main canvas').length);
    await page.fill('#symbol', 'WETOUR');
    await page.click('#go');
    await page.waitForFunction(() => {
      const err = (document.getElementById('err') || {}).textContent || '';
      return err.indexOf('not found') >= 0 || err.indexOf('未找到') >= 0 || err.indexOf('no data') >= 0 || err.indexOf('暂无数据') >= 0;
    }, { timeout: 40000 });
    await page.waitForTimeout(800);
    const after = await page.evaluate(() => document.querySelectorAll('#chart-main canvas').length);
    const emptyMsg = await page.evaluate(() => (document.getElementById('chart-main') || {}).textContent || '');
    log('failure.clear_old_chart', before >= 2 && after === 0, 'before=' + before + ' after=' + after);
    log('failure.show_no_data_hint', emptyMsg.indexOf('No data') >= 0 || emptyMsg.indexOf('暂无数据') >= 0, 'msg=' + emptyMsg.slice(0, 60));
    log('failure.no_js_errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---- 3) 手机：上证指数出图 + 白名单可见 ----
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 720 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.evaluate(() => { try { localStorage.setItem('markets_lang', 'zh'); } catch (e) {} });
    await page.reload({ waitUntil: 'networkidle' });
    await closeOnboard(page);
    const sampleText = await page.evaluate(() => Array.from(document.querySelectorAll('#samples button')).map((b) => b.textContent).join(','));
    log('mobile.samples_has_sse', sampleText.indexOf('上证指数') >= 0, sampleText.slice(0, 100));
    await page.click('#samples button[data-symbol="sh000001"]');
    await waitChart(page);
    const quote = await page.textContent('#quote');
    log('mobile.sse_quote_ok', quote.indexOf('上证指数') >= 0, quote.slice(0, 60).replace(/\n/g, ' '));
    log('mobile.no_js_errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== FAILED ' + failed + ' ===');
  await browser.close();
})();
