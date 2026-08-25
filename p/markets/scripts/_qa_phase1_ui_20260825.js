const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const CORE = 'http://127.0.0.1:8000';
const MK = 'http://127.0.0.1:18012';
const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + (detail ? ' | ' + detail : ''));
}
async function api(path, opts) {
  const r = await fetch(CORE + path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  return r.json();
}
async function closeOnboard(page) {
  try { if (await page.isVisible('#onboard')) await page.click('#onboard-skip'); } catch (e) {}
}

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });

  // login pro (existing) + register fresh free
  const pro = await api('/v1/auth/login', { method: 'POST', body: JSON.stringify({ email: 'e2e.dodo@test.local', password: 'DodoE2e#2026' }) });
  if (pro.token) log('pro login', true);
  else { log('pro login', false, JSON.stringify(pro).slice(0, 200)); process.exit(1); }
  const suffix = Date.now();
  const freeEmail = 'qa.ui.' + suffix + '@ai24x.local';
  const send = await api('/v1/auth/email/send', { method: 'POST', body: JSON.stringify({ email: freeEmail }) });
  const code = send.local_code || (send.data && send.data.local_code) || '';
  const reg = await api('/v1/auth/register', { method: 'POST', body: JSON.stringify({ email: freeEmail, password: 'QaUi#2026', email_code: code }) });
  if (reg.token) log('free register', true);
  else { log('free register', false, JSON.stringify(reg).slice(0, 300)); process.exit(1); }

  // ---------- 1) app.html desktop logged out ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(MK + '/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1200);
    log('app: alert bell exists', !!(await page.$('#btn-alerts')));
    log('app: alert panel exists', !!(await page.$('#alerts-panel')));
    log('app: alert kind select options=6', (await page.$$('#alert-kind option')).length === 6);
    log('app: alert add button exists', !!(await page.$('#btn-alert-add')));
    log('app: footer daily link', /daily/i.test(await page.textContent('footer')));
    log('app: no JS errors (guest)', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---------- 2) app.html desktop logged-in free ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await ctx.addCookies([{ name: 'ai24x_auth_token', value: reg.token, url: MK + '/' }]);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(MK + '/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(2500);
    const trialVisible = await page.isVisible('#trial-box');
    log('app: trial box visible for free user', trialVisible);
    const quota = (await page.textContent('#alert-quota')) || '';
    log('app: alert quota free text', /Free plan/.test(quota), quota.trim());
    log('app: no JS errors (free)', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---------- 3) screener.html (pro) shows factors ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await ctx.addCookies([{ name: 'ai24x_auth_token', value: pro.token, url: MK + '/' }]);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(MK + '/screener.html', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.sr-card', { timeout: 180000 });
    await page.waitForTimeout(500);
    const firstCard = await page.textContent('.sr-card');
    log('screener: card shows Mcap', /Mcap/.test(firstCard));
    log('screener: card shows PE', /PE/.test(firstCard));
    log('screener: card shows RSI', /RSI/.test(firstCard));
    log('screener: card shows 52w', /52w/.test(firstCard));
    log('screener: no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---------- 4) daily page ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(MK + '/daily/', { waitUntil: 'networkidle' });
    await page.waitForSelector('.dl-body table', { timeout: 15000 });
    const rows = await page.$$('.dl-body table tr');
    log('daily: brief table renders', rows.length >= 4, 'rows=' + rows.length);
    const dates = await page.$$('.dl-date');
    log('daily: date chips render', dates.length >= 1, 'chips=' + dates.length);
    log('daily: no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  // ---------- 5) mobile 375 app.html ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(MK + '/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1000);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    log('mobile app: no horizontal overflow', !overflow, 'scrollW=' + (await page.evaluate(() => document.documentElement.scrollWidth)));
    log('mobile app: no JS errors', errors.length === 0, errors.slice(0, 2).join('; '));
    await ctx.close();
  }

  const fails = results.filter((r) => !r.ok).length;
  console.log('=== TOTAL=' + results.length + ' PASS=' + (results.length - fails) + ' FAIL=' + fails + ' ===');
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error('QA FATAL', e); process.exit(2); });

