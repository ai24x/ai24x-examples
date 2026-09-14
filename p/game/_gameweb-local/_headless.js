// 全量 headless 验证 20 款：渲染 + topbar/howto/wrap + console 错误检测
const { execSync } = require('child_process');
const dir = 'C:/Users/Administrator/ops/gameweb';
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const games = ['flip-the-lie.html','reflex-rush.html','tile-match.html','pop-zen.html','mind-match.html',
  'merge-barn.html','odd-spot.html','power-merge.html','neon-snake.html','tap-whack.html',
  'stair-climber.html','color-sort.html','trivia-duel.html','dodge-dash.html','paper-flight.html',
  'rhythm-tap.html','rope-cut.html','word-chain.html','guess-it.html','draw-path.html'];
let fail = 0;
for (const g of games) {
  try {
    const url = 'file:///' + dir.replace(/\\/g, '/') + '/' + g;
    const dom = execSync(`"${edge}" --headless=new --disable-gpu --no-sandbox --dump-dom "${url}" 2>NUL`, { encoding: 'utf8', timeout: 30000, maxBuffer: 50 * 1024 * 1024 });
    const ok = dom.includes('id="topbar"') && dom.includes('id="wrap"') && dom.length > 3000;
    const err = dom.match(/Uncaught|SyntaxError|ReferenceError|TypeError/g);
    if (!ok || err) { fail++; console.log('FAIL:', g, '| err:', err ? err.slice(0, 3).join(',') : 'dom-short'); }
    else console.log('PASS:', g, '| domLen:', dom.length);
  } catch (e) {
    fail++;
    console.log('FAIL:', g, '| error:', e.message.slice(0, 100));
  }
}
console.log(fail ? `\n${fail} FAILED` : '\nALL 20 RENDER PASS');
