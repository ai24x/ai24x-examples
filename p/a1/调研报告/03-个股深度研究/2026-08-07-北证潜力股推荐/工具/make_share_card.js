'use strict';
// 用途：自动化生成 AI行情官「信号分享卡」图片（含 K线信号 + 技术快照评分，评分需登录态）。
// 登录态：AI24X_TOKEN 环境变量，或本文件同目录 token.txt（localStorage 键 ai24x_a_token）。
// 用法：node make_share_card.js 603629 688158
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
// token 过期自检：JWT exp 为秒级时间戳；过期即告警，避免生成无登录态分享卡
if (TOKEN) {
  try {
    const payload = JSON.parse(Buffer.from(TOKEN.split('.')[1], 'base64').toString());
    const exp = Number(payload.exp || 0) * 1000;
    if (exp && exp < Date.now()) {
      console.warn('⚠️ 注入的 token 已过期（' + new Date(exp).toISOString() + '）：分享卡将不含「技术快照/评分」区。请用环境变量 AI24X_TOKEN 或更新 token.txt（勿提交 git）。');
    } else if (exp) {
      console.log('token 有效期至 ' + new Date(exp).toISOString());
    }
  } catch (e) { /* 非 JWT 结构，跳过 */ }
}
const CODES = process.argv.slice(2);

async function genCard(context, code) {
  const page = await context.newPage();
  try {
    const sigReady = page.waitForEvent('console', {
      predicate: m => m.text().indexOf('signals received') >= 0,
      timeout: 25000
    }).then(() => true).catch(() => false);
    await page.goto(DEMO_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#stock-query', { timeout: 15000 });
    await page.fill('#stock-query', code);
    await page.click('#btn-search');
    // 1) 查询完成
    await page.waitForFunction((c) => {
      const live = document.getElementById('quote-live');
      const s = live ? live.textContent : '';
      return location.search.indexOf(c) >= 0 && s.indexOf(c) >= 0;
    }, code, { timeout: 45000 });
    console.log(code, '查询完成');
    // 2) 等 K线信号加载（控制台 signals received）
    const sigOk = await sigReady;
    console.log(code, '信号就绪:', sigOk);
    await page.waitForTimeout(2500);
    // 3) 打开分享层并生成卡片
    await page.click('#btn-share');
    await page.waitForSelector('#share-overlay:not([hidden])', { timeout: 10000 });
    await page.evaluate(() => { const img = document.getElementById('card-preview-img'); if (img) img.src = ''; });
    await page.click('#btn-share-card');
    await page.waitForFunction(() => {
      const img = document.getElementById('card-preview-img');
      return img && img.src && img.src.indexOf('data:image/png') === 0 && img.src.length > 1000;
    }, { timeout: 40000 });
    const dataUrl = await page.evaluate(() => document.getElementById('card-preview-img').src);
    // 4) 名称从 #quote-live 提取：形如 “利通电子（603629）　现价…”
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
  } finally {
    await page.close();
  }
}

(async () => {
  if (!CODES.length) { console.error('用法: node make_share_card.js 603629 688158'); process.exit(1); }
  const browser = await chromium.launch({ executablePath: EDGE, headless: true, args: ['--disable-gpu'] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  // 邀请码始终注入；token 仅在提供时注入
  await context.addInitScript((o) => { try { localStorage.setItem('ai24x_a_token', o.t); localStorage.setItem('ai24x_invite_code', o.i); } catch (e) {} }, { t: TOKEN, i: INVITE });
  console.log('邀请码: ' + INVITE);
  if (TOKEN) { console.log('已注入登录 token: ' + TOKEN.slice(0, 12) + '...'); }
  else { console.log('未注入 token：分享卡将不含「技术快照/评分」区。'); }
  for (const code of CODES) {
    try { await genCard(context, code); }
    catch (e) { console.error('FAIL', code, e.message); }
  }
  await browser.close();
})();
