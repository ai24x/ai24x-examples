const fs = require('fs');
const path = require('path');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const files = fs.readdirSync(ROOT).filter(f => f.endsWith('.html') && !f.startsWith('_') && !f.includes('.bak') && f !== 'index.html').sort();
for (const f of files) {
  const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
  const touchCount = (src.match(/touchstart|touchmove|touchend|pointerdown|pointerup|pointermove/g) || []).length;
  const clickCount = (src.match(/addEventListener\('click'|addEventListener\("click"|\.onclick/g) || []).length;
  const mouseCount = (src.match(/mousedown|mouseup|mousemove/g) || []).length;
  const audios = (src.match(/new Audio\(|AudioContext/g) || []).length;
  const hasCanvas = src.includes('<canvas');
  console.log(`${f.padEnd(22)} touch/ptr=${String(touchCount).padStart(3)} click=${String(clickCount).padStart(3)} mouse=${String(mouseCount).padStart(3)} audio=${audios} canvas=${hasCanvas}`);
}
