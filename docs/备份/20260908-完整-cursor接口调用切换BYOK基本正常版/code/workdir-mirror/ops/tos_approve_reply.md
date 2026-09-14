**ToS/Privacy 定稿上线页已完成并提交。**

✅ **改动清单**
- 新增 `p/markets/web/tos.html`：Terms of Service 英文页（深色主题、back link、meta/canonical 齐全）
- 新增 `p/markets/web/privacy.html`：Privacy Policy 英文页（同风格）
- 4 个拍板值已全部填入：14 天内未用退款 / 新加坡法律 / `support@ai24x.com`（两处）/ Last updated 2026-08-16
- `index.html` 页脚挂 ToS/Privacy 链接；`app.html` 页脚下方加小字链接（独立 div，避开 `data-i18n` 覆盖）
- 草稿 `ops/product-iteration/20260816/tos-privacy-draft-en.md` 已标记 ✅ Approved v1.0 并填值，**不入 commit**

✅ **自测**：关键段落与拍板值逐项命中、两页无中文、无标签失衡、页脚链接可达；commit `c385e19`（4 文件 +149/-1）。

🚀 **部署建议**：纯静态文件，04 同步 4 个文件到 markets web 目录即可生效（无需重启 core），部署后验证 `/tos.html`、`/privacy.html` 200 即可；需要我现在出 04 部署指令吗？

一句话总结：ToS/Privacy 已按雷总拍板值定稿上线（`c385e19`），页面与页脚链接就绪，只待司令部署 04。