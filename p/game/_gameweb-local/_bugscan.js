// 检查原 10 款游戏：事件绑定方式（click vs pointer）+ 潜在 bug 点
const fs = require('fs');
const path = require('path');
const dir = 'C:/Users/Administrator/ops/gameweb';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.html') && !f.startsWith('_') && !f.startsWith('stair'));
for (const f of files) {
  const c = fs.readFileSync(path.join(dir, f), 'utf8');
  const clicks = (c.match(/addEventListener\('click'/g) || []).length;
  const ptr = (c.match(/addEventListener\('pointer/g) || []).length;
  const touch = (c.match(/addEventListener\('touch/g) || []).length;
  const clientX = (c.match(/clientX|clientY/g) || []).length;
  const offset = (c.match(/offsetX|offsetY/g) || []).length;
  const getBCR = (c.match(/getBoundingClientRect/g) || []).length;
  const innerH = (c.match(/innerHeight/g) || []).length;
  const fixed = (c.match(/position:\s*fixed/g) || []).length;
  console.log(f.padEnd(22), 'click:'+clicks, 'pointer:'+ptr, 'touch:'+touch, 'clientXY:'+clientX, 'offsetXY:'+offset, 'getBCR:'+getBCR, 'innerH:'+innerH, 'fixedCSS:'+fixed);
}
