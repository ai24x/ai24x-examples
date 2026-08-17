const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../../..');
const REPL = [
  ['locales.js?v=20260818i', 'locales.js?v=20260818j'],
  ['shell.js?v=20260818i', 'shell.js?v=20260818j'],
  ['console.js?v=20260818i', 'console.js?v=20260818j'],
  ['i18n.js?v=20260812g', 'i18n.js?v=20260818j'],
];
let total = 0;
const files = [];
(function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) { if (name !== 'node_modules' && name !== '.git') walk(p); continue; }
    if (!/\.html$/i.test(name)) continue;
    let src = fs.readFileSync(p, 'utf8');
    let changed = false;
    for (const [a, b] of REPL) {
      if (src.indexOf(a) >= 0) { src = src.split(a).join(b); changed = true; }
    }
    if (changed) { fs.writeFileSync(p, src, 'utf8'); total++; files.push(path.relative(ROOT, p)); }
  }
})(path.join(ROOT, 'web'));
console.log('bumped files: ' + total);
console.log(files.join('\n'));
