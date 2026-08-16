// QA 2026-08-16：www 全站统一深色（theme-dark）、body 计算背景深色、无 JS 报错
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const pages = [
  { url: 'http://127.0.0.1:8000/', name: 'index' },
  { url: 'http://127.0.0.1:8000/pricing.html', name: 'pricing' },
  { url: 'http://127.0.0.1:8000/product.html', name: 'product' },
  { url: 'http://127.0.0.1:8000/help.html', name: 'help' },
  { url: 'http://127.0.0.1:8000/login.html', name: 'login' },
  { url: 'http://127.0.0.1:8000/register.html', name: 'register' },
  { url: 'http://127.0.0.1:8000/account.html', name: 'account', srcOnly: true },
  { url: 'http://127.0.0.1:8000/console.html', name: 'console' },
  { url: 'http://127.0.0.1:8000/dashboard.html', name: 'dashboard' },
  { url: 'http://127.0.0.1:8000/api.html', name: 'api' },
  { url: 'http://127.0.0.1:8000/models/vip-picks.html', name: 'vip-picks' },
  { url: 'http://127.0.0.1:8000/docs.html', name: 'docs' },
  { url: 'http://127.0.0.1:8000/guides/index.html', name: 'guides' },
  { url: 'http://127.0.0.1:8000/status.html', name: 'status' },
  { url: 'http://127.0.0.1:8000/demo.html', name: 'demo', srcOnly: true },
  { url: 'http://127.0.0.1:8000/privacy.html', name: 'privacy' },
  { url: 'http://127.0.0.1:8000/terms.html', name: 'terms' },
  { url: 'http://127.0.0.1:8000/404.html', name: '404' },
  { url: 'http://127.0.0.1:8000/paypal.html', name: 'paypal' },
  { url: 'http://127.0.0.1:8000/refer.html', name: 'refer' },
  { url: 'http://127.0.0.1:8000/partner.html', name: 'partner' },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  let failed = 0;
  for (const p of pages) {
    if (p.srcOnly) {
      // 跳转页（旧灯塔版 a.ai24x.com 用户中心/行情）：直接断言本地源码已切深色
      const res = await fetch(p.url);
      const html = await res.text();
      const ok =
        html.includes('theme-dark.css') && /class="theme-dark"/.test(html);
      if (!ok) failed++;
      console.log(
        (ok ? 'PASS' : 'FAIL') + ' | ' + p.name + ' (srcOnly: theme-dark.css + body class)'
      );
      continue;
    }
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    try {
      await page.goto(p.url, { waitUntil: 'networkidle', timeout: 30000 });
    } catch (e) {
      errors.push('goto: ' + String(e));
    }
    await page.waitForTimeout(700);
    const probe = await page.evaluate(() => {
      const link = document.getElementById('theme-css');
      return {
        cls: document.body.className,
        bg: getComputedStyle(document.body).backgroundColor,
        themeHref: link ? link.getAttribute('href') : null,
      };
    });
    const hasDarkClass = probe.cls.indexOf('theme-dark') >= 0;
    const hasDarkCss = probe.themeHref && probe.themeHref.indexOf('theme-dark.css') >= 0;
    const darkBg = probe.bg === 'rgb(11, 15, 20)'; // #0b0f14
    const ok = hasDarkClass && hasDarkCss && darkBg && errors.length === 0;
    if (!ok) failed++;
    console.log(
      (ok ? 'PASS' : 'FAIL') + ' | ' + p.name + ' | class=' + probe.cls + ' | bg=' + probe.bg + ' | theme=' + probe.themeHref + ' | jsErrors=' + errors.length
    );
    if (errors.length) console.log('    errors: ' + errors.join(' || ').slice(0, 300));
    await page.close();
  }
  await browser.close();
  console.log(failed === 0 ? '=== ALL PASS ===' : '=== ' + failed + ' FAILED ===');
  process.exit(failed === 0 ? 0 : 1);
})();
