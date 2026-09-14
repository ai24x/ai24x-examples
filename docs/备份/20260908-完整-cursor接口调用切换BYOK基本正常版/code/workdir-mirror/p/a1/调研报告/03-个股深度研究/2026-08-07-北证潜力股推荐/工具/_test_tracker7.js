'use strict';
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--disable-gpu'] });
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 200)));
  const TOKEN = fs.readFileSync(path.join(__dirname, 'token.txt'), 'utf8').trim();
  const CFG = JSON.stringify({mcapMin:5,mcapMax:40,amountMin:3000,posMax:35,max5d:22,max10d:32,aiMin:50,topN:3,cap:15,aiOk:false,aiTop:5,kw:'机器,煤炭,锂,算力,光',autoScan:false,planTime:'15:35',minSurge:4,surgeVol:1.8,surgeDays:15,max20d:30,max60d:45,mainline:'must',hotPct:4,hotN:12,turnMin:2,turnMax:20,useFund:true});
  await page.goto('http://127.0.0.1:18001/bj/', { waitUntil: 'domcontentloaded' });
  await page.evaluate((o) => {
    localStorage.setItem('ai24x_a_token', o.t);
    localStorage.setItem('bj_tracker_cfg_v1', o.cfg);
    localStorage.removeItem('bj_tracker_last_run_date');
    localStorage.removeItem('bj_tracker_last_result');
  }, { t: TOKEN, cfg: CFG });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.click('#btn-run');
  const started = Date.now();
  let done = false, failed = false;
  while (Date.now() - started < 110000) {
    const st = await page.evaluate(() => ({
      visible: document.getElementById('result-card').style.display !== 'none',
      log: document.getElementById('log').textContent
    }));
    if (st.visible) { done = true; break; }
    if (st.log.includes('扫描失败') || st.log.includes('无合格标的')) { failed = true; break; }
    await page.waitForTimeout(2000);
  }
  console.log('done=' + done + ' failed=' + failed + ' elapsed=' + Math.round((Date.now() - started) / 1000) + 's');
  const log = await page.textContent('#log');
  console.log('--- LOG ---\n' + log.slice(-900));
  if (done) {
    const picks = await page.evaluate(() =>
      Array.from(document.querySelectorAll('#picks .pick-grid > .card')).map(c => c.innerText.split('\n').slice(0, 5)));
    console.log('--- PICKS (must模式) ---\n' + JSON.stringify(picks, null, 1));
  }
  console.log('--- ERRORS ---\n' + (errors.length ? errors.join('\n') : '(none)'));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });