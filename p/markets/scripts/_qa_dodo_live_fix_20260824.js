// QA：Dodo live 切换后的三项修复（本地 8000 / 18080）
//  1) www console#billing 支付弹窗含 Alipay+Dodo；Starter 促销限购已放开（promo_max 为空）
//  2) open console#billing 支付弹窗含 支付宝/Alipay + Dodo（此前支付宝按钮丢失）
//  3) open /v1/billing/plans 返回 byok 2 档 + token 6 档
const { chromium } = require('C:\\Users\\Admin\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core');

const WWW = 'http://127.0.0.1:8000';
const OPEN = 'http://127.0.0.1:18080';
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail || '' });
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' :: ' + detail : ''));
}

async function apiLogin(base, email, password) {
  const r = await fetch(base + '/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return r.json();
}

async function main() {
  // ---------- open: API plans ----------
  const openLogin = await apiLogin(OPEN, 'byok.demo@ai24x.local', 'ByokDemo#2026');
  check('open login api', !!openLogin.token, openLogin.error || '');
  const plansResp = await fetch(OPEN + '/v1/billing/plans', { headers: { Authorization: 'Bearer ' + openLogin.token } });
  const plans = await plansResp.json();
  const pay = (plans && plans.pay) || {};
  check('open pay.alipay_ready', !!pay.alipay_ready, JSON.stringify({ alipay_ready: pay.alipay_ready, dodo_ready: pay.dodo_ready }));
  check('open pay.dodo_ready', !!pay.dodo_ready, '');
  check('open byok plans >= 2', Array.isArray(plans.byok_plans) && plans.byok_plans.length >= 2, 'count=' + (plans.byok_plans || []).length);
  check('open token plans >= 6', Array.isArray(plans.plans) && plans.plans.length >= 6, 'count=' + (plans.plans || []).length);

  // ---------- open: console 弹窗 ----------
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
  }, { token: openLogin.token, user: openLogin.user });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(OPEN + '/console.html?x=qa' + Date.now() + '#billing', { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(2500);

  const payState = await page.evaluate(() => ({
    pay: window.__tokenPay || null,
    buyBtns: Array.from(document.querySelectorAll('[data-buy-plan]')).map((b) => b.getAttribute('data-buy-plan')),
  }));
  check('open ui pay flags', !!(payState.pay && payState.pay.alipay_ready && payState.pay.dodo_ready),
    JSON.stringify(payState.pay && { alipay_ready: payState.pay.alipay_ready, dodo_ready: payState.pay.dodo_ready }));

  // 点击任一套餐的「选择」→ 弹窗应同时出现 支付宝/Alipay 与 Dodo
  await page.evaluate(() => {
    const btn = document.querySelector('[data-buy-plan]');
    if (btn) btn.click();
  });
  await page.waitForTimeout(800);
  const modalState = await page.evaluate(() => {
    const ch = document.getElementById('modal-pay-channels');
    if (!ch) return { modal: false, text: '' };
    const txt = ch.innerText || '';
    return {
      modal: true,
      hasAlipay: /支付宝|Alipay/.test(txt),
      hasDodo: /Dodo/.test(txt),
      text: txt.replace(/\s+/g, ' ').slice(0, 200),
    };
  });
  check('open modal rendered', modalState.modal, '');
  check('open modal has Alipay', modalState.hasAlipay, modalState.text);
  check('open modal has Dodo', modalState.hasDodo, modalState.text);
  check('open page no js errors', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();

  // ---------- www: console + Starter 促销 ----------
  const wwwLogin = await apiLogin(WWW, 'lei@itxin.com', 'iamlei');
  check('www login api', !!wwwLogin.token, wwwLogin.error || '');
  const wwwPlansResp = await fetch(WWW + '/v1/billing/plans', { headers: { Authorization: 'Bearer ' + wwwLogin.token } });
  const wwwPlans = await wwwPlansResp.json();
  const starter = ((wwwPlans.plans || []).find((p) => p.plan === 'token_pack_10k')) || {};
  check('www starter promo_max open', starter.promo_max_purchases === null || starter.promo_max_purchases === undefined || starter.promo_max_purchases === 0,
    'promo_max=' + starter.promo_max_purchases);
  check('www pay flags', !!(wwwPlans.pay && wwwPlans.pay.alipay_ready && wwwPlans.pay.dodo_ready),
    JSON.stringify(wwwPlans.pay && { alipay_ready: wwwPlans.pay.alipay_ready, dodo_ready: wwwPlans.pay.dodo_ready }));

  const fails = results.filter((r) => !r.ok);
  console.log('\nSUMMARY: ' + (results.length - fails.length) + '/' + results.length + ' PASS');
  process.exit(fails.length ? 1 : 0);
}

main().catch((e) => { console.error('QA_FATAL', e); process.exit(2); });
