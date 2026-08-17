const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../../..');
const stub = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>AI24X Developer Portal</title>
<meta http-equiv="refresh" content="0; url=https://open.ai24x.com" />
<link rel="canonical" href="https://open.ai24x.com" />
<style>
  body{margin:0;background:#0b0f14;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;}
  .box{max-width:520px;padding:32px;text-align:center;}
  h1{font-size:1.35rem;margin:0 0 10px;}
  p{color:#9aa8b8;line-height:1.6;margin:0 0 18px;}
  a{color:#60a5fa;text-decoration:none;font-weight:600;}
</style>
<script>location.replace('https://open.ai24x.com');</script>
</head>
<body>
<div class="box">
  <h1>AI24X Developer Portal</h1>
  <p>API keys, models, docs and developer tools now live at open.ai24x.com. Redirecting you there\u2026</p>
  <p><a href="https://open.ai24x.com">Continue to open.ai24x.com</a></p>
</div>
</body>
</html>
`;
const targets = [
  'web/api.html',
  'web/docs.html',
  'web/models/index.html',
  'web/guides/index.html',
];
for (const t of targets) {
  const p = path.join(ROOT, t);
  if (!fs.existsSync(p)) { console.log('MISS ' + t); continue; }
  fs.writeFileSync(p, stub, 'utf8');
  console.log('OK ' + t);
}
