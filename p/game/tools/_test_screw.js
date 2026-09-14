const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18783;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];
  page.on('pageerror', e=>errors.push('PAGEERROR: '+e.message+' @ '+(e.stack||'').split('\n')[1]));
  page.on('console', m=>{if(m.type()==='error') errors.push('CONSOLE: '+m.text());});
  await page.goto(`http://127.0.0.1:${PORT}/screw-hero.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(800);
  // 读关卡状态
  const cv = await page.$('canvas');
  const box = await cv.boundingBox();
  const G = box.width / 7.2;
  // 第1关螺丝位置 (x*G, y*G)
  const lv1 = [[1.6,1.1],[5.6,1.1],[1.6,3.2],[5.6,3.2]];
  for (const [gx,gy] of lv1) {
    await page.mouse.click(box.x + gx*G, box.y + gy*G);
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(1500);
  const overlayVisible = await page.$eval('#overlay', el => el.classList.contains('show')).catch(()=>false);
  console.log('L1 overlay after all screws:', overlayVisible);
  const left1 = await page.$eval('#left', el => el.textContent).catch(()=>'?');
  console.log('L1 left:', left1);
  // 点下一关
  if (overlayVisible) {
    await page.click('#nextBtn');
    await page.waitForTimeout(500);
    const lvNow = await page.$eval('#lv', el => el.textContent);
    console.log('L2 lv:', lvNow);
  }
  // 截图
  await page.screenshot({path:'E:/AI24X/ai24x-website/ai24x01/p/game/tools/_screw-hero.png'});
  console.log('ERRORS:', errors.length ? errors.join(' | ') : 'none');
  await browser.close(); server.close();
})();
