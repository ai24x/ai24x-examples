const fs = require('fs');
const add = `- **console Plans 栏目补 BYOK（2026-08-23 追加）**：\`/v1/billing/products\`（public_products）新增 byok 产品（BYOK Gateway，2 档 $9.9/$99，url→open.ai24x.com/pricing.html）；console.js renderProducts 对 byok 走 markets 式展示（title_zh/price_label/perk），按钮=外链「Get BYOK Pro」跳 open.ai24x.com（target=_blank），不走站内支付弹窗（BYOK 履约在 open 独立库，core 收款无法激活，避免半成品下单）。locales 新增 page.console.byok.cta；locales.js/console.js 版本 20260823a→20260823b（locales 39 页 / console 1 页）。QA：\_qa_console_byok_20260823.js 9 项全 PASS（真实 /v1/billing/products + catch-all 放行 route.continue）；\_qa_console_vip_20260817.js 回归全 PASS；\_qa_dodo_sync / \_qa_pricing_byok 复跑全 PASS。\n`;
const target = 'D:\\Codex\\.codex\\AGENTS.md';
const cur = fs.readFileSync(target, 'utf8');
if (!cur.includes('console Plans 栏目补 BYOK')) {
  const anchor = '- **本地 core 实为 NSSM 服务（纠正第 24 节记忆）**';
  if (cur.includes(anchor)) {
    fs.writeFileSync(target, cur.replace(anchor, add + anchor), 'utf8');
    console.log('INSERTED before NSSM bullet');
  } else {
    fs.writeFileSync(target, cur + add, 'utf8');
    console.log('APPENDED at end');
  }
} else {
  console.log('ALREADY PRESENT');
}
