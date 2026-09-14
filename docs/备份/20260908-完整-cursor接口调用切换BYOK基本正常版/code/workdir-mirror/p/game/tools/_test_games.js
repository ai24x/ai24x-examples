// 20 款游戏冒烟测试：加载 + 按钮点击 + canvas 交互，收集 JS 报错
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');

const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18777;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.png': 'image/png', '.css': 'text/css' };

const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

function listGames() {
  return fs.readdirSync(ROOT).filter(f => f.endsWith('.html') && !f.startsWith('_') && !f.includes('.bak'));
}

async function smokeTest(browser, file) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });

  const url = `http://127.0.0.1:${PORT}/${file}`;
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 15000 });
    await page.waitForTimeout(800);
    const hasCanvas = await page.$('canvas').then(x => !!x).catch(() => false);

    // 点玩法说明按钮（如果有）
    try { await page.click('#howBtn', { timeout: 800 }).catch(() => {}); await page.waitForTimeout(150); } catch (e) {}

    // 点开始/再来按钮（常见 id）
    let clicked = [];
    for (const sel of ['#restart', '#start', '#play', '.play', '#again', '#next', '#begin', '#retry']) {
      const btn = await page.$(sel).catch(() => null);
      if (btn) {
        try { await btn.click({ timeout: 500 }); clicked.push(sel); await page.waitForTimeout(250); } catch (e) { errors.push('CLICKFAIL ' + sel + ': ' + e.message.split('\n')[0]); }
      }
    }

    // canvas 上模拟点击/按住
    const cv = await page.$('canvas').catch(() => null);
    if (cv) {
      const box = await cv.boundingBox().catch(() => null);
      if (box) {
        const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
        try { await page.mouse.move(cx, cy); await page.mouse.down(); await page.waitForTimeout(300); await page.mouse.up(); } catch (e) { errors.push('MOUSE: ' + e.message.split('\n')[0]); }
      }
    }
    await page.waitForTimeout(600);

    return { file, hasCanvas, clicked: clicked.join(','), errors };
  } catch (e) {
    return { file, hasCanvas: false, clicked: '', errors: ['LOADFAIL: ' + e.message.split('\n')[0]].concat(errors) };
  } finally {
    await page.close().catch(() => {});
  }
}

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const files = listGames();
  console.log('GAMES:', files.length);
  const results = [];
  for (const f of files) {
    const r = await smokeTest(browser, f);
    results.push(r);
    const flag = r.errors.length ? 'BUG ' : 'OK  ';
    console.log(`${flag} ${f.padEnd(24)} canvas=${r.hasCanvas} clicked=[${r.clicked}]`);
    for (const e of r.errors) console.log('      ' + e);
  }
  await browser.close();
  server.close();
  const bugCount = results.filter(r => r.errors.length).length;
  console.log('TOTAL_OK=' + (results.length - bugCount) + ' TOTAL_BUG=' + bugCount);
})();
