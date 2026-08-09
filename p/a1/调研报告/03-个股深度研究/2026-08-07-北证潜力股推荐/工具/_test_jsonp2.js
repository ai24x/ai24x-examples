'use strict';
const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--disable-gpu'] });
  const page = await (await browser.newContext()).newPage();
  await page.setContent('<html><body>t</body></html>');
  const out = await page.evaluate(() => new Promise((resolve) => {
    const host = 'https://push2delay.eastmoney.com';
    const u = host + '/api/qt/clist/get?pn=1&pz=8&po=1&np=1&fltt=2&invt=2&fid=f6&fs=m:0+t:81+s:2048&fields=f12,f14,f2,f3,f5,f6,f8,f9,f10,f20,f21,f23&cb=__bjtest';
    window.__bjtest = (d) => {
      try {
        const rows = (d && d.data && d.data.diff || []);
        resolve({ ok: true, total: d.data.total, first: rows.slice(0, 3).map(r => ({ code: r.f12, name: r.f14, price: r.f2, pct: r.f3, amount: r.f6, mcap: r.f20 })) });
      } catch (e) { resolve({ ok: false, err: String(e) }); }
    };
    const s = document.createElement('script');
    s.src = u;
    s.onerror = () => resolve({ ok: false, err: 'script load error' });
    document.head.appendChild(s);
    setTimeout(() => resolve({ ok: false, err: 'timeout' }), 15000);
  }));
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });