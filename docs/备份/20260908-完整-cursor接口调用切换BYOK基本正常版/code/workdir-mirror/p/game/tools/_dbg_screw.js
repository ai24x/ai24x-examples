const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18785;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  await page.goto(`http://127.0.0.1:${PORT}/screw-hero.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(800);
  const cv = await page.$('canvas');
  const box = await cv.boundingBox();
  const G = box.width / 7.2;
  const lv1 = [[1.6,1.1],[5.6,1.1],[1.6,3.2],[5.6,3.2]];
  for (const [gx,gy] of lv1) {
    await page.mouse.click(box.x + gx*G, box.y + gy*G);
    await page.waitForTimeout(800);
  }
  const dbg = await page.evaluate(() => window.__screwDebug());
  console.log(JSON.stringify(dbg, null, 1));
  await page.waitForTimeout(2000);
  const dbg2 = await page.evaluate(() => window.__screwDebug());
  console.log('AFTER:', JSON.stringify(dbg2));
  await browser.close(); server.close();
})();
