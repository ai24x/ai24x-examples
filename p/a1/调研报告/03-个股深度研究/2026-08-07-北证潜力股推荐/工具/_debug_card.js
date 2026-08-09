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
  page.on('console', m => console.log('[console]', m.type(), m.text().slice(0, 200)));
  page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 300)));
  await page.goto('http://127.0.0.1:18001/demo.html', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('#stock-query', { timeout: 15000 });
  await page.fill('#stock-query', '920932');
  await page.click('#btn-search');
  await page.waitForTimeout(12000);
  const state = await page.evaluate(() => {
    const live = document.getElementById('quote-live');
    const q = document.getElementById('stock-query');
    return {
      href: location.href,
      search: location.search,
      liveText: live ? live.textContent.slice(0, 300) : '(no quote-live)',
      queryVal: q ? q.value : '(no query)',
      bodySnippet: document.body.innerText.slice(0, 400),
    };
  });
  console.log('STATE', JSON.stringify(state, null, 2));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });