const pw = require("C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core");

const TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJ0ZXN0MDVAcXEuY29tIiwicGhvbmUiOiIxODk2ODcwMTkxMyIsImlhdCI6MTc4Njk4MTA5OSwiZXhwIjoxNzg3NTg1ODk5fQ.OvljzV3T4DkM5QQlS351covYAGtWTCaLmXIw-vIX9Hw";
const BASE = "http://127.0.0.1:18001/gd.html";

(async () => {
  const browser = await pw.chromium.launch({
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe"
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
  // 等待 bj-main 可见（真实后端 + 当日缓存，一般 2-5s；上限 60s）
  let visible = false;
  try {
    await page.waitForFunction(() => {
      const el = document.getElementById("bj-main");
      return el && !el.hidden && el.offsetParent !== null;
    }, { timeout: 60000 });
    visible = true;
  } catch (e) { /* timeout */ }
  await page.waitForTimeout(2500);

  const flowSteps = await page.$$eval(".bj-flow-step", els => els.map(e => e.textContent.trim()));
  const disclaimers = await page.$$eval("p.sub, .notice, .ths-foot, .winrate-note", els =>
    els.map(e => e.textContent).filter(t => t && (t.includes("不构成") || t.includes("投资建议") || t.includes("仅供研究"))));
  const mainlinesBox = await page.$eval("#bj-mainlines", el => el.innerHTML.length);
  const boardrankBox = await page.$eval("#bj-boardrank", el => el.innerHTML.length);
  const resultBox = await page.$eval("#bj-result", el => el.innerHTML.length);
  const marketBox = await page.$eval("#bj-market", el => el.innerHTML.length);
  const moreDetails = await page.$eval("#bj-more", el => el.tagName + "|" + el.className);
  const tabText = await page.$$eval(".bj-tab", els => els.map(e => e.textContent.trim()));
  const stratHidden = await page.$eval("#bj-strategy", el => el.hidden);
  const stratText = await page.$eval("#bj-strategy", el => el.textContent || "");
  const marketHasStrategy = await page.$eval("#bj-market", el => (el.textContent || "").includes("观察：") || (el.textContent || "").includes("回避："));
  const orderOk = await page.evaluate(() => {
    var m = document.getElementById("bj-mainlines"), s = document.getElementById("bj-strategy"), b = document.getElementById("bj-boardrank");
    if (!m || !s || !b) return false;
    return m.compareDocumentPosition(s) & Node.DOCUMENT_POSITION_FOLLOWING && s.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
  });

  console.log(JSON.stringify({
    visible, flowSteps, disclaimers, mainlinesBox, boardrankBox, resultBox, marketBox, moreDetails, tabText,
    stratHidden, stratText: stratText.slice(0, 120), marketHasStrategy, orderOk, errors
  }, null, 2));
  await browser.close();
})();
