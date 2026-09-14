const fs = require('fs');
const path = require('path');
const ROOT = 'E:/AI24X/ai24x-website/ai24x01/p/game/_gameweb-local';
const files = fs.readdirSync(ROOT).filter(f => f.endsWith('.html') && !f.startsWith('_') && !f.includes('.bak')).sort();
for (const f of files) {
  const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
  const how = (src.match(/id="howto"[^>]*>([\s\S]*?)<\/div>/) || [])[1] || '';
  const clean = how.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const ids = [...src.matchAll(/id="([a-zA-Z][a-zA-Z0-9_-]*)"/g)].map(m => m[1]);
  console.log('=== ' + f);
  console.log('  HOW: ' + (clean.slice(0, 160) || '(none)'));
  console.log('  IDS: ' + ids.join(','));
}
