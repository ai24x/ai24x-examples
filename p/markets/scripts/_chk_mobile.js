// QA: 各视口下 app.html 首屏K线数量/图表高度（需本机 18012 运行中）
// 用法: set NODE_PATH=...\node_modules && node _chk_mobile.js
const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const cases = [
    { name: 'iPhone SE 375x667', w: 375, h: 667 },
    { name: 'Pixel 412x915', w: 412, h: 915 },
    { name: 'iPhone landscape 812x375', w: 812, h: 375 },
    { name: 'Desktop 1280x800', w: 1280, h: 800 },
  ];
  for (const vp of cases) {
    const page = await browser.newPage({ viewport: { width: vp.w, height: vp.h } });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    const r = await page.evaluate(() => {
      const main = document.getElementById('chart-main');
      return {
        innerWidth: window.innerWidth,
        chartW: main ? main.clientWidth : 0,
        chartH: main ? main.clientHeight : 0,
        mk: window.__mkChart ? window.__mkChart() : null,
      };
    });
    const vr = r.mk && r.mk.mainVr;
    const visibleBars = vr && vr.to ? Math.round(vr.to - vr.from) : null;
    console.log(
      vp.name,
      '| width', r.innerWidth,
      '| chart', r.chartW + 'x' + r.chartH,
      '| visible', visibleBars,
      '| total', r.mk ? r.mk.mainBars : '?',
      '| errors', errors.length ? errors.slice(0, 2) : 'none'
    );
    await page.close();
  }
  await browser.close();
})();
