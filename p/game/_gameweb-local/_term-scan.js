// 检查内部说辞
const fs = require('fs');
const path = require('path');
const dir = 'C:/Users/Administrator/ops/gameweb';
const terms = ['矩阵', '备用项目', '出一个上一个', '内部', 'v1.0', 'v2.0'];
for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.html'))) {
  const c = fs.readFileSync(path.join(dir, f), 'utf8');
  const hits = terms.filter(t => c.includes(t));
  if (hits.length) console.log(f, '->', hits.join(','));
}
console.log('scan done');
