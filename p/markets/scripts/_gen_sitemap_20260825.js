// Regenerate markets sitemap.xml deterministically (batch-2 /stocks/ URLs).
// Usage: node _gen_sitemap_20260825.js  (writes p/markets/web/sitemap.xml)
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SITEMAP = path.join(ROOT, "web", "sitemap.xml");
const BASE = "https://markets.ai24x.com";
const LASTMOD = "2026-08-25";

const main = [
  { loc: "/", freq: "daily", prio: "1.0" },
  { loc: "/app.html", freq: "daily", prio: "0.9" },
  { loc: "/pricing.html", freq: "weekly", prio: "0.8" },
  { loc: "/daily/", freq: "daily", prio: "0.8" },
  { loc: "/screener.html", freq: "daily", prio: "0.7" },
  { loc: "/seo/index.html", freq: "weekly", prio: "0.6" },
];

const stocks = [
  "aapl", "amd", "amzn", "googl", "meta", "msft", "nflx", "nvda", "pltr", "tsla",
  "abnb", "avgo", "coin", "cost", "crm", "orcl", "pypl", "shop", "snow", "uber",
  "ba", "cat", "dis", "jnj", "jpm", "lly", "nke", "pfe", "v", "xom",
];

const pairs = [
  "dia-vs-spy", "iwm-vs-spy", "macd-indicator-guide", "moving-averages-guide",
  "qqq-vs-spy", "qqq-vs-voo", "rsi-indicator-guide", "support-resistance-guide",
  "volume-price-guide", "voo-vs-spy",
];

const urls = [...main];
for (const s of stocks) urls.push({ loc: `/stocks/${s}`, freq: "weekly", prio: "0.6" });
for (const p of pairs) urls.push({ loc: `/seo/${p}.html`, freq: "weekly", prio: "0.6" });

urls.sort((a, b) => (a.loc < b.loc ? -1 : a.loc > b.loc ? 1 : 0));

const lines = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
];
for (const u of urls) {
  lines.push("  <url>");
  lines.push(`    <loc>${BASE}${u.loc}</loc>`);
  lines.push(`    <lastmod>${LASTMOD}</lastmod>`);
  lines.push(`    <changefreq>${u.freq}</changefreq>`);
  lines.push(`    <priority>${u.prio}</priority>`);
  lines.push("  </url>");
}
lines.push("</urlset>", "");

fs.writeFileSync(SITEMAP, lines.join("\n"), "utf8");
console.log(`sitemap written: ${urls.length} urls -> ${SITEMAP}`);
