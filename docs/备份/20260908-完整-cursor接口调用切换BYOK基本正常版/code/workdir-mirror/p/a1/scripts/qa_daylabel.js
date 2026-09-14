// QA: 2026-08-18 数据日统一口径「今日/昨日」（盘前/盘中展示上一交易日 → 昨日；今日收盘更新完成 → 今日）
// 用法: node qa_daylabel.js （需 18001 静态 + 18011 后端运行中；实况场景为 intraday，另用 fetch mock 覆盖 fresh/stale）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJ0ZXN0MDVAcXEuY29tIiwicGhvbmUiOiIxODk2ODcwMTkxMyIsImlhdCI6MTc4NzAxOTI2NiwiZXhwIjoxNzg3NjI0MDY2fQ.dfDSzz3z6EIVXAWMnnFiJ31hvPqJ1hmA36Q-YTa9IEg';

const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}

function mockPayload(day) {
  return {
    ok: true, cached: false, date: day.date, asof: day.asof, market_code: 'hs',
    total: 700, scanned: 64, fine: 2, stale_from: day.stale_from || '',
    intraday: !!day.intraday, stale: !!day.stale, today_missing: !!day.today_missing, off_market: !!day.off_market,
    mainlines: [{ name: 'AI服务器算力', src: 'daily' }],
    board_rank: [
      { name: 'AI服务器算力', secid: '90.BK0653', mainline: true, ml_name: 'AI服务器算力', tier: 'king', f164: 100, f62: 10, p5: 5, leaders: [{ code: '000977', name: '浪潮信息', pct: 5 }] },
      { name: '通信光模块CPO', secid: '90.BK1004', mainline: true, ml_name: '通信光模块CPO', tier: 'key', f164: 80, f62: 8, p5: 4, leaders: [{ code: '300502', name: '新易盛', pct: 4 }] },
      { name: '半导体', secid: '90.BK1036', mainline: true, ml_name: '半导体', tier: 'key', f164: 60, f62: 6, p5: 3, leaders: [{ code: '688041', name: '海光信息', pct: 3 }] },
      { name: '光伏设备', secid: '90.BK1031', mainline: false, tier: 'backup', f164: 40, f62: 4, p5: 2, leaders: [] },
    ],
    picks: [
      { code: '000977', name: '浪潮信息', pct: 5, tier: 'king', final: 80, position: 25, mktcap: 1000, patterns: {}, strategy: {} },
    ],
    runners: [],
    prev_track: [],
    vip: true,
    md: null,
  };
}

async function openAndWait(page, url, containerSel) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(function (sel) {
    return document.querySelectorAll(sel + ' .br-item').length >= 1;
  }, containerSel, { timeout: 90000 });
  await page.waitForTimeout(1000);
}

async function run(ctx, opts) {
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', function (e) { errs.push(String(e)); });
  if (opts.mock) {
    await page.route(function (url) { return url.pathname === '/api/bj/screener' && !!url.search; }, function (route) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(opts.mock) });
    });
  }
  await openAndWait(page, opts.url, opts.containerSel);
  await page.waitForTimeout(600);

  const rows = await page.evaluate(function (sel) {
    return Array.prototype.slice.call(document.querySelectorAll(sel + ' .br-item')).map(function (r) {
      return (r.textContent || '').replace(/\s+/g, ' ');
    });
  }, opts.containerSel);
  const allTxt = rows.join('\n');

  log(opts.label + ' 排行第1行 ' + opts.expMain, rows.length > 0 && rows[0].indexOf(opts.expMain) >= 0, rows[0] ? rows[0].slice(0, 60) : 'no rows');
  log(opts.label + ' 排行无「⭐ 今日主线」' + (opts.fresh ? '（fresh 场景除外）' : ''), opts.fresh || allTxt.indexOf('⭐ 今日主线') < 0, '');
  log(opts.label + ' 排行含「' + opts.expFund + '」', allTxt.indexOf(opts.expFund) >= 0, '');

  if (!opts.mobileOnly) {
    const resTxt = await page.evaluate(function () {
      var el = document.getElementById('bj-result');
      return el ? (el.textContent || '').replace(/\s+/g, ' ') : '';
    });
    const expPickOk = opts.expPickTitle ? resTxt.indexOf(opts.expPickTitle) >= 0 : (resTxt.indexOf('上一交易日') >= 0 || resTxt.indexOf('昨日标的') >= 0 || resTxt.indexOf('昨日无合格') >= 0);
    log(opts.label + ' 结果区含「' + (opts.expPickTitle || '昨日/上一交易日') + '」', expPickOk, resTxt.slice(0, 80));
    log(opts.label + ' 结果区不含「今日标的」' + (opts.fresh ? '（fresh 场景除外）' : ''), opts.fresh || resTxt.indexOf('今日标的') < 0, '');
  } else {
    const secTitle = await page.evaluate(function () {
      var el = document.getElementById('sec-title');
      return el && el.childNodes.length ? el.childNodes[0].textContent : '';
    });
    log(opts.label + ' sec-title = ' + opts.expTitle, secTitle === opts.expTitle, secTitle);
  }
  log(opts.label + ' no JS errors', errs.length === 0, errs.slice(0, 3).join(' ; '));
  await page.close();
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });

  // 1) 实况：本地后端 intraday=true（上一交易日数据）→ 昨日
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
    await ctx.addInitScript(function (t) { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, TOKEN);
    await run(ctx, { label: '实况-intraday', url: 'http://127.0.0.1:18001/gd.html?i=CL2KDLGR', containerSel: '#bj-boardrank', expMain: '⭐ 昨日主线', expFund: '昨日主力', expPickTitle: '', fresh: false });
    await ctx.close();
  }

  // 2) mock fresh：今日收盘已更新 → 今日
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
    await ctx.addInitScript(function (t) { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, TOKEN);
    const today = new Date();
    const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
    await run(ctx, { label: 'mock-fresh', url: 'http://127.0.0.1:18001/gd.html?i=CL2KDLGR', containerSel: '#bj-boardrank', mock: mockPayload({ date: todayStr, asof: todayStr }), expMain: '⭐ 今日主线', expFund: '今日主力', expPickTitle: '今日标的 · 买什么', fresh: true });
    await ctx.close();
  }

  // 3) mock stale：今日无合格，展示上一交易日 → 昨日
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
    await ctx.addInitScript(function (t) { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, TOKEN);
    const today = new Date();
    const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
    const p = mockPayload({ date: todayStr, asof: '2026-08-17', stale: true, stale_from: '2026-08-17' });
    p.picks = [];
    await run(ctx, { label: 'mock-stale', url: 'http://127.0.0.1:18001/gd.html?i=CL2KDLGR', containerSel: '#bj-boardrank', mock: p, expMain: '⭐ 昨日主线', expFund: '昨日主力', expPickTitle: '', fresh: false });
    await ctx.close();
  }

  // 4) 手机版实况：sec-title + 排行
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, serviceWorkers: 'block' });
    await ctx.addInitScript(function (t) { try { localStorage.setItem('ai24x_a_token', t); } catch (e) {} }, TOKEN);
    await run(ctx, { label: '手机实况', url: 'http://127.0.0.1:18001/m/gd.html?i=CL2KDLGR', containerSel: '#boardrank', expMain: '⭐ 昨日主线', expFund: '昨日主力', expTitle: '昨日 AI 筛选', mobileOnly: true, fresh: false });
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
