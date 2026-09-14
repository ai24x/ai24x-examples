// 给 merge-barn / power-merge 补里程碑结算浮层（毕业/2048），统一 20 款结算体验 + 分享钩子
const fs = require('fs');
const path = require('path');
const dir = 'C:/Users/Administrator/ops/gameweb';

const OVERLAY_CSS = `<style id="xz-mz">
#overlay{position:fixed;inset:0;background:rgba(2,6,23,.9);display:none;align-items:center;justify-content:center;z-index:10;}
#overlay.show{display:flex;}
#overlay .panel{text-align:center;padding:30px 26px;border-radius:20px;background:#1e293b;border:1px solid #334155;max-width:320px;width:90%;}
#overlay .panel h2{font-size:22px;margin-bottom:6px;}
#overlay .grade{font-size:44px;font-weight:800;color:#38bdf8;margin:6px 0 2px;}
#overlay .avg{color:#94a3b8;font-size:14px;margin-bottom:12px;}
#overlay .share{font-size:13px;color:#fbbf24;margin-bottom:16px;padding:8px 12px;background:#1e293b;border:1px dashed #475569;border-radius:10px;}
#overlay .play{background:linear-gradient(90deg,#38bdf8,#6366f1);border:none;color:#fff;font-size:17px;font-weight:800;padding:12px 36px;border-radius:999px;cursor:pointer;box-shadow:0 6px 0 rgba(0,0,0,.3);touch-action:manipulation;}
#overlay .play:active{transform:translateY(3px);box-shadow:0 3px 0 rgba(0,0,0,.3);}
</style>`;

function inject(fn, overlayHTML, triggerOld, triggerNew, againBtnId) {
  const p = path.join(dir, fn);
  let c = fs.readFileSync(p, 'utf8');
  if (c.indexOf('xz-mz') >= 0) { console.log('SKIP(already):', fn); return; }
  fs.writeFileSync(p + '.bak-v2', c);
  // 1) CSS 插到 </head> 前
  c = c.replace('</head>', OVERLAY_CSS + '\n</head>');
  // 2) overlay HTML 插到第一个 <script> 前（wrap 结束之后）
  const si = c.indexOf('<script>');
  if (si < 0) { console.log('FAIL no script:', fn); return; }
  c = c.slice(0, si) + overlayHTML + '\n' + c.slice(si);
  // 3) 触发逻辑替换
  if (c.indexOf(triggerOld) < 0) { console.log('FAIL trigger not found:', fn, '|', triggerOld.slice(0, 60)); return; }
  c = c.split(triggerOld).join(triggerNew);
  // 4) 按钮绑定：在最后一个 </script> 前注入
  const lastScript = c.lastIndexOf('</script>');
  const bind = `\n  var mzBtn=document.getElementById('${againBtnId}'),mzOv=document.getElementById('overlay');\n  if(mzBtn&&mzOv){ mzBtn.addEventListener('pointerdown',function(e){e.preventDefault();mzOv.classList.remove('show');}); }\n`;
  c = c.slice(0, lastScript) + bind + c.slice(lastScript);
  fs.writeFileSync(p, c);
  console.log('OK:', fn);
}

// merge-barn：农场毕业
inject('merge-barn.html',
  `<div id="overlay"><div class="panel"><h2>🏆 农场毕业！</h2><div class="grade">凤凰合体成功</div><div class="avg">最高 <b id="mBest">-</b> 级 · 共合成 <b id="mCount">0</b> 次</div><div class="share">我在合成农场合出了凤凰！🏆 你来挑战吗？</div><button class="play" id="mzAgain">继续养殖</button></div></div>`,
  `if(maxLevel>=MAXLV){ msgEl.textContent='🏆 合出凤凰！农场毕业了！'; }`,
  `if(maxLevel>=MAXLV){ msgEl.textContent='🏆 合出凤凰！农场毕业了！'; var mzOv=document.getElementById('overlay'); if(mzOv){ document.getElementById('mBest').textContent=(maxLevel+1); document.getElementById('mCount').textContent=merges; mzOv.classList.add('show'); } }`,
  'mzAgain');

// power-merge：合出 2048
inject('power-merge.html',
  `<div id="overlay"><div class="panel"><h2>🏆 合出 2048！</h2><div class="grade">数字大师</div><div class="avg">最高 <b id="mBest">-</b> · 共合并 <b id="mCount">0</b> 次</div><div class="share">我合出了 2048！🧠 你能做到吗？</div><button class="play" id="mzAgain">继续挑战</button></div></div>`,
  `if(nv>=2048){ msgEl.textContent='🏆 合出 2048！'; }`,
  `if(nv>=2048){ msgEl.textContent='🏆 合出 2048！'; var mzOv=document.getElementById('overlay'); if(mzOv){ document.getElementById('mBest').textContent=nv; document.getElementById('mCount').textContent=merges; mzOv.classList.add('show'); } }`,
  'mzAgain');

console.log('DONE');
