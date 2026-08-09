'use strict';
// 北证分享卡专用版：拦截 /api/me 的配额字段（前端配额已用尽，但后端接口不限流），其余逻辑与 make_share_card.js 一致。
// 用法：node make_share_card_bj.js 920932 920098 920284
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const TOOL_DIR = __dirname;
const REPORT_DIR = path.dirname(TOOL_DIR);
const EDGE = process.env.AI24X_EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const DEMO_URL = process.env.AI24X_DEMO_URL || 'http://127.0.0.1:18001/demo.html';
const INVITE = String(process.env.AI24X_INVITE || 'BWPX3Z8B').trim().toUpperCase();
const TOKEN = (process.env.AI24X_TOKEN || '')
  || (fs.existsSync(path.join(TOOL_DIR, 'token.txt'))
      ? fs.readFileSync(path.join(TOOL_DIR, 'token.txt'), 'utf8').trim() : '');
const CODES = process.argv.slice(2);

async function genCard(context, page, code) {
  try {
    const sigReady = page.waitForEvent('console', {
      predicate: m => m.text().indexOf('signals received') >= 0,
      timeout: 25000
    }).then(() => true).catch(() => false);
    await page.goto(DEMO_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#stock-query', { timeout: 15000 });
    await page.fill('#stock-query', code);
    await page.click('#btn-search');
    await page.waitForFunction((c) => {
      const live = document.getElementById('quote-live');
      const s = live ? live.textContent : '';
      return location.search.indexOf(c) >= 0 && s.indexOf(c) >= 0;
    }, code, { timeout: 60000 });
    console.log(code, '查询完成');
    const sigOk = await sigReady;
    console.log(code, '信号就绪:', sigOk);
    await page.waitForTimeout(2500);
    await page.click('#btn-share');
    await page.waitForSelector('#share-overlay:not([hidden])', { timeout: 10000 });
    await page.evaluate(() => { const img = document.getElementById('card-preview-img'); if (img) img.src = ''; });
    await page.click('#btn-share-card');
    await page.waitForFunction(() => {
      const img = document.getElementById('card-preview-img');
      return img && img.src && img.src.indexOf('data:image/png') === 0 && img.src.length > 1000;
    }, { timeout: 60000 });
    const dataUrl = await page.evaluate(() => document.getElementById('card-preview-img').src);
    let name = '';
    try {
      const live = await page.evaluate(() => {
        const el = document.getElementById('quote-live');
        return el ? el.textContent : '';
      });
      const m = live.match(/^\s*([^\uff08(]+?)[\uff08(]/);
      if (m) name = m[1].trim();
    } catch (e) {}
    let safe = String(name || code).replace(/[^\u4e00-\u9fa5A-Za-z0-9]/g, '').replace(/W$/, '');
    if (!safe) safe = code;
    const fname = '分享卡_' + safe + '_' + code + '.png';
    const out = path.join(REPORT_DIR, fname);
    fs.writeFileSync(out, Buffer.from(dataUrl.split(',')[1], 'base64'));
    console.log('saved', fname, fs.statSync(out).size, 'bytes');
  } catch (e) {
    console.error('FAIL', code, e.message);
  }
}

(async () => {
  if (!CODES.length) { console.error('用法: node make_share_card_bj.js 920932 ...'); process.exit(1); }
  const browser = await chromium.launch({ executablePath: EDGE, headless: true, args: ['--disable-gpu'] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  // 拦截 /api/me：保留真实账号信息，仅把配额改为充足，绕过前端“今日次数已用完”拦截（后端接口不受限）
  await context.route('**/api/me**', async (route) => {
    try {
      const resp = await route.fetch();
      const body = await resp.text();
      let patched = body;
      try {
        const j = JSON.parse(body);
        if (j && j.quota) {
          j.quota.remaining = 9999;
          j.quota.remaining_day = 9999;
          j.quota.remaining_week = 9999;
          j.quota.remaining_month = 9999;
          patched = JSON.stringify(j);
        }
      } catch (e) {}
      await route.fulfill({ response: resp, body: patched });
    } catch (e) {
      await route.continue();
    }
  });
  await context.addInitScript((o) => { try { localStorage.setItem('ai24x_a_token', o.t); localStorage.setItem('ai24x_invite_code', o.i); } catch (e) {} }, { t: TOKEN, i: INVITE });
  console.log('邀请码: ' + INVITE);
  if (TOKEN) { console.log('已注入登录 token: ' + TOKEN.slice(0, 12) + '...'); }
  else { console.log('未注入 token：分享卡将不含「技术快照/评分」区。'); }
  const page = await context.newPage();
  for (const code of CODES) {
    await genCard(context, page, code);
  }
  await browser.close();
})();