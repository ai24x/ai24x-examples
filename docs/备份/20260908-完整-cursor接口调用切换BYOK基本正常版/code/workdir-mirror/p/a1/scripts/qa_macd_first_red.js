const path = require("path");
const pw = require("C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core");

const BASE = "http://127.0.0.1:18001";
const payload = {
  ok: true,
  date: "2026-08-16",
  asof: "2026-08-14",
  market: "all",
  picks: [
    {
      code: "920999", name: "测试首红", price: 12.34, pct: 5.2, final: 72,
      tier: "key", mainHit: true, mainName: "PCB", patterns: { macdFirstRed: 1, smallYang: 1 },
      macdFirstRedDays: 0, surgeDaysAgo: 4, pullback2Days: null,
      pos: 0.25, chg5: 8.1, chg20: 12.3, mcap: 15.2, risks: [],
      levels: { s1: 11.9, s2: 11.6, p1: 12.9, p2: 13.5, stop: 11.5 }, fund: {}, tail: {}
    }
  ],
  runners: [
    {
      code: "920998", name: "测试备选", price: 8.88, pct: 3.1, final: 61,
      patterns: { macdFirstRed: 1, surgeStart: 1 }, macdFirstRedDays: 2,
      surgeDaysAgo: 5, pos: 0.3, chg5: 6.2, chg20: 9.1, mcap: 9.8,
      risks: ["排名靠后"], bearish_level: "pass"
    }
  ],
  macd_reds: [
    {
      code: "920997", name: "今日首红标的", price: 6.66, pct: 4.4, final: 74,
      macdFirstRedDays: 0, gcDays: 1, pos: 0.22, chg5: 7.5, chg20: 9.2,
      mcap: 12.5, amount: 0.8, turnover: 6.2,
      mainHit: true, mainName: "PCB",
      patterns: { macdFirstRed: 1, smallYang: 1 }, risks: [], bearish_level: "pass",
      levels: { s1: 6.3, s2: 6.1, p1: 7.0, p2: 7.4, stop: 6.0 }, fund: { earnPos: ["预增"] }
    },
    {
      code: "920996", name: "红柱第二天标的", price: 15.5, pct: 2.0, final: 68,
      macdFirstRedDays: 1, gcDays: 2, pos: 0.35, chg5: 4.8, chg20: 6.1,
      mcap: 21.0, amount: 1.1, turnover: 4.5,
      obsHit: true, obsName: "创新药",
      patterns: { macdFirstRed: 1, pullback2: 1 }, pullback2Days: 3, risks: [], bearish_level: "warn",
      levels: { s1: 15.0, s2: 14.6, p1: 16.2, p2: 16.9, stop: 14.4 }
    },
    {
      code: "920995", name: "红柱第三天标的", price: 9.9, pct: -0.5, final: 60,
      macdFirstRedDays: 2, gcDays: 3, pos: 0.42, chg5: 3.2, chg20: 5.0,
      mcap: 8.8, amount: 0.4, turnover: 3.1,
      patterns: { macdFirstRed: 1 }, risks: ["换手偏低"], bearish_level: "pass",
      levels: { s1: 9.5, s2: 9.2, p1: 10.4, p2: 10.9, stop: 9.1 }
    }
  ],
  mainlines: [{ name: "PCB", src: "daily" }]
};
const macdPayload = {
  ok: true,
  date: "2026-08-16",
  asof: "2026-08-14",
  market_code: "macd",
  total: 800, scanned: 60, fine: 12,
  market: { pts: 3.0 }, regime: "stable",
  mainlines: [{ name: "PCB", src: "daily" }],
  macd_reds: payload.macd_reds
};

(async () => {
  const browser = await pw.chromium.launch({
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe"
  });
  const context = await browser.newContext({ serviceWorkers: "block" });
  const page = await context.newPage();
  const errors = [];
  const reqs = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message));
  page.on("request", (r) => { if (r.url().includes("/api/")) reqs.push(r.url().split("?")[0]); });
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 400) {
      errors.push("HTTP " + r.status() + " " + r.url().split("?")[0]);
    }
  });
  await page.route("**/api/**", async (route) => {
    const u = route.request().url();
    console.log("ROUTE HIT:", u.split("?")[0]);
    if (u.includes("/api/bj/screener?") || u.includes("/api/bj/screener/run") || u.endsWith("/api/bj/screener")) {
      const isMacd = u.indexOf("market=macd") >= 0;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(isMacd ? macdPayload : payload) });
    }
    const mocks = {
      "/api/me": { user: { role: "vip", name: "QA" } },
      "/api/report/today": { ok: true, public_md: "", data: {} },
      "/api/bj/screener/progress": { ok: true, phase: "done", progress: 100, msg: "" },
      "/api/ths/sentiment": { ok: true, data: {} },
      "/api/bj/winrate": { ok: true, n: 0, asof: "", items: [] },
      "/api/bj/history": { ok: true, items: [] }
    };
    let body = null;
    for (const [k, v] of Object.entries(mocks)) {
      if (u.includes(k)) { body = v; break; }
    }
    return route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify(body || { ok: true })
    });
  });
  await page.addInitScript(() => {
    try { localStorage.setItem("ai24x_a_token", "qa-test-token"); } catch (e) {}
  });
  await page.goto(BASE + "/gd.html", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(2500);
  const body = await page.content();
  const txt = await page.evaluate(() => document.body ? document.body.innerText.slice(0, 600) : "");
  console.log("REQS:", reqs.join(" | "));
  console.log("BODY TEXT:", txt.replace(/\n+/g, " / ").slice(0, 500));
  const hasNote = body.includes("MACD首根红柱") || body.includes("进阶策略");
  const hasTag = body.includes("今日首红") && body.includes("MACD首红");
  const hasSection = body.includes("MACD 量能首红") && body.includes("红柱第2天") && body.includes("红柱第3天");
  const hasTop = body.includes("⭐优先");
  const hasTab = await page.evaluate(() => !!document.querySelector('#bj-tabs .bj-tab[data-market="macd"]'));
  console.log("note bar rendered:", hasNote);
  console.log("section rendered:", hasSection);
  console.log("top-3 stars rendered:", hasTop);
  console.log("tags rendered:", hasTag);
  console.log("macd tab exists:", hasTab);

  // 点击 MACD首红 tab -> 应渲染独立栏目（不含主推区）
  await page.evaluate(() => {
    const t = document.querySelector('#bj-tabs .bj-tab[data-market="macd"]');
    if (t) t.click();
  });
  await page.waitForTimeout(1500);
  const body2 = await page.content();
  const macdMain = body2.includes("MACD 量能首红") && body2.includes("⭐优先") && !body2.includes("今日 AI 筛选");
  console.log("macd tab main content rendered:", macdMain);
  console.log("console errors:", errors.length ? errors : "none");
  await browser.close();
  process.exit(hasNote && hasTag && hasSection && hasTop && hasTab && macdMain && !errors.length ? 0 : 1);
})().catch((e) => { console.error("QA FAIL", e); process.exit(1); });
