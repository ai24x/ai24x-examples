// QA：本地 www console#billing Overview/Plans 支付弹窗 Dodo 按钮 + Dodo 下单（8000）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const BASE = 'http://127.0.0.1:8000';
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail || '' });
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' :: ' + detail : ''));
}

async function main() {
  const loginResp = await fetch(BASE + '/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'e2e.dodo@test.local', password: 'DodoE2e#2026' }),
  }).catch((e) => ({ status: 0, error: String(e) }));
  let login = loginResp.status === 200 ? await loginResp.json() : null;
  if (!login || !login.token) {
    console.log('login failed: ' + JSON.stringify({ status: loginResp.status, body: loginResp.error || '' }));
    process.exit(1);
  }
  if (!login || !login.token) { process.exit(1); }

  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.addInitScript(({ token, user }) => {
    if (location.origin === 'http://127.0.0.1:8000') {
      localStorage.setItem('ai24x_auth_token', token);
      localStorage.setItem('ai24x_auth_user', JSON.stringify(user));
    }
    window.__openUrls = [];
    const origOpen = window.open;
    window.open = function (url) { window.__openUrls.push(String(url || '')); return null; };
  }, { token: login.token, user: login.user });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto(BASE + '/console.html?x=qa' + Date.now() + '#billing', { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(2500);

  const state = await page.evaluate(() => {
    const txt = document.body ? document.body.innerText : '';
    const pay = window.__tokenPay || null;
    const tokenCard = document.querySelector('#productsList [data-product="token"]');
    const marketsCard = document.querySelector('#productsList [data-product="markets"]');
    const byokCard = document.querySelector('#productsList [data-product="byok"]');
    return {
      pay,
      hasDodoText: txt.indexOf('Dodo') >= 0,
      hint: (document.getElementById('payHint') || {}).textContent || '',
      tokenChooseBtns: tokenCard ? tokenCard.querySelectorAll('.product-plan-act button.btn-primary').length : 0,
      marketsChooseBtns: marketsCard ? marketsCard.querySelectorAll('.product-plan-act button.btn-primary').length : 0,
      byokLink: byokCard ? (byokCard.querySelector('.product-plan-act a') || {}).href || '' : '',
    };
  });
  check('www dodo_ready flag', !!(state.pay && state.pay.dodo_ready), JSON.stringify(state.pay && { dodo_ready: state.pay.dodo_ready, dodo_mode: state.pay.dodo_mode }));
  check('www Dodo text on page', state.hasDodoText, '');
  check('www token choose buttons', state.tokenChooseBtns > 0, 'n=' + state.tokenChooseBtns);
  check('www markets choose buttons', state.marketsChooseBtns > 0, 'n=' + state.marketsChooseBtns);
  check('www byok -> open link', state.byokLink.indexOf('open.ai24x.com') >= 0 || state.byokLink.indexOf('127.0.0.1:18080') >= 0, state.byokLink);

  // 点 token 卡片第一个「选择」→ 弹窗 → Dodo → 下单
  await page.click('#productsList [data-product="token"] .product-plan-act button.btn-primary');
  await page.waitForTimeout(500);
  const chooser = await page.evaluate(() => {
    const ch = document.getElementById('modal-pay-channels');
    const btns = ch ? Array.from(ch.querySelectorAll('button')).map((b) => (b.innerText || '').trim()) : [];
    return { btns, hasDodo: btns.some((t) => t.indexOf('Dodo') >= 0) };
  });
  check('www chooser has Dodo', chooser.hasDodo, JSON.stringify(chooser.btns));
  await page.evaluate(() => {
    const ch = document.getElementById('modal-pay-channels');
    const b = Array.from(ch.querySelectorAll('button')).find((x) => (x.innerText || '').indexOf('Dodo') >= 0);
    if (b) b.click();
  });
  await page.waitForFunction(() => (window.__openUrls || []).some((u) => u.indexOf('checkout.dodopayments.com') >= 0), { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(800);
  const opened = await page.evaluate(() => (window.__openUrls || []).filter((u) => u.indexOf('checkout.dodopayments.com') >= 0));
  check('www dodo checkout opened', opened.length > 0, JSON.stringify(opened));

  check('www no page errors', errors.length === 0, JSON.stringify(errors.slice(0, 3)));
  const failed = results.filter((r) => !r.ok);
  console.log('TOTAL ' + results.length + ' / FAIL ' + failed.length);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
