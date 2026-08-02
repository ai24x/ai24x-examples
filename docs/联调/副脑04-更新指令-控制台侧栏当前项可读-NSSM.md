# 副脑04 · 更新指令（控制台左侧当前栏目文字可读 · 静态）

> 发令：2026-08-02 · **副脑04 = 对外生产**（www）  
> 目标提交：`6d1c227`（`fix(web): keep console sidebar active nav text readable`）  
> 范围：仅静态 `web/css/base.css` + `web/console.html`（**无需**重启 `AI24X-core`）  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

## 问题

控制台左侧当前栏目用了 `--accent-ink`（多为白字），浅色侧栏上看不清。

## 本包

| 项 | 说明 |
|----|------|
| CSS | `.console-nav-item.is-active` 改为 `color: var(--accent)` |
| 缓存 | `console.html` → `base.css?v=20260802r` |

## 执行

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望：6d1c227 fix(web): keep console sidebar active nav text readable
# （若仅差 docs SHA 钉死提交亦可，至少含本修复）

# 静态拉码即生效；硬刷新控制台即可（Ctrl+F5）
```

## 验收（回报主脑）

1. `git log -1` 为本包  
2. 打开 `https://www.ai24x.com/console.html` 硬刷新：左侧**当前栏目**为主题色（蓝/金等），**不是**白字  
3. 切换 Overview / API keys 等，当前项始终可读  

## 回滚

```powershell
git checkout HEAD~1 -- web/css/base.css web/console.html
# 或回退到上一稳定 SHA 后硬刷新
```

## 不要做

- 不要重启 core（本包无关 API）  
- 不要整文件覆盖 `.env`
