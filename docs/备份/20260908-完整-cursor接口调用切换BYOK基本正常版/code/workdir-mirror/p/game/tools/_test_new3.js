const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18792;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const files = ['screw-hero.html','weird-merge.html','arrow-maze.html','neon-snake.html'];
  for (const f of files) {
    const ctx = await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
    const page = await ctx.newPage();
    const errors=[];
    page.on('pageerror', e=>errors.push('PAGEERROR: '+e.message));
    page.on('console', m=>{if(m.type()==='error'&&!m.text().includes('favicon')) errors.push('CONSOLE: '+m.text());});
    await page.goto(`http://127.0.0.1:${PORT}/${f}`,{waitUntil:'load',timeout:15000});
    await page.waitForTimeout(700);
    // 交互一轮
    for(let i=0;i<10;i++){
      const cells = await page.$$('button, .cell, .opbtn');
      if(cells.length){
        const b = cells[Math.floor(Math.random()*cells.length)];
        const vis = await b.isVisible().catch(()=>false);
        if(vis){ const bx = await b.boundingBox().catch(()=>null); if(bx){ await page.touchscreen.tap(bx.x+bx.width/2, bx.y+bx.height/2).catch(()=>{}); await page.waitForTimeout(150); } }
      }
      const cv = await page.$('canvas');
      if(cv){ const bx = await cv.boundingBox().catch(()=>null); if(bx){ await page.touchscreen.tap(bx.x+bx.width*0.5, bx.y+bx.height*0.4).catch(()=>{}); await page.waitForTimeout(120); } }
    }
    await page.waitForTimeout(500);
    const state = await page.evaluate(() => ({ overlay: (document.getElementById('overlay')||{}).classList ? document.getElementById('overlay').classList.contains('show') : false }));
    console.log((errors.length?'BUG ':'OK  ')+f+' overlay='+state.overlay+(errors.length?(' | '+errors.join(' | ')):''));
    await ctx.close();
  }
  await browser.close(); server.close();
})();
