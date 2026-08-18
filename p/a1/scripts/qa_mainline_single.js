// QA: 2026-08-18 板块排行「主线 ✓」全局唯一（只有第 1 名 king 主线显示，其余 mainline 显示重点关注）
// 用法: node qa_mainline_single.js （需 18001 静态 + 18011 后端运行中）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJ0ZXN0MDVAcXEuY29tIiwicGhvbmUiOiIxODk2ODcwMTkxMyIsImlhdCI6MTc4NzAxOTI2NiwiZXhwIjoxNzg3NjI0MDY2fQ.dfDSzz3z6EIVXAWMnnFiJ31hvPqJ1hmA36Q-YTa9IEg';

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

async function waitBoardRank(page, containerSel) {
  await page.waitForFunction(function (sel) {
    return document.querySelectorAll(sel + ' .br-item').length >= 1;
  }, containerSel, { timeout: 90000 });
  // 给渲染 settle 一点时间
  await page.waitForTimeout(1500);
}

async function assertRanking(page, containerSel, label) {
  const errs = [];
  page.on('pageerror', function (e) { errs.push(String(e)); });
  const info = await page.evaluate(function (sel) {
    const rows = Array.prototype.slice.call(document.querySelectorAll(sel + ' .br-item'));
    return rows.map(function (r, i) {
      return {
        i: i + 1,
        text: (r.textContent || '').replace(/\s+/g, ' ').slice(0, 120),
        hasMain: (r.textContent || '').indexOf('主线 ✓') >= 0,
        hasKing: (r.textContent || '').indexOf('⭐ 今日主线') >= 0,
        hasKey: (r.textContent || '').indexOf('重点关注') >= 0,
      };
    });
  }, containerSel);

  log(label + ' board_rank rows rendered', info.length >= 3, 'rows=' + info.length);

  const mainRows = info.filter(function (r) { return r.hasMain; });
  const kingRows = info.filter(function (r) { return r.hasKing; });

  log(label + ' 主线✓ 全局唯一(≤1)', mainRows.length <= 1, 'count=' + mainRows.length + ' -> ' + JSON.stringify(mainRows.map(function (r) { return r.i + ':' + r.text.slice(0, 40); })));
  log(label + ' 主线✓ 与 ⭐今日主线 同行', kingRows.length === mainRows.length && kingRows.every(function (k) { return k.hasMain; }),
    'kingRows=' + kingRows.length + ' mainRows=' + mainRows.length);
  if (mainRows.length === 1) {
    log(label + ' 主线✓ 在第 1 名', mainRows[0].i === 1, 'idx=' + mainRows[0].i);
  }
  const keyNonMain = info.filter(function (r) { return r.hasKey && r.hasMain; });
  log(label + ' 重点关注行不含 主线✓', keyNonMain.length === 0, 'bad=' + keyNonMain.length);
  const keyCount = info.filter(function (r) { return r.hasKey; }).length;
  log(label + ' 重点关注数量为 2', keyCount === 2, 'count=' + keyCount);
  log(label + ' no JS errors', errs.length === 0, errs.slice(0, 3).join(' ; '));
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });

  // ---- 桌面 gd.html ----
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await ctx.addInitScript(function (t) {
      try { localStorage.setItem('ai24x_a_token', t); } catch (e) {}
    }, TOKEN);
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18001/gd.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded' });
    await waitBoardRank(page, '#bj-boardrank');
    await assertRanking(page, '#bj-boardrank', '桌面');
    await ctx.close();
  }

  // ---- 手机 m/gd.html ----
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    await ctx.addInitScript(function (t) {
      try { localStorage.setItem('ai24x_a_token', t); } catch (e) {}
    }, TOKEN);
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:18001/m/gd.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded' });
    await waitBoardRank(page, '#boardrank');
    await assertRanking(page, '#boardrank', '手机');
    await ctx.close();
  }

  await browser.close();
  const failed = results.filter(function (r) { return !r.ok; });
  console.log('\n==== ' + (failed.length ? failed.length + ' FAILED' : 'ALL PASS') + ' (' + results.length + ' checks) ====');
  process.exit(failed.length ? 1 : 0);
})().catch(function (e) {
  console.error('QA CRASH:', e);
  process.exit(2);
});
