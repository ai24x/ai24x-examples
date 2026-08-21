/* 静态 QA：验证 markets app.html 图表标记英文翻译全覆盖（无中文漏出） */
const fs = require('fs');
const path = require('path');

const appPath = path.resolve(__dirname, '..', 'web', 'app.html');
const html = fs.readFileSync(appPath, 'utf8');

// 1) 提取 MARKER_MAP 对象源码
const mStart = html.indexOf('var MARKER_MAP = {');
const mEnd = html.indexOf('};', mStart);
if (mStart < 0 || mEnd < 0) { console.error('MARKER_MAP not found'); process.exit(1); }
const mapSrc = html.slice(mStart + 'var MARKER_MAP = '.length, mEnd + 1);

// 2) 提取 markerText 函数源码（括号计数），在沙箱中定义
const fStart = html.indexOf('function markerText(text) {');
if (fStart < 0) { console.error('markerText not found'); process.exit(1); }
let depth = 0, fEnd = fStart;
for (let i = fStart; i < html.length; i++) {
  if (html[i] === '{') depth++;
  else if (html[i] === '}') { depth--; if (depth === 0) { fEnd = i + 1; break; } }
}
const fnBody = html.slice(fStart, fEnd).replace('function markerText(text) {', 'markerText = function (text) {');

const MARKER_MAP = eval('(' + mapSrc + ')');
let markerText;
const state = { lang: 'en' };
eval(fnBody + ';');

// 3) 共享引擎可能输出的全部标签 + 常见组合
const engineTags = ['小底', '底1', '底2', '金1', '金2', '金3', '买2', '卖1', '卖2', '险1', '险2', '破', '↗', '↘'];
const combos = ['底1·底2', '金1·买2', '卖1·卖2', '险1·破', '险2·破', '底1·买2', '金1·金2'];
const cases = engineTags.concat(combos, ['', '\u200b']);

const CJK = /[\u4e00-\u9fff]/;
let fail = 0;
// 英文模式：零中文
for (const c of cases) {
  const en = markerText(c);
  const leak = CJK.test(en);
  if (leak) { console.error('CJK LEAK:', JSON.stringify(c), '->', JSON.stringify(en)); fail++; }
  else console.log('ok:', JSON.stringify(c), '->', JSON.stringify(en));
}
// 中文模式：标记同样必须英文（国际版图表标记固定英文）
state.lang = 'zh';
for (const c of cases) {
  const en = markerText(c);
  if (CJK.test(en)) { console.error('ZH-MODE CJK LEAK:', JSON.stringify(c), '->', JSON.stringify(en)); fail++; }
}
state.lang = 'en';

// 4) 覆盖性检查：引擎单个标签必须在映射里（英文模式下不得原样透出中文）
for (const t of engineTags) {
  if (!MARKER_MAP[t]) { console.error('MISSING MAP KEY:', t); fail++; }
}

// 5) 合规禁词扫描（英文译名不得含 buy/sell/hold/...）
const banned = /\b(buy|sell|hold|target|guarantee|advice|advisor|signal|recommend|tips|picks|broker|trade)\b/i;
for (const k of Object.keys(MARKER_MAP)) {
  const en = MARKER_MAP[k].en || '';
  if (banned.test(en)) { console.error('BANNED WORD in en:', k, en); fail++; }
}

console.log(fail === 0 ? 'MARKER_EN_QA_OK' : 'MARKER_EN_QA_FAIL');
process.exit(fail === 0 ? 0 : 1);
