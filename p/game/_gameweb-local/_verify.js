// 全量验证：20 款游戏外壳完整性 + script 语法 + index 卡片唯一性 + 文件大小
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const dir = 'C:/Users/Administrator/ops/gameweb';

const GAMES = ['flip-the-lie.html','reflex-rush.html','tile-match.html','pop-zen.html','mind-match.html',
  'merge-barn.html','odd-spot.html','power-merge.html','neon-snake.html','tap-whack.html',
  'stair-climber.html','color-sort.html','trivia-duel.html','dodge-dash.html','paper-flight.html',
  'rhythm-tap.html','rope-cut.html','word-chain.html','guess-it.html','draw-path.html'];
// 豁免：pop-zen 为纯解压连续型（无里程碑结算，页面内提示设计合理）
const NO_OVERLAY = ['pop-zen.html'];

let fail = 0;
for (const f of GAMES) {
  const p = path.join(dir, f);
  if (!fs.existsSync(p)) { console.log('MISSING:', f); fail++; continue; }
  const c = fs.readFileSync(p, 'utf8');
  const checks = {
    'shell': c.indexOf('xz-shell') >= 0,
    'topbar': c.indexOf('id="topbar"') >= 0,
    'howto': c.indexOf('id="howto"') >= 0,
    'wrap': c.indexOf('id="wrap"') >= 0,
    'overlay': c.indexOf('id="overlay"') >= 0 || NO_OVERLAY.indexOf(f) >= 0,
    'fit': c.indexOf('function fit') >= 0,
    'copyguard': c.indexOf('contextmenu') >= 0,
    'cr': c.indexOf('xz-cr') >= 0,
    'backlink': c.indexOf('index.html') >= 0,
    'pointerdown': c.indexOf('pointerdown') >= 0,
  };
  const bad = Object.entries(checks).filter(([, ok]) => !ok).map(([k]) => k);
  const re = /<script>([\s\S]*?)<\/script>/g;
  let m, sErr = [];
  while ((m = re.exec(c))) { try { new vm.Script(m[1]); } catch (e) { sErr.push(e.message.slice(0, 60)); } }
  const size = c.length;
  if (bad.length || sErr.length || size > 16000) {
    fail++;
    console.log('FAIL:', f, '| missing:', bad.join(','), '| jsErr:', sErr.join('|'), '| size:', size);
  } else {
    console.log('PASS:', f, '| size:', size);
  }
}

// index 检查：卡片唯一
const idx = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
const hrefs = [...idx.matchAll(/href="([^"]+\.html)"/g)].map(m => m[1]);
const dup = hrefs.filter((h, i) => hrefs.indexOf(h) !== i);
console.log('\nindex cards:', hrefs.length, '| unique:', new Set(hrefs).size, '| dup:', dup.length ? dup.join(',') : 'none');
const idxHrefs = new Set(hrefs);
const missing = GAMES.filter(g => !idxHrefs.has(g));
console.log('games not in index:', missing.length ? missing.join(',') : 'none');

console.log(fail ? `\n${fail} FAILED` : '\nALL 20 PASS');
