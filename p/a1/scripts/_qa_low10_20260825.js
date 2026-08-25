const pw = require("C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core");

const BASE = "http://127.0.0.1:18001/gd.html";

(async () => {
  // 登录拿 token
  const loginRes = await fetch("http://127.0.0.1:18011/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: "18968701913", password: "iamlei" }),
  });
  const login = await loginRes.json();
  const TOKEN = login.token;
  if (!TOKEN) { console.log("LOGIN FAIL", JSON.stringify(login)); process.exit(1); }

  const browser = await pw.chromium.launch({
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  });
  const context = await browser.newContext({ serviceWorkers: "block" });
  await context.addInitScript((tok) => {
    try { localStorage.setItem("ai24x_a_token", tok); } catch (e) {}
  }, TOKEN);
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message));
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 500) errors.push("HTTP " + r.status() + " " + r.url().split("?")[0]);
  });

  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  try {
    await page.waitForFunction(() => {
      const el = document.getElementById("bj-main");
      return el && !el.hidden && el.offsetParent !== null;
    }, { timeout: 60000 });
  } catch (e) { console.log("TIMEOUT waiting bj-main"); }

  // 找 low10 tab
  const tabs = await page.$$eval("#bj-tabs .bj-tab", els => els.map(e => ({
    market: e.getAttribute("data-market"),
    text: (e.textContent || "").trim(),
  })));
  console.log("TABS:", JSON.stringify(tabs));

  const lowTab = await page.$('#bj-tabs .bj-tab[data-market="low10"]');
  if (!lowTab) { console.log("LOW10 TAB NOT FOUND"); await browser.close(); process.exit(1); }
  await lowTab.click();
  await page.waitForTimeout(6000);

  // 日期标签 / 状态条 / 重扫按钮
  const dateLabels = await page.$$eval("[class*=date], [class*=asof], .chip-sub, .bj-meta, .winrate-strip, [id*=status], .bj-status", els =>
    els.filter(e => e.offsetParent !== null).map(e => (e.textContent || "").trim()).filter(t => t).slice(0, 15)
  );
  console.log("DATELABELS:", JSON.stringify(dateLabels));

  // 默认 hs tab：主线区渲染
  const hsTab = await page.$('#bj-tabs .bj-tab[data-market="hs"]');
  if (hsTab) { await hsTab.click(); await page.waitForTimeout(5000); }
  const mlBox = await page.$("#bj-mainlines");
  if (mlBox) {
    console.log("MAINLINES_HTML:", (await mlBox.textContent()).trim().slice(0, 300));
  }
  const brBox = await page.$("#bj-boardrank");
  if (brBox) {
    const brText = (await brBox.textContent()).trim().slice(0, 400);
    console.log("BOARDRANK_TEXT:", brText);
  }

  const buttons = await page.$$eval("button, .btn", els =>
    els.filter(e => e.offsetParent !== null).map(e => (e.textContent || "").trim()).filter(t => t).slice(0, 12)
  );
  console.log("BUTTONS:", JSON.stringify(buttons));

  // 读取结果区
  const cards = await page.$$eval(".pick-card, .bj-pick, [class*=pick]", els =>
    els.filter(e => e.offsetParent !== null).map(e => ({
      cls: e.className,
      text: (e.textContent || "").slice(0, 120),
    })).slice(0, 12)
  );
  console.log("CARDS:", JSON.stringify(cards, null, 1));

  const canvases = await page.$$eval("canvas", els => els.filter(e => e.offsetParent !== null).length);
  console.log("VISIBLE_CANVAS:", canvases);
  console.log("JS_ERRORS:", JSON.stringify(errors));

  await browser.close();
})().catch(e => { console.error("QA FAIL", e); process.exit(1); });
