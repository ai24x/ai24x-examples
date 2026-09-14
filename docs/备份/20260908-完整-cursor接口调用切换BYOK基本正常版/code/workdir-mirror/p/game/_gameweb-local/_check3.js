// 验收脚本：语法检查 + 大小限制 + 无外链 + Edge headless 冒烟（抓 Uncaught/console 错误）
const fs = require('fs');
const { execSync } = require('child_process');
const dir = 'C:/Users/Administrator/ops/gameweb';
const files = ['color-sort.html','trivia-duel.html','dodge-dash.html'];
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
let fail = 0;
for (const f of files) {
  const html = fs.readFileSync(dir + '/' + f, 'utf8');
  const size = Buffer.byteLength(html, 'utf8');
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  let ok = true;
  scripts.forEach((code, i) => {
    try { new Function(code); } catch (e) { ok = false; console.log(f, 'script#' + i, 'SYNTAX ERROR:', e.message); }
  });
  const ext = /https?:\/\//.test(html) ? 'HAS-EXTERNAL-URL!' : 'no-external';
  // 游戏逻辑脚本(#0)禁止 click，统一外壳脚本(#1)的 howBtn 用 click 是模板既定行为
  const gameClick = /addEventListener\(\s*'click'/.test(scripts[0] || '') ? 'GAME-HAS-CLICK!' : 'game-no-click';
  console.log(f, size + 'B', size <= 14336 ? '<=14KB' : 'TOO-BIG', 'scripts:' + scripts.length, ok ? 'syntax-ok' : 'SYNTAX-FAIL', ext, gameClick);
  if (!ok || size > 14336 || ext !== 'no-external' || gameClick !== 'game-no-click') fail = 1;
  try {
    const url = 'file:///' + dir.replace(/\\/g, '/') + '/' + f;
    const out = execSync(`"${edge}" --headless=new --disable-gpu --no-sandbox --enable-logging=stderr --v=0 --virtual-time-budget=2500 --dump-dom "${url}" 2>&1`, { encoding: 'utf8', timeout: 45000, maxBuffer: 100 * 1024 * 1024 });
    const uncaught = (out.match(/Uncaught[^\r\n]*/g) || []).filter(x => !x.includes('Uncaught (in promise) 0')).slice(0, 3);
    const consoleErrs = (out.match(/ERROR:CONSOLE[^\r\n]*/g) || []).slice(0, 3);
    const domPart = out.slice(out.lastIndexOf('<!DOCTYPE'), out.lastIndexOf('</html>') + 7);
    const hasWrap = domPart.includes('id="wrap"');
    const hasHow = domPart.includes('id="howto"') && domPart.includes('怎么玩');
    console.log('   headless: domLen=' + domPart.length, 'wrap=' + hasWrap, 'howto=' + hasHow,
      'uncaught=' + (uncaught.length ? uncaught.join(' | ') : 'none'),
      'consoleErr=' + (consoleErrs.length ? consoleErrs.join(' | ') : 'none'));
    if (!hasWrap || !hasHow || uncaught.length) fail = 1;
  } catch (e) { console.log('   headless ERROR:', e.message.slice(0, 200)); fail = 1; }
}
console.log(fail ? 'RESULT: FAIL' : 'RESULT: PASS');
process.exit(fail);
