// 批量改造脚本：为 gameweb 现有 10 款游戏注入统一外壳
// 1) 顶部返回栏 + 玩法说明（可折叠） 2) 390x780 设计基准等比缩放 3) L1 防拷贝 4) 版权注脚
const fs = require('fs');
const path = require('path');
const dir = 'C:/Users/Administrator/ops/gameweb';

const GAMES = [
  { f: 'flip-the-lie.html', n: 'Flip the Lie',  tag: '逆向反应', how: '看提示做<b>相反</b>动作：说"左"点右边，说"红"点蓝色。反应越快分越高，玩的就是反直觉。' },
  { f: 'reflex-rush.html',  n: 'Reflex Rush',   tag: '反应力测试', how: '等方块变绿立刻点击，共 5 轮取平均反应时间，越短越强，可以和朋友比拼谁的手更快。' },
  { f: 'tile-match.html',   n: 'Tile Match',    tag: '记忆翻牌', how: '记住牌面位置，翻开两张配对，全部配对完成用时越短越好。' },
  { f: 'pop-zen.html',      n: 'Pop Zen',       tag: '解压泡泡', how: '点击泡泡消除，连击加分，享受解压爽感，消完一整板有惊喜奖励。' },
  { f: 'mind-match.html',   n: 'Mind Match',    tag: '默契考验', how: '和朋友各自回答同样的问题，答案越一致默契分越高，测测你们有多懂彼此。' },
  { f: 'merge-barn.html',   n: 'Merge Barn',    tag: '合成农场', how: '拖动相同动物合并升级，从鸡蛋一路合成到神兽，目标是<b>农场毕业</b>。' },
  { f: 'odd-spot.html',     n: 'Odd Spot',      tag: '你不对劲', how: '在画面里找出唯一<b>不对劲</b>的那个，找得越快得分越高，考验观察力。' },
  { f: 'power-merge.html',  n: 'Power Merge',   tag: '数字合成', how: '相同数字合并升级，策略规划格子，目标是合出 <b>2048</b>。' },
  { f: 'neon-snake.html',   n: 'Neon Snake',    tag: '霓虹贪吃蛇', how: '控制蛇吃光点变长，别撞墙别咬到自己，经典玩法霓虹赛博风。' },
  { f: 'tap-whack.html',    n: 'Tap Whack',     tag: '打星星', how: '星星冒出来就点它加分，点中炸弹扣分，限时内得分越高越好。' },
];

const CSS = `<style id="xz-shell">
#topbar{position:fixed;top:0;left:0;right:0;height:64px;z-index:50;display:flex;align-items:center;gap:10px;padding:0 14px;background:rgba(15,23,42,.94);backdrop-filter:blur(8px);border-bottom:1px solid #334155;color:#e2e8f0;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;-webkit-user-select:none;user-select:none;}
#topbar a{color:#38bdf8;text-decoration:none;font-size:14px;font-weight:700;display:flex;align-items:center;gap:4px;white-space:nowrap;}
#topbar .tt{flex:1;text-align:center;font-size:15px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
#topbar .tg{font-size:11px;color:#94a3b8;font-weight:400;margin-left:4px;}
#howBtn{width:30px;height:30px;border-radius:50%;border:1px solid #334155;background:#1e293b;color:#94a3b8;font-weight:800;cursor:pointer;font-size:15px;line-height:1;flex:none;}
#howto{display:none;position:fixed;top:72px;left:50%;transform:translateX(-50%);width:min(92vw,420px);z-index:70;background:#1e293b;border:1px solid #475569;border-radius:14px;padding:14px 16px;color:#cbd5e1;font-size:13px;line-height:1.7;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;box-shadow:0 12px 32px rgba(0,0,0,.55);}
#howto.show{display:block;}
#howto b{color:#38bdf8;}
.xz-cr{position:fixed;bottom:4px;right:10px;font-size:10px;color:#475569;z-index:45;font-family:-apple-system,"Segoe UI",sans-serif;pointer-events:none;-webkit-user-select:none;user-select:none;}
</style>`;

const JS = `<script>
(function(){
  'use strict';
  // --- 等比缩放：390x780 设计基准（上方 64px 顶部栏），其它屏幕自动等比 ---
  var W=390,H=780,TOP=64;
  var wrap=document.getElementById('wrap');
  function fit(){
    if(!wrap) return;
    var s=Math.min(innerWidth/W,(innerHeight-TOP)/H);
    if(s>1.4) s=1.4;
    var w=W*s,h=H*s;
    wrap.style.width=w+'px';
    wrap.style.height=h+'px';
    wrap.style.left=((innerWidth-w)/2)+'px';
    wrap.style.top=(TOP+(innerHeight-TOP-h)/2)+'px';
    wrap.style.position='fixed';
    wrap.style.margin='0';
    wrap.style.transform='scale('+s+')';
    wrap.style.transformOrigin='top left';
  }
  fit();
  addEventListener('resize',fit);
  addEventListener('orientationchange',fit);
  // 结算浮层提到顶部栏之上（面板里自带返回入口）
  var ov=document.getElementById('overlay');
  if(ov) ov.style.zIndex=60;
  // --- 玩法说明折叠 ---
  var hb=document.getElementById('howBtn'),ht=document.getElementById('howto');
  if(hb&&ht){
    hb.addEventListener('click',function(e){e.stopPropagation();ht.classList.toggle('show');});
    document.addEventListener('pointerdown',function(e){if(ht.classList.contains('show')&&!ht.contains(e.target)&&e.target!==hb)ht.classList.remove('show');});
  }
  // --- L1 防拷贝：禁右键 / 禁 F12 / 禁 Ctrl+S,U,P / 禁 Ctrl+Shift+I,J,C ---
  document.addEventListener('contextmenu',function(e){e.preventDefault();});
  document.addEventListener('dragstart',function(e){e.preventDefault();});
  document.addEventListener('keydown',function(e){
    var k=e.key||'';
    if(k==='F12'||(e.ctrlKey&&['s','u','p','S','U','P'].indexOf(k)>=0)||(e.ctrlKey&&e.shiftKey&&['i','j','c','I','J','C'].indexOf(k)>=0)){e.preventDefault();e.stopPropagation();return false;}
  });
  // 长按防存图
  document.addEventListener('touchstart',function(){},false);
})();
<\/script>`;

function inject(fn, name, tag, how) {
  const p = path.join(dir, fn);
  let c = fs.readFileSync(p, 'utf8');
  if (c.indexOf('xz-shell') >= 0) { console.log('SKIP(already):', fn); return; }
  // 备份
  fs.writeFileSync(p + '.bak-v1', c);
  const topbar = `<div id="topbar"><a href="index.html">← 列表</a><span class="tt">${name}<span class="tg">${tag}</span></span><button id="howBtn" aria-label="玩法说明">?</button></div>
<div id="howto"><b>怎么玩</b><br>${how}</div>
`;
  // head 尾部插 CSS
  c = c.replace('</head>', CSS + '\n</head>');
  // body 开始后插 topbar
  const bi = c.indexOf('<body>');
  if (bi < 0) { console.log('FAIL no body:', fn); return; }
  c = c.slice(0, bi + 6) + '\n' + topbar + c.slice(bi + 6);
  // </body> 前插 JS + 版权
  c = c.replace('</body>', JS + '\n<div class="xz-cr">© 2026 AI24X Game Zone</div>\n</body>');
  fs.writeFileSync(p, c);
  console.log('OK:', fn);
}

GAMES.forEach(g => inject(g.f, g.n, g.tag, g.how));
console.log('DONE');
