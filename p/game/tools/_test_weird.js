const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18787;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];
  page.on('pageerror', e=>errors.push('PAGEERROR: '+e.message+' @ '+(e.stack||'').split('\n')[1]));
  page.on('console', m=>{if(m.type()==='error'&&!m.text().includes('favicon')) errors.push('CONSOLE: '+m.text());});
  await page.goto(`http://127.0.0.1:${PORT}/weird-merge.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(800);
  // 初始棋盘
  const snap = () => page.evaluate(() => {
    const cells = [...document.querySelectorAll('.cell')];
    return cells.map(c => c.textContent || null);
  });
  console.log('board:', JSON.stringify(await snap()));
  // 找相邻同种合并（循环 30 次）
  for (let i=0;i<30;i++) {
    const b = await snap();
    let found = null;
    outer:
    for (let r=0;r<6;r++) for (let c=0;c<6;c++) {
      if (!b[r*6+c]) continue;
      for (const [dr,dc] of [[0,1],[1,0]]) {
        const rr=r+dr, cc=c+dc;
        if (rr<6 && cc<6 && b[rr*6+cc] && b[rr*6+cc]===b[r*6+c]) { found=[r,c,rr,cc]; break outer; }
      }
    }
    if (!found) break;
    const box = await (await page.$('#board')).boundingBox();
    const cw = box.width/6, ch = box.height/6;
    const clickCell = (r,c) => page.mouse.click(box.x + c*cw + cw/2, box.y + r*ch + ch/2);
    await clickCell(found[0], found[1]);
    await page.waitForTimeout(150);
    await clickCell(found[2], found[3]);
    await page.waitForTimeout(250);
  }
  const st = await page.evaluate(() => ({
    score: document.getElementById('score').textContent,
    dexN: document.getElementById('dexN').textContent,
    candy: document.getElementById('candy').textContent,
    overlay: document.getElementById('overlay').classList.contains('show')
  }));
  console.log('state:', JSON.stringify(st));
  await page.screenshot({path:'E:/AI24X/ai24x-website/ai24x01/p/game/tools/_weird-merge.png'});
  console.log('ERRORS:', errors.length ? errors.join(' | ') : 'none');
  await browser.close(); server.close();
})();
