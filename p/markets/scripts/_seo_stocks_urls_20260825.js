// SEO /stocks/{symbol} 干净 URL 上线：canonical/og:url/相关链接/sitemap 切到 /stocks/（2026-08-25）
// 用法：node _seo_stocks_urls_20260825.js
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SEO_DIR = path.join(ROOT, "web", "seo");
const SITEMAP = path.join(ROOT, "web", "sitemap.xml");
const APP = "https://markets.ai24x.com";

const STOCKS = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "META", "GOOGL", "AMD", "PLTR", "NFLX"];
const LOW = STOCKS.map((s) => s.toLowerCase());

function read(p) {
  return fs.readFileSync(p, "utf8");
}
function write(p, s) {
  fs.writeFileSync(p, s, "utf8");
}

let changed = 0;
for (const sym of STOCKS) {
  const slug = sym.toLowerCase();
  const f = path.join(SEO_DIR, slug + ".html");
  if (!fs.existsSync(f)) {
    console.log("MISS", f);
    continue;
  }
  let html = read(f);
  const before = html;

  // canonical + og:url -> /stocks/{slug}
  html = html.replace(
    new RegExp(`<link rel="canonical" href="${APP}/seo/${slug}\\.html">`, "g"),
    `<link rel="canonical" href="${APP}/stocks/${slug}">`
  );
  html = html.replace(
    new RegExp(`<meta property="og:url" content="${APP}/seo/${slug}\\.html">`, "g"),
    `<meta property="og:url" content="${APP}/stocks/${slug}">`
  );

  // related-stock links -> absolute /stocks/{other}
  for (const other of STOCKS) {
    const oslug = other.toLowerCase();
    html = html.replace(
      new RegExp(`<a href="${oslug}\\.html">${other}</a>`, "g"),
      `<a href="/stocks/${oslug}">${other}</a>`
    );
  }
  // "All guides" -> /seo/index.html (page now served at /stocks/{slug})
  html = html.replace(/<a href="index\.html">All guides<\/a>/g, '<a href="/seo/index.html">All guides</a>');

  if (html !== before) {
    write(f, html);
    changed++;
    console.log("UPDATED", slug + ".html");
  } else {
    console.log("NOCHANGE", slug + ".html");
  }
}

// sitemap.xml: stock pages -> /stocks/{slug}
if (fs.existsSync(SITEMAP)) {
  let xml = read(SITEMAP);
  const beforeXml = xml;
  for (const sym of STOCKS) {
    const slug = sym.toLowerCase();
    xml = xml.replace(
      new RegExp(`<loc>${APP}/seo/${slug}\\.html</loc>`, "g"),
      `<loc>${APP}/stocks/${slug}</loc>`
    );
  }
  if (xml !== beforeXml) {
    write(SITEMAP, xml);
    console.log("UPDATED sitemap.xml");
  } else {
    console.log("NOCHANGE sitemap.xml");
  }
}

console.log("DONE changed=" + changed);
