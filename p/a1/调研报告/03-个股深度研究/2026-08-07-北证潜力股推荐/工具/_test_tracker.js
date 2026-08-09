'use strict';
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--disable-gpu'] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + String(e).slice(0, 300)));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text().slice(0, 300)); });
  const TOKEN = fs.readFileSync(path.join(__dirname, 'token.txt'), 'utf8').trim();
  await page.goto('http://127.0.0.1:18001/bj-tracker/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('#btn-run', { timeout: 15000 });
  // 设置小规模测试参数 + token
  await page.evaluate((t) => {
    localStorage.setItem('ai24x_a_token', t);
    localStorage.setItem('bj_tracker_cfg_v1', JSON.stringify({mcapMin:5,mcapMax:40,amountMin:3000,posMax:35,max5d:22,max10d:32,aiMin:55,topN:3,cap:12,aiOk:true,aiTop:5,kw:'机器,煤炭,锂,算力,光'}));
  }, TOKEN);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#btn-run', { timeout: 15000 });
  console.log('page loaded, token state:', await page.textContent('#tokstate'));
  await page.click('#btn-run');
  // 轮询等待结果卡片出现
  const started = Date.now();
  let done = false;
  while (Date.now() - started < 150000) {
    const visible = await page.evaluate(() => document.getElementById('result-card').style.display !== 'none');
    if (visible) { done = true; break; }
    const logText = await page.textContent('#log');
    if (logText.includes('扫描失败')) { console.log('SCAN FAILED\n' + logText); break; }
    await page.waitForTimeout(3000);
  }
  console.log('done=' + done + ' elapsed=' + Math.round((Date.now() - started) / 1000) + 's');
  const logText = await page.textContent('#log');
  console.log('--- LOG ---\n' + logText.slice(-1800));
  const picks = await page.evaluate(() => {
    const cards = document.querySelectorAll('#picks .pick-grid > .card');
    return Array.from(cards).map(c => c.innerText.split('\n').slice(0, 6));
  });
  console.log('--- PICKS ---\n' + JSON.stringify(picks, null, 1));
  await page.screenshot({ path: path.join(__dirname, '_tracker_test.png'), fullPage: true });
  console.log('--- ERRORS ---\n' + (errors.length ? errors.join('\n') : '(none)'));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });