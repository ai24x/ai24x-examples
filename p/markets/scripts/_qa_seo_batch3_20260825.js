// QA: batch-3 SEO stock pages (2026-08-25) — full 30-stock regression.
// Asserts canonical/og:url = /stocks/{slug}, absolute /seo/assets img,
// all related links absolute /stocks/*, disclaimer present, no relative stock links,
// index + sitemap cover every symbol.
const fs = require("fs");
const path = require("path");

const SEO = path.resolve(__dirname, "..", "web", "seo");
const APP = "https://markets.ai24x.com";
const stocks = [
  "nvda", "aapl", "tsla", "msft", "amzn", "meta", "googl", "amd", "pltr", "nflx",
  "avgo", "cost", "crm", "orcl", "uber", "abnb", "pypl", "shop", "snow", "coin",
  "jpm", "v", "lly", "jnj", "pfe", "xom", "ba", "cat", "nke", "dis",
];

let pass = 0;
const fails = [];

for (const slug of stocks) {
  const fp = path.join(SEO, `${slug}.html`);
  if (!fs.existsSync(fp)) { fails.push(`${slug}: missing file`); continue; }
  const html = fs.readFileSync(fp, "utf8");
  const canon = `rel="canonical" href="${APP}/stocks/${slug}"`;
  const og = `property="og:url" content="${APP}/stocks/${slug}"`;
  const img = `src="${APP}/seo/assets/${slug}.svg"`;
  const dis = "not investment advice";
  const relBad = new RegExp(`href="${slug}\\.html"`);
  const allGuides = `href="/seo/index.html"`;
  const checks = [
    [canon, "canonical"],
    [og, "og:url"],
    [img, "absolute img"],
    [dis, "disclaimer"],
    [allGuides, "all-guides link"],
  ];
  let ok = true;
  for (const [needle, label] of checks) {
    if (!html.includes(needle)) { fails.push(`${slug}: MISSING ${label}`); ok = false; }
  }
  if (relBad.test(html)) { fails.push(`${slug}: relative self link found`); ok = false; }
  const others = stocks.filter((s) => s !== slug);
  const missingOthers = others.filter((s) => !html.includes(`href="/stocks/${s}"`));
  if (missingOthers.length) { fails.push(`${slug}: missing related links ${missingOthers.join(",")}`); ok = false; }
  if (ok) pass++;
}

{
  const fp = path.join(SEO, "index.html");
  const html = fs.readFileSync(fp, "utf8");
  const missing = stocks.filter((s) => !html.includes(`href="/stocks/${s}"`));
  if (missing.length) fails.push(`index: missing stock links ${missing.join(",")}`);
  else pass++;
}

{
  const fp = path.resolve(__dirname, "..", "web", "sitemap.xml");
  const xml = fs.readFileSync(fp, "utf8");
  const missing = stocks.filter((s) => !xml.includes(`/stocks/${s}</loc>`));
  if (missing.length) fails.push(`sitemap: missing ${missing.join(",")}`);
  else pass++;
}

console.log(`PASS=${pass} FAIL=${fails.length}`);
if (fails.length) {
  console.log(fails.join("\n"));
  process.exit(1);
}
