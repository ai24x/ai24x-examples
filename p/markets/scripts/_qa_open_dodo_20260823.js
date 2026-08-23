// QA：open 站 console#billing 支付弹窗 Dodo 按钮 + BYOK 卡片 + Dodo 下单（本地 18080）
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const BASE = 'http://127.0.0.1:18080';
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail || '' });
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' :: ' + detail : ''));
}

async function main() {
  // 1) API 登录拿 token
  const loginResp = await fetch(BASE + '/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'byok.demo@ai24x.local', password: 'ByokDemo#2026' }),
  });
  const login = await loginResp.json();
  check('login api', !!login.token, login.error || '');
  if (!login.token) { console.log(JSON.stringify(results, null, 1)); process.exit(1); }

  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.addInitScript(({ token, user }) => {
    if (location.origin === 'http://127.0.0.1:18080') {
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
  const apiLog = [];
  page.on('response', (r) => { if (r.url().indexOf('/v1/billing/') >= 0) apiLog.push(r.status() + ' ' + r.url()); });

  await page.goto(BASE + '/console.html?x=qa' + Date.now() + '#billing', { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(2000);

  // 2) BYOK 卡片渲染
  const byokState = await page.evaluate(() => {
    const txt = document.body ? document.body.innerText : '';
    const buyBtns = Array.from(document.querySelectorAll('#byokPlansList [data-buy-plan]')).map((b) => b.getAttribute('data-buy-plan'));
    return {
      noPlansEmpty: txt.indexOf('暂无 BYOK 套餐') >= 0 || txt.indexOf('No BYOK plans yet') >= 0,
      buyBtns,
      payHint: (document.getElementById('payHint') || {}).textContent || '',
      pay: window.__tokenPay || null,
    };
  });
  check('byok cards rendered', !byokState.noPlansEmpty && byokState.buyBtns.length >= 2, JSON.stringify(byokState.buyBtns));
  check('dodo_ready flag', !!(byokState.pay && byokState.pay.dodo_ready), JSON.stringify(byokState.pay && { dodo_ready: byokState.pay.dodo_ready, dodo_mode: byokState.pay.dodo_mode }));
  check('payHint mentions Dodo', byokState.payHint.indexOf('Dodo') >= 0, byokState.payHint.slice(0, 160));

  // 3) 点 BYOK 选购 → 支付弹窗含 Dodo
  await page.evaluate(() => {
    const tabs = document.querySelectorAll('.plans-tab');
    tabs.forEach((t) => { if (t.getAttribute('data-plan-tab') === 'byok') t.click(); });
  });
  await page.waitForTimeout(400);
  await page.click('#byokPlansList [data-buy-plan]');
  await page.waitForTimeout(600);
  const chooser = await page.evaluate(() => {
    const ch = document.getElementById('modal-pay-channels');
    const btns = ch ? Array.from(ch.querySelectorAll('button')).map((b) => (b.innerText || '').trim()) : [];
    return { modalOpen: !!ch, btns };
  });
  check('pay chooser modal open', chooser.modalOpen, '');
  check('chooser has Dodo', chooser.btns.some((t) => t.indexOf('Dodo') >= 0), JSON.stringify(chooser.btns));

  // 4) 点 Dodo → 下单 → checkout URL 打开
  await page.evaluate(() => {
    const ch = document.getElementById('modal-pay-channels');
    const btns = Array.from(ch.querySelectorAll('button'));
    const dodoBtn = btns.find((b) => (b.innerText || '').indexOf('Dodo') >= 0);
    if (dodoBtn) dodoBtn.click();
  });
  await page.waitForFunction(() => (window.__openUrls || []).some((u) => u.indexOf('checkout.dodopayments.com') >= 0), { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(800);
  const dodoResult = await page.evaluate(() => {
    const urls = window.__openUrls || [];
    const txt = document.body ? document.body.innerText : '';
    const hintEl = document.getElementById('modal-pay-result-hint');
    return {
      urls,
      hasDodoCheckout: urls.some((u) => u.indexOf('checkout.dodopayments.com') >= 0),
      payResultHint: (hintEl && hintEl.textContent) || '',
      hasOpenLink: !!document.getElementById('modal-pay-open-link') && document.getElementById('modal-pay-open-link').style.display !== 'none',
    };
  });
  check('dodo checkout url opened', dodoResult.hasDodoCheckout, JSON.stringify(dodoResult.urls));
  check('dodo result hint shown', dodoResult.payResultHint.indexOf('Dodo') >= 0, dodoResult.payResultHint.slice(0, 200));
  check('dodo open-link shown', dodoResult.hasOpenLink, '');

  // 关闭支付弹窗，进入 token 页签
  await page.evaluate(() => {
    const btn = document.querySelector('#modal-pay [data-close-modal="modal-pay"]');
    if (btn) btn.click();
    const m = document.getElementById('modal-pay');
    if (m) { m.setAttribute('aria-hidden', 'true'); m.classList.remove('is-open'); }
  });
  await page.waitForTimeout(300);

  // 5) token 页签 → token 套餐弹窗也有 Dodo
  await page.evaluate(() => {
    const tabs = document.querySelectorAll('.plans-tab');
    tabs.forEach((t) => { if (t.getAttribute('data-plan-tab') === 'token') t.click(); });
  });
  await page.waitForTimeout(400);
  const tokenState = await page.evaluate(() => {
    const group = document.getElementById('plansGroupToken');
    const buyBtns = group ? Array.from(group.querySelectorAll('[data-buy-plan]')) : [];
    return { tokenVisible: !!group && !group.hidden, buyBtns: buyBtns.length };
  });
  check('token tab visible', tokenState.tokenVisible, '');
  check('token table has choose buttons', tokenState.buyBtns > 0, 'n=' + tokenState.buyBtns);

  // 5a) 中文界面语言包：平台托管套餐价格统一美元（$），不再显示 ¥
  const zhCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await zhCtx.addInitScript(({ token, user }) => {
    if (location.origin === 'http://127.0.0.1:18080') {
      localStorage.setItem('ai24x_auth_token', token);
      localStorage.setItem('ai24x_auth_user', JSON.stringify(user));
      localStorage.setItem('ai24x_lang', 'zh');
    }
  }, { token: login.token, user: login.user });
  const zhPage = await zhCtx.newPage();
  zhPage.on('pageerror', (e) => errors.push(String(e)));
  await zhPage.goto(BASE + '/console.html?x=zh' + Date.now() + '#billing', { waitUntil: 'networkidle', timeout: 45000 });
  await zhPage.waitForTimeout(1500);
  await zhPage.evaluate(() => {
    const tabs = document.querySelectorAll('.plans-tab');
    tabs.forEach((t) => { if (t.getAttribute('data-plan-tab') === 'token') t.click(); });
  });
  await zhPage.waitForTimeout(500);
  const zhState = await zhPage.evaluate(() => {
    const group = document.getElementById('plansGroupToken');
    const rows = group ? Array.from(group.querySelectorAll('tr')) : [];
    const prices = [];
    rows.forEach((tr) => {
      const tds = Array.from(tr.querySelectorAll('td'));
      if (tds.length >= 2) prices.push((tds[1].textContent || '').trim());
    });
    return {
      prices: prices,
      isZh: !!(window.AI24X_API && AI24X_API.isZhUi && AI24X_API.isZhUi()),
    };
  });
  check('zh ui active', zhState.isZh, '');
  check(
    'zh token prices show USD not ¥',
    zhState.prices.length > 0 &&
      zhState.prices.every((t) => t.indexOf('$') === 0) &&
      zhState.prices.every((t) => t.indexOf('¥') < 0),
    JSON.stringify(zhState.prices)
  );
  await zhCtx.close();

  // 5b) 点 token 表格「选择」→ 弹窗有 Dodo → 下单并打开 checkout
  const beforeOpen = await page.evaluate(() => (window.__openUrls || []).length);
  await page.click('#plansGroupToken [data-buy-plan]');
  await page.waitForTimeout(500);
  const tokenChooser = await page.evaluate(() => {
    const ch = document.getElementById('modal-pay-channels');
    const btns = ch ? Array.from(ch.querySelectorAll('button')).map((b) => (b.innerText || '').trim()) : [];
    return { btns, hasDodo: btns.some((t) => t.indexOf('Dodo') >= 0) };
  });
  check('token chooser has Dodo', tokenChooser.hasDodo, JSON.stringify(tokenChooser.btns));
  await page.evaluate(() => {
    const ch = document.getElementById('modal-pay-channels');
    const b = Array.from(ch.querySelectorAll('button')).find((x) => (x.innerText || '').indexOf('Dodo') >= 0);
    if (b) b.click();
  });
  await page.waitForFunction((n) => (window.__openUrls || []).length > n && (window.__openUrls || []).some((u) => u.indexOf('checkout.dodopayments.com') >= 0), beforeOpen, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(800);
  const tokenDodo = await page.evaluate(() => (window.__openUrls || []).filter((u) => u.indexOf('checkout.dodopayments.com') >= 0).length);
  check('token Dodo checkout opened', tokenDodo > 0, 'dodoUrls=' + tokenDodo);

  // 6) token 套餐直接发 dodo order API（绕过 UI 点击，验证 product=token 链路）
  const ord = await page.evaluate(async () => {
    const r = await AI24X_API.billingDodoOrder('token_value_pack', 'token');
    return r;
  });
  check('token dodo order api', !!(ord && ord.pay_url && ord.pay_url.indexOf('checkout.dodopayments.com') >= 0), JSON.stringify(ord && { otn: ord.out_trade_no, url: ord.pay_url }));

  check('no page errors', errors.length === 0, JSON.stringify(errors.slice(0, 3)));
  console.log(JSON.stringify({ apiLog: apiLog.slice(0, 20) }, null, 1));
  const failed = results.filter((r) => !r.ok);
  console.log('TOTAL ' + results.length + ' / FAIL ' + failed.length);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
