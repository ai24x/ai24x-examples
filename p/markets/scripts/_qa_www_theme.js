// QA 2026-08-16：www 主页深色默认、其它页仍蓝白、无 JS 报错
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const pages = [
  { url: 'http://127.0.0.1:8000/', expectDark: true },
  { url: 'http://127.0.0.1:8000/pricing.html', expectDark: false },
  { url: 'http://127.0.0.1:8000/product.html', expectDark: false },
  { url: 'http://127.0.0.1:8000/help.html', expectDark: false },
  { url: 'http://127.0.0.1:8000/login.html', expectDark: false },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  let failed = 0;
  for (const p of pages) {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(p.url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    const cls = await page.evaluate(() => document.body.className);
    const dark = cls.indexOf('theme-dark') >= 0;
    const ok = dark === p.expectDark && errors.length === 0;
    if (!ok) failed++;
    console.log((ok ? 'PASS' : 'FAIL') + ' | ' + p.url + ' | class=' + cls + ' | jsErrors=' + errors.length);
    await page.close();
  }
  await browser.close();
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== ' + failed + ' FAILED ===');
  process.exit(failed === 0 ? 0 : 1);
})();
