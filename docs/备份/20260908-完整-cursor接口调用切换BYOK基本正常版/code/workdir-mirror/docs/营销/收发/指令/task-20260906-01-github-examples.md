# 【01 任务】创建 GitHub 仓库 ai24x-examples + 推送示例代码

> 通道：司令 → 01（同步直驱） ｜ 04 被 GitHub 屏蔽，改用 01 浏览器登录态执行 ｜ 老板已确认 01 浏览器已登录 GitHub

## 背景
GitHub 官方号 @ai24x（https://github.com/ai24x）已注册成功，仓库 ai24x-examples 待创建。

## 任务
1. **创建仓库**：用 01 浏览器登录 GitHub → `New repository` → 名 `ai24x-examples`、Public、MIT 许可证、Add a README
2. **推送示例骨架**（每个示例一个子目录，纯文件不进仓库元数据管理，直接 GitHub Web 编辑器或本地 git 推）：
   - `python/` — GPT-4o/DeepSeek via OpenAI SDK 接入示例（base_url、completions、streaming）
   - `curl/` — `curl -X POST` 示例（chat、models 列表示例）
   - `node/` — Node.js fetch 示例
3. **README** 写入：
   ```
   # AI24X Examples

   Example code for using AI24X Gateway — one OpenAI-compatible key for DeepSeek, Qwen, GLM, Kimi, GPT-5, and Claude.

   ## Quick Start
   ```python
   from openai import OpenAI
   client = OpenAI(base_url="https://api.ai24x.com/v1", api_key="sk-...")
   completion = client.chat.completions.create(model="flash", messages=[...])
   ```
   
   See individual directories for Python, Node.js, and curl examples.

   ## Docs
   - [AI24X Gateway](https://open.ai24x.com)
   - [Pricing](https://www.ai24x.com/pricing.html)
   - [BYOK Setup](https://open.ai24x.com)

   *Not investment advice. Educational purposes only.*
   ```
4. **红线**：示例 key 统一用 `sk-...` 占位符；禁止放真实密钥、内部路由地址、成本细节、数据源信息；禁止提及「投资/信号/股价」
5. **发布后**：截图仓库首页，落盘 `C:\Users\Administrator\ops\github-ai24x-examples-20260906.md`

## 回执
✅ 已完成项：仓库链接 / 示例文件清单 / 红线自查 0
⚠️ 问题项（无则写「无」）
