const pw = require("C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core");

(async () => {
  const browser = await pw.chromium.launch({
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe"
  });
  const context = await browser.newContext({ serviceWorkers: "block" });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message));
  await page.addInitScript(() => {
    try { localStorage.setItem("ai24x_a_token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJ0ZXN0MDVAcXEuY29tIiwicGhvbmUiOiIxODk2ODcwMTkxMyIsImlhdCI6MTc4Njg5NTg0OCwiZXhwIjoxNzg3NTAwNjQ4fQ.wUGFYbFI5f-eYn_yQvVJ6lAGi9NyPRJQNQEtgMdIbp4"); } catch (e) {}
  });
  await page.goto("http://127.0.0.1:18001/gd.html", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const txt = await page.evaluate(() => {
    const box = document.getElementById("bj-market");
    return box ? box.innerText : "";
  });
  console.log("MARKET BOX:", txt.replace(/\n+/g, " / ").slice(0, 400));
  const bad = txt.includes("backup_20260813_obscap") || /backup_\d+/.test(txt);
  const ok = txt.includes("最近大盘") && !bad;
  console.log("backup leaked:", bad);
  console.log("recent report label ok:", ok);
  console.log("console errors:", errors.length ? errors : "none");
  await browser.close();
  process.exit(ok && !bad && !errors.length ? 0 : 1);
})().catch((e) => { console.error("QA FAIL", e); process.exit(1); });
