const fs = require('fs');
const path = require('path');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const files = fs.readdirSync(ROOT).filter(f => f.endsWith('.html') && !f.startsWith('_') && !f.includes('.bak'));
let issues = [];
for (const f of files) {
  const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
  // 收集所有 id 定义
  const idDefs = new Set();
  const idRe = /\bid=["']([^"']+)["']/g;
  let m;
  while ((m = idRe.exec(src))) idDefs.add(m[1]);
  // 收集 getElementById 引用
  const refRe = /getElementById\(['"]([^'"]+)['"]\)/g;
  const missing = new Set();
  while ((m = refRe.exec(src))) if (!idDefs.has(m[1])) missing.add(m[1]);
  if (missing.size) issues.push({ file: f, missing: [...missing] });
  // 检查 querySelector('#xx') 引用
  const qsRe = /querySelector\(['"]#([a-zA-Z0-9_-]+)['"]\)/g;
  const missingQs = new Set();
  while ((m = qsRe.exec(src))) if (!idDefs.has(m[1])) missingQs.add(m[1]);
  if (missingQs.size) issues.push({ file: f + ' (querySelector)', missing: [...missingQs] });
}
if (!issues.length) console.log('NO_MISSING_ID');
else issues.forEach(i => console.log('MISSING_ID', i.file, JSON.stringify(i.missing)));
