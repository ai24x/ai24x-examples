const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18786;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];
  page.on('pageerror', e=>errors.push('PAGEERROR: '+e.message));
  page.on('console', m=>{if(m.type()==='error'&&!m.text().includes('favicon')) errors.push('CONSOLE: '+m.text());});
  await page.goto(`http://127.0.0.1:${PORT}/screw-hero.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(600);
  const cv = await page.$('canvas');
  const box = await cv.boundingBox();
  const G = box.width / 7.2;
  const levels = [
    [[1.6,1.1],[5.6,1.1],[1.6,3.2],[5.6,3.2]],
    [[1.5,1.0],[3.6,1.0],[5.7,1.0],[1.5,3.0],[3.6,3.0],[5.7,3.0]],
    [[1.4,1.0],[3.6,1.0],[5.8,1.0],[2.5,2.8],[4.7,2.8],[1.4,4.5],[3.6,4.5],[5.8,4.5]],
    [[1.2,1.0],[3.0,1.0],[4.8,1.0],[6.0,1.0],[1.2,2.9],[3.0,2.9],[4.8,2.9],[6.0,2.9],[2.1,4.6],[3.9,4.6],[5.7,4.6]],
    [[1.1,1.0],[2.5,1.0],[3.9,1.0],[5.3,1.0],[6.1,1.0],[1.1,2.7],[2.5,2.7],[3.9,2.7],[5.3,2.7],[6.1,2.7],[1.8,4.4],[3.3,4.4],[4.8,4.4]]
  ];
  for (let lv=0; lv<levels.length; lv++) {
    const screws = levels[lv];
    for (const [gx,gy] of screws) {
      await page.mouse.click(box.x + gx*G, box.y + gy*G);
      await page.waitForTimeout(260);
    }
    await page.waitForTimeout(1800);
    const st = await page.evaluate(() => ({
      overlay: document.getElementById('overlay').classList.contains('show'),
      title: document.getElementById('ovT').textContent,
      secs: document.getElementById('secs').textContent,
      rank: document.getElementById('rankLine').textContent.slice(0,50)
    }));
    console.log('L'+(lv+1)+':', JSON.stringify(st));
    if (!st.overlay) { console.log('FAIL at L'+(lv+1)); break; }
    if (lv < levels.length-1) {
      const nextVis = await page.$eval('#nextBtn', el => el.style.display !== 'none').catch(()=>false);
      if (nextVis) { await page.click('#nextBtn'); await page.waitForTimeout(600); }
      else { console.log('NO NEXT BTN at L'+(lv+1)); break; }
    }
  }
  console.log('ERRORS:', errors.length ? errors.join(' | ') : 'none');
  await browser.close(); server.close();
})();
