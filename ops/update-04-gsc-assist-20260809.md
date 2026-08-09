# AI24X 04 辅助指令 · GSC 收录修复后续（只读 + sitemap ping）

## 背景
2878e47 已上线（canonical 归一 / noindex / sitemap 补全 / nginx 软 404 修复），公网已复核通过。
「请求验证修复」无 GSC API 支持且需 Google 登录态 → 由雷总在 GSC 页面人工操作，你不要代点、不要尝试登录雷总账号。

## 任务（全部只读，不改任何生产配置）
1. 检查本机是否有 GSC API 访问能力（search console service account / OAuth token / 已保存凭据）：
   - 有 → 拉取 site=sc-domain:ai24x.com 的 URL Inspection / Index coverage 数据，导出含 canonical 相关（Google chose different canonical / Alternate page with proper canonical）的受影响 URL 清单，落盘 ops/gsc-index-20260809.md + .json
   - 无 → 明确报告「无 GSC API 凭据」，不强行尝试
2. ping sitemap 加速重抓：
   - curl -s -o /dev/null -w "%{http_code}" "https://www.google.com/ping?sitemap=https%3A%2F%2Fwww.ai24x.com%2Fsitemap.xml" → 期望 200
   - Bing 同款 ping：https://www.bing.com/ping?sitemap=... 可选
3. 复核（curl 公网，3 项）：
   a. https://www.ai24x.com/ 首页 canonical = https://www.ai24x.com/
   b. 不存在路径返回 404（不再是 200）
   c. /sitemap.xml 含 guides/codex.html 且首页 loc 为根路径
4. 飞书私信 + 群回执（✅ / ⚠️，注明 GSC API 有无凭据）

- 全程只读：不修改代码、不重启 core、不碰 nginx
