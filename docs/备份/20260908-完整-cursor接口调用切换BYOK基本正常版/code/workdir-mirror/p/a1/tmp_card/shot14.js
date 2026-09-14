const { chromium } = require('C:/Users/Admin/node_modules/playwright-core');
(async () => {
  const login = await fetch('http://127.0.0.1:18011/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: 'test05@qq.com', password: 'Test12345678' }) });
  const { token } = await login.json();
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:18001/daily/index.html?i=CL2KDLGR', { waitUntil: 'domcontentloaded' });
  await page.evaluate(t => { localStorage.setItem('ai24x_a_token', t); }, token);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#report h2', { timeout: 60000 });
  await page.waitForTimeout(1500);
  const out = await page.evaluate(() => {
    const card = document.querySelector('.page-main .card');
    const kids = [];
    card.childNodes.forEach((n, idx) => {
      if (n.nodeType === 1) {
        const b = n.getBoundingClientRect();
        const cs = getComputedStyle(n);
        kids.push({ idx, tag: n.tagName, id: n.id, cls: String(n.className).slice(0, 30), y: Math.round(b.top), h: Math.round(b.height), disp: cs.display, margin: cs.marginTop + '/' + cs.marginBottom });
      } else if (n.nodeType === 3 && n.textContent.trim()) {
        kids.push({ idx, text: n.textContent.trim().slice(0, 30) });
      }
    });
    const cardB = card.getBoundingClientRect();
    const cardCs = getComputedStyle(card);
    return { cardY: Math.round(cardB.top), cardH: Math.round(cardB.height), cardPad: cardCs.padding, kids };
  });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
