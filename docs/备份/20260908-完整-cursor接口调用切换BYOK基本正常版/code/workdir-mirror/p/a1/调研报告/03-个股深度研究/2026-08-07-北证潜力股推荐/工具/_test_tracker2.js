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
  await page.goto('http://127.0.0.1:18001/bj-tracker/', { waitUntil: 'domcontentloaded' });
  await page.evaluate((t) => {
    localStorage.setItem('ai24x_a_token', t);
    localStorage.setItem('bj_tracker_cfg_v1', JSON.stringify({mcapMin:5,mcapMax:40,amountMin:3000,posMax:40,max5d:25,max10d:35,aiMin:50,topN:3,cap:12,aiOk:false,aiTop:5,kw:''}));
  }, TOKEN);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.click('#btn-run');
  const started = Date.now();
  let done = false, failed = false;
  while (Date.now() - started < 90000) {
    const st = await page.evaluate(() => ({
      visible: document.getElementById('result-card').style.display !== 'none',
      log: document.getElementById('log').textContent
    }));
    if (st.visible) { done = true; break; }
    if (st.log.includes('扫描失败')) { failed = true; break; }
    await page.waitForTimeout(2000);
  }
  console.log('done=' + done + ' failed=' + failed + ' elapsed=' + Math.round((Date.now() - started) / 1000) + 's');
  const log = await page.textContent('#log');
  console.log('--- LOG tail ---\n' + log.slice(-900));
  const picks = await page.evaluate(() =>
    Array.from(document.querySelectorAll('#picks .pick-grid > .card')).map(c => c.innerText.split('\n').slice(0, 2).join(' | ')));
  console.log('--- PICKS ---\n' + JSON.stringify(picks, null, 1));
  console.log('--- ERRORS ---\n' + (errors.length ? errors.join('\n') : '(none)'));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });