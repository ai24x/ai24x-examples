const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const PORT = 18789;
const server = http.createServer((req,res)=>{const p=path.join(ROOT,decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);res.end();return;} res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}); fs.createReadStream(p).pipe(res);});
const ARROWS = ['↑','→','↓','←'];
const DR = [[-1,0],[0,1],[1,0],[0,-1]];
const dirOf = (a,b) => { const dr=b[0]-a[0], dc=b[1]-a[1]; if(dr===-1) return 0; if(dc===1) return 1; if(dr===1) return 2; return 3; };

async function solve(page) {
  const grid = await page.evaluate(() => {
    const cells = [...document.querySelectorAll('.cell')];
    return cells.map(c => c.textContent || '');
  });
  const N = 7;
  const dirs = [];
  for (let r=0;r<N;r++){ dirs.push([]); for(let c=0;c<N;c++) dirs[r][c] = ARROWS.indexOf(grid[r*N+c]); }
  // BFS: 状态=(r,c)，转移=把当前格旋转到4个方向之一
  const parent = {}; const start='0,0', end=(N-1)+','+(N-1);
  const q=[{key:start, r:0, c:0}];
  const visited = new Set([start]);
  let goal = null;
  while(q.length) {
    const cur = q.shift();
    if (cur.key === end) { goal = cur; break; }
    for (let d=0; d<4; d++) {
      const nr = cur.r + DR[d][0], nc = cur.c + DR[d][1];
      if (nr<0||nr>=N||nc<0||nc>=N) continue;
      const nk = nr+','+nc;
      if (visited.has(nk)) continue;
      visited.add(nk);
      parent[nk] = { from: cur.key, rot: (d - dirs[cur.r][cur.c] + 4) % 4 };
      q.push({key:nk, r:nr, c:nc});
    }
  }
  if (!goal) return null;
  // 回溯
  const moves = [];
  let k = goal.key;
  while (k !== start) {
    const p = parent[k];
    moves.push({ cell: p.from, rot: p.rot });
    k = p.from;
  }
  moves.reverse();
  return { moves, totalRot: moves.reduce((a,m)=>a+m.rot,0) };
}

(async()=>{
  await new Promise(r=>server.listen(PORT,r));
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];
  page.on('pageerror', e=>errors.push('PAGEERROR: '+e.message+' @ '+(e.stack||'').split('\n')[1]));
  page.on('console', m=>{if(m.type()==='error'&&!m.text().includes('favicon')) errors.push('CONSOLE: '+m.text());});
  await page.goto(`http://127.0.0.1:${PORT}/arrow-maze.html`,{waitUntil:'load',timeout:15000});
  await page.waitForTimeout(600);
  const box = await (await page.$('#board')).boundingBox();
  const cw = box.width/7, ch = box.height/7;
  const clickCell = async (r,c,times) => { for(let i=0;i<times;i++){ await page.mouse.click(box.x + c*cw + cw/2, box.y + r*ch + ch/2); await page.waitForTimeout(120); } };
  for (let lv=0; lv<5; lv++) {
    const sol = await solve(page);
    if (!sol) { console.log('L'+(lv+1)+': NO SOLUTION'); break; }
    for (const m of sol.moves) {
      const [r,c] = m.cell.split(',').map(Number);
      await clickCell(r,c,m.rot);
    }
    await page.click('#goBtn');
    await page.waitForTimeout(800);
    const st = await page.evaluate(() => ({
      overlay: document.getElementById('overlay').classList.contains('show'),
      ovT: document.getElementById('ovT').textContent,
      stars: document.getElementById('stars').textContent,
      rot: document.getElementById('rotLine').textContent
    }));
    console.log('L'+(lv+1)+': solved rot='+sol.totalRot, JSON.stringify(st));
    if (!st.overlay) { console.log('FAIL at L'+(lv+1)); break; }
    if (lv<4) { await page.click('#restart'); await page.waitForTimeout(700); }
  }
  console.log('ERRORS:', errors.length ? errors.join(' | ') : 'none');
  await browser.close(); server.close();
})();
