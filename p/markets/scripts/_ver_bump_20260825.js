// 全站版本号统一升级：locales/shell 内容变更 → 20260825a（39 页）
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..', '..');
const WEB = path.join(ROOT, 'web');
const OLD_LOC = 'locales.js?v=20260823b';
const OLD_SHELL = 'shell.js?v=20260823c';
const NEW = '20260825a';
let files = [];
(function walk(dir) {
  for (const d of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, d.name);
    if (d.isDirectory()) walk(p);
    else if (d.name.endsWith('.html')) files.push(p);
  }
})(WEB);
let locOld = 0, shellOld = 0, locNew = 0, shellNew = 0;
for (const f of files) {
  let s = fs.readFileSync(f, 'utf8');
  const lo = s.split(OLD_LOC).length - 1;
  const so = s.split(OLD_SHELL).length - 1;
  if (lo || so) {
    s = s.split(OLD_LOC).join('locales.js?v=' + NEW);
    s = s.split(OLD_SHELL).join('shell.js?v=' + NEW);
    fs.writeFileSync(f, s, 'utf8');
    locOld += lo; shellOld += so;
  }
  const ln = s.split('locales.js?v=' + NEW).length - 1;
  const sn = s.split('shell.js?v=' + NEW).length - 1;
  locNew += ln; shellNew += sn;
}
console.log('files=' + files.length + ' locOld=' + locOld + ' shellOld=' + shellOld + ' locNew=' + locNew + ' shellNew=' + shellNew);
if (locOld !== locNew || shellOld !== shellNew) {
  console.error('VERSION BUMP MISMATCH');
  process.exit(1);
}
