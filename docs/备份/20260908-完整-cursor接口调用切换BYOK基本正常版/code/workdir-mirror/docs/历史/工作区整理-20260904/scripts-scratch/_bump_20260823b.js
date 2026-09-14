const fs = require('fs');
const path = require('path');
const root = path.resolve('web');
const pairs = [
  ['locales.js?v=20260823a', 'locales.js?v=20260823b'],
  ['console.js?v=20260823a', 'console.js?v=20260823b'],
];
let files = 0, changed = 0;
const bumps = {};
function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (e.isFile() && e.name.endsWith('.html')) {
      files++;
      let s = fs.readFileSync(p, 'utf8');
      let hit = false;
      for (const [from, to] of pairs) {
        if (s.includes(from)) {
          s = s.split(from).join(to);
          hit = true;
          bumps[from] = (bumps[from] || 0) + 1;
        }
      }
      if (hit) {
        fs.writeFileSync(p, s, 'utf8');
        changed++;
      }
    }
  }
}
walk(root);
console.log('html scanned:', files, '| changed:', changed, '|', JSON.stringify(bumps));
