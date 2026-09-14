const fs = require('fs');
const path = require('path');
const dir = 'C:/Users/Administrator/ops/gameweb';
for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.html') && f !== 'index.html')) {
  const c = fs.readFileSync(path.join(dir, f), 'utf8');
  const i = x => c.indexOf(x);
  console.log(f, '| body:', i('<body>'), 'wrap:', i('id="wrap"'), 'stage:', i('id="stage"'), 'canvas:', i('<canvas'), 'overlay:', i('id="overlay"'), 'dvh:', i('100dvh'), 'vh:', i('100vh'), 'size:', c.length);
}
