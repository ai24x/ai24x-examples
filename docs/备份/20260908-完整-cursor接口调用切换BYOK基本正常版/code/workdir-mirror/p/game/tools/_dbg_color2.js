const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18782;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  page.on('response', r=>{ if(r.status()>=400) console.log('HTTP'+r.status(), JSON.stringify(r.url())); });
  page.on('request', r=>{ if(!r.url().includes('/color-sort.html') && !r.url().includes('favicon')) console.log('REQ', r.resourceType(), JSON.stringify(r.url())); });
  await page.goto(`http://127.0.0.1:${PORT}/color-sort.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(1000);
  // 模拟倒水
  const cv = await page.$('canvas');
  if(cv){ const box = await cv.boundingBox(); for(let i=0;i<10;i++){ const x=box.x+box.width*(0.08+0.2*(i%5)), y=box.y+box.height*0.25; await page.mouse.click(x,y); await page.waitForTimeout(150); } }
  await page.waitForTimeout(500);
  console.log('DONE');
  await browser.close(); server.close();
})();
