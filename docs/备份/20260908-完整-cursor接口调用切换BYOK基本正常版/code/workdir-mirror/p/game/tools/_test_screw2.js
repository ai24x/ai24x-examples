const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18784;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  page.on('pageerror', e=>console.log('PAGEERROR:', e.message));
  await page.goto(`http://127.0.0.1:${PORT}/screw-hero.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(800);
  // 读取 canvas 尺寸和螺丝预期位置
  const info = await page.evaluate(() => {
    const stage = document.getElementById('stage');
    const r = stage.getBoundingClientRect();
    const cv = document.getElementById('cv');
    return { W: r.width, H: r.height, cvW: cv.width, cvH: cv.height, dpr: window.devicePixelRatio };
  });
  console.log('info:', JSON.stringify(info));
  const cv = await page.$('canvas');
  const box = await cv.boundingBox();
  const G = box.width / 7.2;
  console.log('box:', JSON.stringify(box), 'G=', G);
  // 逐个点击螺丝并打印点击后 canvas 像素变化/overlay
  const lv1 = [[1.6,1.1],[5.6,1.1],[1.6,3.2],[5.6,3.2]];
  for (const [gx,gy] of lv1) {
    const px = box.x + gx*G, py = box.y + gy*G;
    await page.mouse.click(px, py);
    await page.waitForTimeout(700);
    const st = await page.evaluate(() => ({
      overlay: document.getElementById('overlay').classList.contains('show'),
      tip: document.getElementById('tip').textContent,
      combo: document.getElementById('combo').textContent,
      left: document.getElementById('left').textContent
    }));
    console.log('click', gx, gy, '->', JSON.stringify(st));
  }
  await page.waitForTimeout(2500);
  const st2 = await page.evaluate(() => ({
    overlay: document.getElementById('overlay').classList.contains('show'),
    tip: document.getElementById('tip').textContent,
    secs: document.getElementById('secs').textContent,
    stars: document.getElementById('stars').textContent
  }));
  console.log('final:', JSON.stringify(st2));
  await page.screenshot({path:'E:/AI24X/ai24x-website/ai24x01/p/game/tools/_screw2.png'});
  await browser.close(); server.close();
})();
