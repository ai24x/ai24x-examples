// QA: open.ai24x.com product/pricing/vip-picks 三页实测（版本/JS报错/资源404/文案渲染）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const URLS = [
  'http://127.0.0.1:18015/product.html?lang=zh',
  'http://127.0.0.1:18015/pricing.html?lang=zh',
  'http://127.0.0.1:18015/models/vip-picks.html?lang=zh',
  'http://127.0.0.1:18015/product.html?lang=en',
  'http://127.0.0.1:18015/pricing.html?lang=en',
];

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });

  for (const url of URLS) {
    const page = await ctx.newPage();
    const jsErrors = [];
    const pageErrors = [];
    const failed = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const loc = msg.location();
        jsErrors.push(msg.text() + ' @@ ' + (loc ? loc.url : ''));
      }
    });
    page.on('pageerror', (err) => pageErrors.push(String(err)));
    page.on('requestfailed', (req) => failed.push(req.url() + ' :: ' + req.failure()?.errorText));
    page.on('response', (resp) => {
      if (resp.status() >= 400) {
        failed.push(resp.status() + ' ' + resp.url() + ' type=' + resp.request().resourceType());
      }
    });

    try {
      const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 40000 });
      await page.waitForTimeout(3000);
      const title = await page.title();
      const h1 = await page.locator('h1').first().textContent().catch(() => '');
      const hasNav = await page.locator('.site-header .nav, .site-header nav, header a').count().catch(() => 0);
      const theme = await page.evaluate(() => {
        const b = document.body;
        const c = b ? b.className : '';
        return c + ' | css=' + (document.querySelector('#theme-css')?.getAttribute('href') || '');
      });
      const failedRes = failed.filter((f) => !f.startsWith('4') && f.includes('http'));
      const errToast = await page.evaluate(() => {
        const t = document.querySelector('.toast, #toast, .alert-error, [class*="error"], [class*="alert"]');
        return t ? (t.textContent || '').trim().slice(0, 120) : '';
      });
      const tableRows = await page.locator('table tbody tr, .model-table-wrap tr').count().catch(() => 0);
      const footerText = await page.locator('footer').first().textContent().catch(() => '');
      const emptyI18n = await page.evaluate(() => {
        const arr = [];
        document.querySelectorAll('[data-i18n]').forEach((el) => {
          const t = (el.textContent || '').trim();
          if (t === '' && el.offsetParent !== null) arr.push(el.getAttribute('data-i18n'));
        });
        return arr.slice(0, 12);
      });
      const keyLeak = await page.evaluate(() => {
        const arr = [];
        document.querySelectorAll('[data-i18n]').forEach((el) => {
          const t = (el.textContent || '').trim();
          if (t === el.getAttribute('data-i18n')) arr.push(t);
        });
        return arr.slice(0, 8);
      });
      log(url.split('open.ai24x.com')[1], true, `title="${title}" h1="${(h1||'').trim().slice(0,50)}" navLinks=${hasNav} theme=${theme} jsErr=${jsErrors.length} pgErr=${pageErrors.length} badRes=${failed.length} rows=${tableRows} emptyI18n=${emptyI18n.length} keyLeak=${keyLeak.length} toast="${errToast}"`);
      if (emptyI18n.length) console.log('   EMPTY-I18N:', emptyI18n.join(','));
      if (keyLeak.length) console.log('   KEY-LEAK:', keyLeak.join(','));
      if (url.includes('pricing')) {
        const gridText = await page.locator('#tokenPlansGrid').textContent().catch(() => '');
        console.log('   PLANS:', (gridText || '').replace(/\s+/g, ' ').trim().slice(0, 500));
      }
      if (url.includes('vip-picks')) {
        const tableText = await page.locator('.model-table-wrap table').first().textContent().catch(() => '');
        console.log('   TABLE-HEAD:', (tableText || '').replace(/\s+/g, ' ').trim().slice(0, 400));
      }
      if (url.includes('product')) {
        const mainText = await page.locator('main').textContent().catch(() => '');
        console.log('   PRODUCT-MAIN:', (mainText || '').replace(/\s+/g, ' ').trim().slice(0, 700));
      }
      jsErrors.slice(0, 4).forEach((e) => console.log('   JSERR:', e.slice(0, 220)));
      pageErrors.slice(0, 4).forEach((e) => console.log('   PGERR:', e.slice(0, 220)));
      failed.slice(0, 8).forEach((f) => console.log('   BADRES:', f.slice(0, 180)));
    } catch (e) {
      log(url, false, 'goto failed: ' + String(e).slice(0, 200));
    } finally {
      await page.close();
    }
  }

  await browser.close();
  const fails = results.filter((r) => !r.ok).length;
  console.log(`\nTOTAL ${results.length}  FAIL ${fails}`);
  process.exit(fails ? 1 : 0);
})();
