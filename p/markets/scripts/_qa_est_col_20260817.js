// 实测 vip-picks 两张表的列宽（找出被撑开的列）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  for (const lang of ['zh', 'en']) {
    await page.goto('http://127.0.0.1:18015/models/vip-picks.html?lang=' + lang, { waitUntil: 'domcontentloaded', timeout: 40000 });
    await page.waitForTimeout(3500);
    const tables = await page.locator('.model-table-wrap table').count();
    console.log('== lang=' + lang, 'tables:', tables, 'errors:', errors.length, errors[0] || '');
    for (let ti = 0; ti < tables; ti++) {
      const widths = await page.evaluate((idx) => {
        const tbl = document.querySelectorAll('.model-table-wrap table')[idx];
        const tr = tbl.querySelector('tbody tr');
        const cells = tr ? Array.from(tr.cells) : [];
        const w = cells.map((c) => Math.round(c.getBoundingClientRect().width));
        const headers = Array.from(tbl.querySelectorAll('thead th')).map((h) => h.textContent.trim());
        const tblW = Math.round(tbl.getBoundingClientRect().width);
        const wrapW = document.querySelectorAll('.model-table-wrap')[idx] ? Math.round(document.querySelectorAll('.model-table-wrap')[idx].getBoundingClientRect().width) : 0;
        return { headers, w, tblW, wrapW, scroll: document.querySelectorAll('.model-table-wrap')[idx].scrollWidth };
      }, ti);
      console.log('  table' + (ti + 1), 'estCol:', widths.w[4], 'tableW:', widths.tblW, 'wrapW:', widths.wrapW, 'overflow:', widths.scroll > widths.wrapW);
    }
  }
  await browser.close();
})();
