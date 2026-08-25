const pw = require("C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core");

(async () => {
  const loginRes = await fetch("http://127.0.0.1:18011/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: "18968701913", password: "iamlei" }),
  });
  const login = await loginRes.json();
  const TOKEN = login.token;
  if (!TOKEN) { console.log("LOGIN FAIL"); process.exit(1); }

  const browser = await pw.chromium.launch({
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  });
  const context = await browser.newContext({
    serviceWorkers: "block",
    viewport: { width: 375, height: 812 },
  });
  await context.addInitScript((tok) => {
    try { localStorage.setItem("ai24x_a_token", tok); } catch (e) {}
  }, TOKEN);
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message));

  await page.goto("http://127.0.0.1:18001/m/gd.html", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(9000);

  const bodyText = (await page.evaluate(() => document.body.innerText || "")).slice(0, 600);
  console.log("BODY:", bodyText.replace(/\n+/g, " | "));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
  console.log("H_OVERFLOW:", overflow);
  console.log("JS_ERRORS:", JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error("QA FAIL", e); process.exit(1); });
