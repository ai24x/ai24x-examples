# 平台官 AGENTS.md — AI24X平台（token聚合出口基础平台）

> 本文件是平台官（AI24X平台项目总负责 🏗️）的通信协议。
> 实际收发通道：`docs\营销\收发\`（指令\ + 回复\，历史文件均在此）。

## 🔌 与总司令（主脑）的专项通信协议（2026-08-13 雷总定）

需要总司令/副脑/雷总配合时，走文件通道（总司令 cron 每 10 分钟轮询），不依赖飞书直接联系。

### 发需求给总司令
1. 需求写文件：`docs\营销\收发\指令\YYYYMMDD-HHMM-需求名.md`
2. 内容模板：`# 需求类型：①总司令直接办 / ②需副脑办(注明) / ③需雷总审批` + `# 需求描述` + `# 验收标准`
3. 写完即止，总司令自动处理

### 收总司令结果
- 结果写 `docs\营销\收发\回复\<指令文件名>-out.md`，需要时读取

### 规则
- 能自己搞定的（写代码/本地测试）直接干，不发总司令
- 涉副脑生产/跨机器/需雷总审批 → 写指令发总司令

## 📌 更新指令统一规范（2026-08-28 主脑签发 · Codex + Cursor 共同执行）

**背景：** 8/27-28 副脑03/04 更新延迟不执行，群无回执。根因：①指令文件落盘后未 push 到 Gitee（untracked 未提交）②主脑侧有 gitee / origin 两个 remote，副脑只拉 origin，只推 gitee 副脑收不到。

**统一规则（每次更新/派发必做）：**
1. **落盘即提交**：指令文件、任务书、代码改动完成后，立即 `git add` + `git commit`（信息写清 日期+对象+内容）
2. **双推才算送达**：commit 后必须推**两个 remote**：
   - `git push gitee master`（→ gitee.com/ai24x/ai24x01.git）
   - `git push origin master`（→ gitee.com/ai24x/ai24x-website.git，**副脑实际拉取的仓库**）
   - 缺一不可，只推一个 = 没送达
3. **推送后自检**：`git status` 确认无未提交的指令/任务书文件；`git log origin/master -1` 确认最新提交已同步
4. **指令命名**：统一 `YYYYMMDD-HHMM-对象-动作-摘要.md`，落盘到对应收发目录
5. **不要重复派发**：已提交/已执行的任务不重复驱动；确认状态先查 git log 与回复目录

**验证标准：** 副脑 `git pull origin master` 能拉到最新提交 + 收到指令文件 + 回执到位，才算一次成功派发。

### 04 派发通道（2026-08-29 与 Codex 定稿统一）

- **标准代码更新（默认）**：`powershell -File scripts\deploy04_direct.ps1 <指令.ps1>` —— ssh 直跑、无 LLM、成功自动发指挥部群
- **复杂任务**（DB / nginx / 后台操作）：`powershell -File scripts\deploy04.ps1 <指令.ps1>` —— 04 openclaw
- 指令从 `docs/营销/收发/指令/TEMPLATE-更新部署验收.md` 生成；末行保留 `# ✅ 04更新完成｜…`
- Cursor 细则：`.cursor/rules/deploy-brain04.mdc`

> Cursor/Codex 执行细则见仓库根 `.cursor/rules/dispatch-dual-push.mdc`、`.cursor/rules/deploy-brain04.mdc`、`.cursor/rules/deploy-brain03-a1.mdc`。

## 副脑速查
- 01 42.192.1.93（游戏生产+构建测试）｜02 118.89.111.23（运营）｜03 123.207.199.238（国内生产）｜04 43.160.246.30（国际生产/PayPal）
