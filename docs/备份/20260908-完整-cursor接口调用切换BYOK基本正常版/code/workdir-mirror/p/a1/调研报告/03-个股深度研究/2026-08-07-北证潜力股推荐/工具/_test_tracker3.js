'use strict';
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--disable-gpu'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 200)));
  const TOKEN = fs.readFileSync(path.join(__dirname, 'token.txt'), 'utf8').trim();
  const CFG = JSON.stringify({mcapMin:5,mcapMax:40,amountMin:3000,posMax:40,max5d:25,max10d:35,aiMin:50,topN:3,cap:12,aiOk:false,aiTop:5,kw:'',autoScan:false,planTime:'15:35'});
  await page.goto('http://127.0.0.1:18001/bj-tracker/', { waitUntil: 'domcontentloaded' });
  await page.evaluate((o) => {
    localStorage.setItem('ai24x_a_token', o.t);
    localStorage.setItem('bj_tracker_cfg_v1', o.cfg);
    localStorage.removeItem('bj_tracker_last_run_date');
    localStorage.removeItem('bj_tracker_last_result');
  }, { t: TOKEN, cfg: CFG });
  await page.reload({ waitUntil: 'domcontentloaded' });
  console.log('A. 初始状态:', await page.textContent('#progtext'));
  await page.click('#btn-run');
  const started = Date.now();
  while (Date.now() - started < 90000) {
    const v = await page.evaluate(() => document.getElementById('result-card').style.display !== 'none');
    if (v) break;
    await page.waitForTimeout(2000);
  }
  await page.waitForTimeout(1500);
  const st1 = await page.evaluate(() => {
    const h = JSON.parse(localStorage.getItem('bj_tracker_hist_v1') || '[]') || [];
    return {
      lastRun: localStorage.getItem('bj_tracker_last_run_date'),
      hasResult: !!localStorage.getItem('bj_tracker_last_result'),
      histCount: h.length,
      histDates: h.map(x => x.date),
      logTail: document.getElementById('log').textContent.split('\n').slice(-4).join('\n')
    };
  });
  console.log('B. 扫完状态:', JSON.stringify(st1, null, 1));
  await page.click('#btn-run');
  const started2 = Date.now();
  while (Date.now() - started2 < 90000) {
    const v = await page.evaluate(() => document.getElementById('log').textContent.includes('结果已自动保存'));
    if (v) break;
    await page.waitForTimeout(2000);
  }
  await page.waitForTimeout(1500);
  const st2 = await page.evaluate(() => {
    const h = JSON.parse(localStorage.getItem('bj_tracker_hist_v1') || '[]') || [];
    return { histCount: h.length, histDates: h.map(x => x.date) };
  });
  console.log('C. 二次扫描后历史(应仍1条当天):', JSON.stringify(st2));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const st3 = await page.evaluate(() => ({
    resultVisible: document.getElementById('result-card').style.display !== 'none',
    prog: document.getElementById('progtext').textContent,
    log: document.getElementById('log').textContent,
    pickCount: document.querySelectorAll('#picks .pick-grid > .card').length
  }));
  console.log('D. 刷新后(自动恢复):', JSON.stringify(st3, null, 1));
  console.log('--- ERRORS ---\n' + (errors.length ? errors.join('\n') : '(none)'));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });