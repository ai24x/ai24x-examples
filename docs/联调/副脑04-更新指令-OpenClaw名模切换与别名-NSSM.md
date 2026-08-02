# 副脑04 · 更新指令（OpenClaw 名模切换 · Completions 别名 · NSSM）

> 发令：2026-08-03 · **副脑04 = 对外生产**（www + api）  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

## 本包做什么

| 项 | 说明 |
|----|------|
| API | `map_model_name`：`kimi`/`gpt`/`claude`/`gemini`/`mimo`/`qwen` 等短别名 → 规范 `vip-*`；`shared`/`free-shared` 归一；`gpt-4o` 等仍 drop-in 到 flash/pro |
| 静态 | OpenClaw 指南示例含 flash/pro/ultra/auto/shared + 中国/国际 VIP 样例；踩坑补充 shared 无 tools |

**智能体日常仍建议 `flash`/`pro`。** `shared` 仅免费文本；`vip-*` 需会员 + 预充。

## 执行

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline

# API 必须重启
nssm restart AI24X-core
# 或你们现用的重启方式；确认进程起来

# 静态随拉码生效；硬刷新
# https://www.ai24x.com/guides/openclaw.html
```

## 验收（回报主脑）

1. 本机/服务器：`cd api; python scripts_map_model_smoke.py` → 全 PASS  
2.（有 VIP+余额时）curl Completions：`model=kimi` 与 `model=vip-kimi` 均非落到 flash  
3. `model=shared` 文本可聊；带 tools 应 402（或明确需余额）  
4. 指南页示例可见 shared / vip-kimi / vip-claude-sonnet  

## 回滚

```powershell
git checkout HEAD~1 -- api/openai_compat.py web/guides/openclaw.html web/guides/index.html web/config/locales.js
nssm restart AI24X-core
```
