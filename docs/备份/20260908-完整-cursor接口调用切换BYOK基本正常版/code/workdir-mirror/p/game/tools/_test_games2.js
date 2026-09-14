// 20 款游戏第二轮测试：真错误（pageerror/console/404/交互异常）采集
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');

const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18779;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.png': 'image/png', '.css': 'text/css', '.ico': 'image/x-icon' };

const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

function listGames() {
  return fs.readdirSync(ROOT).filter(f => f.endsWith('.html') && !f.startsWith('_') && !f.includes('.bak')).sort();
}

async function testGame(browser, file) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message + ' @ ' + (e.stack || '').split('\n').slice(1, 3).join(' | ')));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });
  page.on('requestfailed', r => { const u = r.url(); if (!u.includes('favicon')) errors.push('REQFAIL: ' + u); });
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) errors.push('HTTP' + r.status() + ': ' + r.url()); });

  const url = `http://127.0.0.1:${PORT}/${file}`;
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 15000 });
    await page.waitForTimeout(500);

    // 玩法说明展开/收起
    const howBtn = await page.$('#howBtn');
    if (howBtn) { await howBtn.click().catch(() => {}); await page.waitForTimeout(100); await howBtn.click().catch(() => {}); }

    // 可点击按钮逐个点（overlay 未显示则跳过，不算错）
    for (const sel of ['#restart', '#start', '#play', '.play', '#again', '#next', '#begin', '#retry', '#close', '#ok']) {
      const el = await page.$(sel).catch(() => null);
      if (!el) continue;
      const visible = await el.isVisible().catch(() => false);
      if (!visible) continue;
      try { await el.click({ timeout: 800 }); await page.waitForTimeout(200); } catch (e) { errors.push('CLICKERR ' + sel + ': ' + e.message.split('\n')[0]); }
    }

    // canvas 按住/点击
    const cv = await page.$('canvas');
    if (cv) {
      const box = await cv.boundingBox().catch(() => null);
      if (box) {
        const pts = [[0.5, 0.5], [0.2, 0.3], [0.8, 0.6]];
        for (const [fx, fy] of pts) {
          try { await page.mouse.move(box.x + box.width * fx, box.y + box.height * fy); await page.mouse.down(); await page.waitForTimeout(200); await page.mouse.up(); } catch (e) { errors.push('MOUSEERR: ' + e.message.split('\n')[0]); }
          await page.waitForTimeout(120);
        }
      }
    }

    // 键盘交互（方向键/空格）
    try { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(100); await page.keyboard.press('Space'); } catch (e) { errors.push('KEYERR: ' + e.message.split('\n')[0]); }

    // 等一轮，让游戏循环跑出错误
    await page.waitForTimeout(900);
    return { file, errors };
  } catch (e) {
    return { file, errors: ['LOADFAIL: ' + e.message.split('\n')[0]].concat(errors) };
  } finally {
    await page.close().catch(() => {});
  }
}

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const files = listGames();
  const results = [];
  for (const f of files) {
    const r = await testGame(browser, f);
    results.push(r);
    if (r.errors.length) {
      console.log('BUG  ' + f);
      r.errors.forEach(e => console.log('      ' + e));
    } else {
      console.log('OK   ' + f);
    }
  }
  await browser.close();
  server.close();
  const bugs = results.filter(r => r.errors.length);
  console.log('TOTAL=' + files.length + ' OK=' + (files.length - bugs.length) + ' BUG=' + bugs.length);
})();
