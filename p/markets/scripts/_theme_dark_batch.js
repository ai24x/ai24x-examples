// 2026-08-16 www 全站统一深色：批量替换 theme-blue -> theme-dark
// 机械替换，UTF-8 无 BOM。privacy/terms 补主题引用与 body class。
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../../../web');

function walk(dir) {
  let out = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) out = out.concat(walk(p));
    else if (ent.name.endsWith('.html')) out.push(p);
  }
  return out;
}

const files = walk(ROOT);
let changed = 0;
const reports = [];

for (const f of files) {
  const rel = path.relative(ROOT, f).replace(/\\/g, '/');
  let s = fs.readFileSync(f, 'utf8');
  let count = 0;
  let before = s;

  // 主题 CSS 引用 + body class（双引号与单引号两种写法）
  const reps = [
    ['theme-blue.css', 'theme-dark.css'],
    ['class="theme-blue"', 'class="theme-dark"'],
    ["class='theme-blue'", "class='theme-dark'"],
    ['data-theme="blue"', 'data-theme="dark"'],
  ];
  for (const [a, b] of reps) {
    if (s.includes(a)) {
      count += s.split(a).length - 1;
      s = s.split(a).join(b);
    }
  }

  // privacy/terms：无主题引用，补深色主题链接与 body class
  if ((rel === 'privacy.html' || rel === 'terms.html') && !s.includes('theme-dark.css')) {
    const anchor = 'href="css/base.css?v=20260812e"';
    const themeLink =
      '<link id="theme-css" rel="stylesheet" href="css/themes/theme-dark.css?v=20260812e" data-base="css/themes/" />';
    if (s.includes(anchor)) {
      s = s.split(anchor).join(anchor + '\n' + themeLink);
      count++;
    }
    if (/<body>/.test(s)) {
      s = s.replace(/<body>/, '<body class="theme-dark">');
      count++;
    }
  }

  if (s !== before) {
    fs.writeFileSync(f, s, 'utf8');
    changed++;
    reports.push(`${rel} (${count})`);
  }
}

console.log(`files_changed=${changed}`);
for (const r of reports) console.log('  ' + r);

// 校验残留
let residual = 0;
for (const f of files) {
  const s = fs.readFileSync(f, 'utf8');
  const m = s.match(/theme-blue/g);
  if (m) {
    residual += m.length;
    console.log('RESIDUAL ' + path.relative(ROOT, f).replace(/\\/g, '/') + ': ' + m.length);
  }
}
console.log(`residual_theme_blue=${residual}`);
process.exit(residual === 0 ? 0 : 1);
