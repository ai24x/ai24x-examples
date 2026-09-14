const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18778;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  page.on('pageerror', e=>console.log('PAGEERROR:', e.message, '\nSTACK:', (e.stack||'').split('\n').slice(0,6).join('\n')));
  page.on('console', m=>{if(m.type()==='error') console.log('CONSOLE:', m.text());});
  page.on('requestfailed', r=>console.log('REQFAIL:', r.url()));
  await page.goto(`http://127.0.0.1:${PORT}/neon-snake.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(1200);
  // 模拟按键开始（贪吃蛇通常需要方向键/空格）
  for (let i=0;i<5;i++){ await page.keyboard.press('ArrowRight'); await page.waitForTimeout(150); }
  await page.waitForTimeout(800);
  await page.screenshot({path:'E:/AI24X/ai24x-website/ai24x01/p/game/tools/_neon-snake.png'});
  await browser.close(); server.close();
})();
