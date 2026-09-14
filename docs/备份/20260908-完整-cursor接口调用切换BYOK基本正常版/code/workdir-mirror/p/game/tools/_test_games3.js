// 第三轮深度测试：模拟真实玩法，跑 开始→游玩→结算→重开 闭环，抓异常
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');

const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18781;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.png': 'image/png', '.css': 'text/css' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

function listGames() {
  return fs.readdirSync(ROOT).filter(f => f.endsWith('.html') && !f.startsWith('_') && !f.includes('.bak') && f !== 'index.html').sort();
}

async function deepTest(browser, file) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message + ' @ ' + (e.stack || '').split('\n').slice(1, 2).join('')));
  page.on('console', m => { if (m.type() === 'error' && !m.text().includes('favicon')) errors.push('CONSOLE: ' + m.text()); });

  await page.goto(`http://127.0.0.1:${PORT}/${file}`, { waitUntil: 'load', timeout: 15000 });
  await page.waitForTimeout(400);

  // 循环交互：最多 40 次操作，让游戏推进
  for (let round = 0; round < 40; round++) {
    // 1) 可见按钮（开始/选项/重开）
    const btns = await page.$$('button, .opt, .card, [id^="opt"], [class*="opt"], #board > *, #field > *, #scene > *, #opts > *').catch(() => []);
    let acted = false;
    for (const b of btns.slice(0, 8)) {
      const vis = await b.isVisible().catch(() => false);
      if (!vis) continue;
      const box = await b.boundingBox().catch(() => null);
      if (!box) continue;
      try {
        await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2).catch(async () => { await b.click({ timeout: 400 }); });
        acted = true;
        await page.waitForTimeout(180);
        break;
      } catch (e) {}
    }
    // 2) canvas 按住/点击
    if (!acted) {
      const cv = await page.$('canvas');
      if (cv) {
        const box = await cv.boundingBox().catch(() => null);
        if (box) {
          const fx = [0.5, 0.25, 0.75][round % 3], fy = [0.5, 0.35, 0.65][round % 3];
          try {
            await page.touchscreen.tap(box.x + box.width * fx, box.y + box.height * fy);
            if (round % 2) { await page.touchscreen.tap(box.x + box.width * 0.8, box.y + box.height * 0.8); }
          } catch (e) {}
        }
      } else {
        // 无 canvas 无按钮：点页面中心
        await page.touchscreen.tap(195, 500).catch(() => {});
      }
      await page.waitForTimeout(200);
    }
    // 3) 方向键（蛇/跑酷类）
    if (round % 3 === 0) { await page.keyboard.press('ArrowRight').catch(() => {}); }
  }

  await page.waitForTimeout(600);
  // 结算后点重开
  for (const sel of ['#restart', '#playBtn', '#nextBtn', '.play']) {
    const el = await page.$(sel).catch(() => null);
    if (!el) continue;
    const vis = await el.isVisible().catch(() => false);
    if (vis) { try { await el.click({ timeout: 600 }); await page.waitForTimeout(300); } catch (e) {} }
  }
  await page.waitForTimeout(400);

  await ctx.close().catch(() => {});
  return { file, errors };
}

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const files = listGames();
  const results = [];
  for (const f of files) {
    const r = await deepTest(browser, f);
    results.push(r);
    if (r.errors.length) { console.log('BUG  ' + f); r.errors.forEach(e => console.log('      ' + e)); }
    else console.log('OK   ' + f);
  }
  await browser.close(); server.close();
  const bugs = results.filter(r => r.errors.length);
  console.log('DEEP_TOTAL=' + files.length + ' OK=' + (files.length - bugs.length) + ' BUG=' + bugs.length);
})();
