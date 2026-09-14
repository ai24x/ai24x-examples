// 2026-08-18 板块排名与主线判定优化 前端验收（桌面 gd.html + 手机 m/gd.html，375px 视口）
const pw = require("C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core");
const fs = require("fs");

const TOKEN = fs.readFileSync("_tok_local.txt", "utf-8").trim();
const BASE = "http://127.0.0.1:18001";

async function newPage(context) {
  const page = await context.newPage();
  page._errors = [];
  page.on("console", (m) => { if (m.type() === "error") page._errors.push("CONSOLE: " + m.text()); });
  page.on("pageerror", (e) => page._errors.push("PAGEERROR: " + e.message));
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 500) page._errors.push("HTTP " + r.status() + " " + r.url().split("?")[0]);
  });
  return page;
}

async function waitMain(page, timeout) {
  try {
    await page.waitForFunction(() => {
      const el = document.getElementById("bj-main");
      return el && !el.hidden && el.offsetParent !== null;
    }, { timeout: timeout || 60000 });
    return true;
  } catch (e) { return false; }
}

(async () => {
  const browser = await pw.chromium.launch({
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe"
  });
  const results = {};

  // ---------- 桌面 gd.html ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
    await ctx.addInitScript((tok) => { try { localStorage.setItem("ai24x_a_token", tok); } catch (e) {} }, TOKEN);
    const page = await newPage(ctx);
    await page.goto(BASE + "/gd.html", { waitUntil: "domcontentloaded", timeout: 30000 });
    const ok = await waitMain(page, 60000);
    await page.waitForTimeout(2500);

    // hs 榜：煤炭 key 位 ml_why（新晋主线判定小字）
    const hsRank = await page.$$eval("#bj-boardrank .br-item", els => els.map(e => {
      const why = e.querySelector(".br-mlwhy");
      const badges = Array.from(e.querySelectorAll(".tier-badge")).map(b => b.textContent.trim());
      return { name: (e.querySelector(".n") || {}).textContent || "", badges: badges, why: why ? why.textContent : "" };
    }));
    const coal = hsRank.find(r => r.name.indexOf("煤炭") >= 0) || {};
    const coalOk = !!coal.why && coal.why.indexOf("新晋主线") >= 0 && coal.badges.indexOf("新晋") >= 0;

    // MACD 首红 tab：src 标注
    await page.click('.bj-tab[data-market="macd"]');
    await page.waitForTimeout(4000);
    const macdSrc = await page.$$eval(".mr-card .src-tag", els => els.map(e => e.textContent.trim()));
    const macdCnt = await page.$$eval(".mr-card", els => els.length);
    const macdOk = macdCnt >= 3 && macdSrc.some(s => s === "复盘样本") && macdSrc.some(s => s === "全市场扫描");

    // 回踩企稳 tab：scope 文案
    await page.click('.bj-tab[data-market="pb"]');
    await page.waitForTimeout(4000);
    const pbScope = await page.$eval("#bj-meta", el => el.textContent || "");
    const pbScopeOk = pbScope.indexOf("沪深京全市场·首板回踩企稳") >= 0;
    const pbCnt = await page.$$eval("#bj-result .pick, #bj-result .runner-card", els => els.length);

    results.desktop = { ok, coal: { name: coal.name, badges: coal.badges, why: coal.why }, coalOk,
      macd: { cnt: macdCnt, src: macdSrc, ok: macdOk },
      pb: { scopeOk: pbScopeOk, pbScope: pbScope.slice(0, 60), cnt: pbCnt },
      errors: page._errors };
    await ctx.close();
  }

  // ---------- 手机 m/gd.html（375px）----------
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, serviceWorkers: "block" });
    await ctx.addInitScript((tok) => { try { localStorage.setItem("ai24x_a_token", tok); } catch (e) {} }, TOKEN);
    const page = await newPage(ctx);
    await page.goto(BASE + "/m/gd.html", { waitUntil: "domcontentloaded", timeout: 30000 });
    try {
      await page.waitForFunction(() => {
        const el = document.getElementById("list");
        return el && el.innerHTML.length > 0;
      }, { timeout: 60000 });
    } catch (e) {}
    await page.waitForTimeout(2500);

    const mRank = await page.$$eval(".br-item", els => els.map(e => {
      const why = e.querySelector(".br-mlwhy");
      const badges = Array.from(e.querySelectorAll(".tier")).map(b => b.textContent.trim());
      return { name: (e.querySelector(".br-name") || {}).textContent || "", badges: badges, why: why ? why.textContent : "" };
    }));
    const mCoal = mRank.find(r => r.name.indexOf("煤炭") >= 0) || {};
    const mCoalOk = !!mCoal.why && mCoal.why.indexOf("新晋主线") >= 0 && mCoal.badges.indexOf("新晋") >= 0;

    // 375px 无横向溢出
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    const meta = await page.$eval("#meta", el => el.textContent || "");

    // pb tab（手机版）
    await page.click('#tab-pb');
    await page.waitForTimeout(4000);
    const mPbScope = await page.$eval("#meta", el => el.textContent || "");
    const mPbScopeOk = mPbScope.indexOf("沪深京全市场·首板回踩企稳") >= 0;

    results.mobile = { mCoalOk, mCoal: { name: mCoal.name, badges: mCoal.badges, why: mCoal.why },
      overflow, meta: meta.slice(0, 80), mPbScopeOk, mPbScope: mPbScope.slice(0, 80), errors: page._errors };
    await ctx.close();
  }

  console.log(JSON.stringify(results, null, 2));
  await browser.close();
})();
