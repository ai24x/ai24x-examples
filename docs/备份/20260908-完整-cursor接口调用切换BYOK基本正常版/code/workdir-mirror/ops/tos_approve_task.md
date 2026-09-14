# ToS/Privacy 定稿上线 · markets 国际版（雷总已拍板「按建议」）

> 授权依据：`p\markets\AGENTS.md` 例外审批流程——雷总 2026-08-16 下午已在会话中逐条拍板「按建议」，本任务为**批准后的定稿 + 上线准备**，不再是待审批草稿。
> 执行：行情官国际版 Codex 会话 · 产物：2 个英文页面 + commit + 回执 · 部署：司令统一执行

## 已拍板值（雷总确认，直接填入，不要再问）
1. Refund policy（1.5 节）→ **Unused subscription refunds are available within 14 days of purchase.**
2. Governing law（1.11 节）→ **the laws of Singapore**
3. Support email（2.5 / 2.8 节，两处）→ **support@ai24x.com**
4. Last updated → **August 16, 2026**

## 任务
1. 以 `ops\product-iteration\20260816\tos-privacy-draft-en.md` 为底稿，生成 2 个英文页面，风格与 markets 站点（app.html / index.html 深色主题）保持一致：
   - `p\markets\web\tos.html`（Terms of Service）
   - `p\markets\web\privacy.html`（Privacy Policy）
   - 页面顶部放返回链接（back to markets.ai24x.com），含 title / meta description / lang="en"；内容照草稿全文，填好上述 4 个拍板值。
2. 链接挂载：
   - `p\markets\web\index.html` 页脚加 ToS / Privacy 链接（/tos.html、/privacy.html）
   - `p\markets\web\app.html` 页脚（如有 footer）同步加（没有页脚则在登录/订阅面板附近加一行小字链接，保持英文）
3. 草稿标记定稿：把 `ops\product-iteration\20260816\tos-privacy-draft-en.md` 顶部 Status 改为 `✅ Approved v1.0（2026-08-16 雷总拍板）`，并填好 4 个值。
4. commit：message 注明「周复盘自主迭代（ToS/Privacy 审批定稿）」，只提交 `p\markets\web\tos.html`、`p\markets\web\privacy.html`、`p\markets\web\index.html`、`p\markets\web\app.html`（如 app.html 无改动则只提交前 3 个）；**草稿 ops 文件不入 commit**。

## 执行纪律
- 先 `git status` / `git log` 查重，不重复做已提交工作
- 纯静态页面，不改共享 js/css/locales；如需站点样式，参考现有内联 CSS 或独立 <style>，不动公共资源
- 自测：确认 tos.html / privacy.html 关键段落与拍板值在位、链接可达、无中文、HTML 无语法错误
- 不部署公网（部署由司令统一执行）
- 回执格式：✅ 改动清单（每项一行）+ 自测结果 + 部署建议
