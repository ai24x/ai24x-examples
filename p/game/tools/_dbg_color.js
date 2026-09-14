const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18780;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  page.on('response', r=>{ if(r.status()>=400) console.log('HTTP'+r.status(), r.url()); });
  await page.goto(`http://127.0.0.1:${PORT}/color-sort.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(1500);
  // 尝试玩一下：点击试管
  const cv = await page.$('canvas');
  if(cv){ const box = await cv.boundingBox(); console.log('canvas box:', JSON.stringify(box)); for(let i=0;i<8;i++){ const x=box.x+box.width*(0.1+0.2*i), y=box.y+box.height*0.5; await page.mouse.click(x,y); await page.waitForTimeout(200);} }
  await page.waitForTimeout(500);
  await browser.close(); server.close();
})();
