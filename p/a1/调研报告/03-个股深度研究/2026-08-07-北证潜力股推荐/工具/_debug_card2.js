'use strict';
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--disable-gpu'] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const TOKEN = fs.readFileSync(path.join(__dirname, 'token.txt'), 'utf8').trim();
  await context.addInitScript((o) => { try { localStorage.setItem('ai24x_a_token', o.t); localStorage.setItem('ai24x_invite_code', o.i); } catch (e) {} }, { t: TOKEN, i: 'BWPX3Z8B' });
  const page = await context.newPage();
  page.on('request', r => {
    const u = r.url();
    if (/18011|gtimg|eastmoney/.test(u)) console.log('[req]', r.method(), u.slice(0, 160));
  });
  page.on('response', async r => {
    const u = r.url();
    if (/18011/.test(u)) {
      let body = '';
      try { body = (await r.text()).slice(0, 200); } catch (e) {}
      console.log('[resp]', r.status(), u.slice(0, 160), '|', body.replace(/\s+/g, ' ').slice(0, 160));
    }
  });
  page.on('console', m => console.log('[console]', m.type(), m.text().slice(0, 150)));
  page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 300)));
  await page.goto('http://127.0.0.1:18001/demo.html', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('#stock-query', { timeout: 15000 });
  const authed = await page.evaluate(() => {
    try { return { token: (localStorage.getItem('ai24x_a_token') || '').slice(0, 12), } } catch (e) { return {}; }
  });
  console.log('AUTH', JSON.stringify(authed));
  await page.fill('#stock-query', '920932');
  await page.click('#btn-search');
  await page.waitForTimeout(15000);
  const state = await page.evaluate(() => ({
    href: location.href,
    liveText: (document.getElementById('quote-live') || {}).textContent || '',
    status: (document.getElementById('quote-status') || {}).textContent || '',
    err: (document.getElementById('load-error') || {}).hidden !== false ? '' : (document.getElementById('load-error').textContent || ''),
  }));
  console.log('STATE', JSON.stringify(state, null, 2));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });