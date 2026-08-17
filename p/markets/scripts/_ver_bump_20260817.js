// 2026-08-17 全站共享资源版本号统一升级（shell/locales/console.js）· 第二轮 f→g / console g→h
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..', '..'); // repo root
const WEB = path.join(ROOT, 'web');

const MAP = [
  ['shell.js?v=20260818f', 'shell.js?v=20260818g'],
  ['locales.js?v=20260818f', 'locales.js?v=20260818g'],
  ['console.js?v=20260818f', 'console.js?v=20260818g'],
  ['console.js?v=20260818g', 'console.js?v=20260818h'],
];

function walk(dir) {
  let out = [];
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) {
      if (name === 'node_modules' || name === '.git') continue;
      out = out.concat(walk(p));
    } else if (/\.html$/i.test(name)) {
      out.push(p);
    }
  }
  return out;
}

let changed = 0;
const touched = [];
for (const file of walk(WEB)) {
  let src = fs.readFileSync(file, 'utf8');
  let cur = src;
  for (const [a, b] of MAP) {
    cur = cur.split(a).join(b);
  }
  if (cur !== src) {
    fs.writeFileSync(file, cur, 'utf8');
    changed++;
    touched.push(path.relative(ROOT, file));
  }
}

// 校验残留
let left = 0;
for (const [a] of MAP) {
  for (const file of walk(WEB)) {
    const src = fs.readFileSync(file, 'utf8');
    if (src.includes(a)) {
      left++;
      console.log('RESIDUAL', a, file);
    }
  }
}

console.log('changed:', changed, 'residual:', left);
