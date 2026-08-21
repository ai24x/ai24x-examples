/* 实时校验：18012 全部白名单标的的实际 markers 经翻译后零中文 */
const fs = require('fs');
const path = require('path');

const appPath = path.resolve(__dirname, '..', 'web', 'app.html');
const html = fs.readFileSync(appPath, 'utf8');

const mStart = html.indexOf('var MARKER_MAP = {');
const mEnd = html.indexOf('};', mStart);
const mapSrc = html.slice(mStart + 'var MARKER_MAP = '.length, mEnd + 1);
const fStart = html.indexOf('function markerText(text) {');
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

const CJK = /[\u4e00-\u9fff]/;
const syms = ['^DJI', '^IXIC', '^GSPC', '^VIX', 'AAPL', 'NVDA', 'SPY', 'QQQ'];
const tags = new Set();
let fail = 0;

for (const s of syms) {
  const url = 'http://127.0.0.1:18012/api/signals?symbol=' + encodeURIComponent(s) + '&period=day&count=500';
  const resp = JSON.parse(require('child_process').execSync(
    'curl -s --max-time 60 "' + url + '"', { encoding: 'utf8' }));
  if (resp.code !== 0) { console.error('API fail', s, resp.msg); fail++; continue; }
  for (const m of resp.data.markers || []) {
    const t = String(m.text || '').replace(/\u200b/g, '').trim();
    if (t) tags.add(t);
  }
}

for (const t of [...tags].sort()) {
  const en = markerText(t);
  if (CJK.test(en)) { console.error('LIVE CJK LEAK:', JSON.stringify(t), '->', JSON.stringify(en)); fail++; }
  else console.log('ok:', JSON.stringify(t), '->', JSON.stringify(en));
}
console.log('live_tags=' + tags.size);
console.log(fail === 0 ? 'MARKER_LIVE_OK' : 'MARKER_LIVE_FAIL');
process.exit(fail === 0 ? 0 : 1);
