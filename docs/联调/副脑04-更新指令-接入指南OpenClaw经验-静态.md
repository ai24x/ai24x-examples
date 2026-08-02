# 副脑04 · 更新指令（接入指南 · OpenClaw 现场经验 + 关联页 · 静态）

> 发令：2026-08-03 · **副脑04 = 对外生产**（www）  
> 目标提交：`08bf963`（`docs(web): publish OpenClaw field notes on integration guides`）  
> 范围：仅静态 `web/guides/**` + `web/help.html` + `web/config/locales.js`（**无需**重启 `AI24X-core`）  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

## 本包要点

| 页 | 说明 |
|----|------|
| `guides/openclaw.html` | 完整经验：`/v1`、tools、真流式、VIP、405/401/402、干净会话、CLI 验收 |
| `guides/index.html` | 总述主推 Completions（流式+tools）；OpenClaw / LobeChat 卡片文案对齐 |
| Cursor / Continue / Open WebUI / LiteLLM / LobeChat | Key 须完整粘贴；tools → Completions（非仅 Responses） |
| `locales.js` | 中英同步；缓存 `?v=20260803b` |

## 执行

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline

# 静态拉码即生效；硬刷新即可（Ctrl+F5）
# 抽查：
# https://www.ai24x.com/guides/openclaw.html
# https://www.ai24x.com/guides/index.html
```

## 验收（回报主脑）

1. OpenClaw 页可见「工具 / 命令执行」「实测踩坑」等章节  
2. 中文站切换后文案为中文（非英文残留）  
3. 索引页 OpenClaw 卡片提到 tools / 流式，而非仅「根域名」  
4. **无需**重启 core（本包纯静态）

## 回滚

```powershell
git checkout HEAD~1 -- web/guides web/config/locales.js
# 或还原到上一已知好 SHA 后硬刷新
```
