# 副脑03 更新指令 · 行情官邀请奖励「日爆发」与封顶（+20/日 +100/周 · 日封顶 200 · 周封顶 1000）

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee，拉码后 `git log -1` 应含「日爆发」（代码提交 837f771，其后可能跟一条 docs 提交）

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 邀请奖励逻辑 | `db.py`：每激活 1 人，邀请人 **当日 +20 次**、**本周 +100 次**；新增 `invite_daily_cap`（默认 200）对日奖励按日封顶；周奖励仍按 `invite_weekly_cap`（默认 1000）封顶；周额度只统计周奖励类型（修复日奖励混入周额度的问题） |
| 后台配置 | `admin_ui.py`：邀请奖励配置区新增「邀请人日封顶（奖励累计）」输入框，可在线调整 |
| 前台文案 | `account.html`：邀请奖励提示改为「好友首次有效查询后到账（你 +100/周，+20/日，当日奖励封顶 200 次，每周奖励封顶 1000 次）」 |
| 配置口径 | 被邀请人不再额外赠送（注册即享免费档 100/周、20/天）；无数据库结构变更，启动自动建表逻辑不受影响 |

## 二、执行（PowerShell · 整段复制给 OpenClaw）

```powershell
$ErrorActionPreference = 'Stop'
$repo = 'C:i24x01'

Write-Host '=== 1/3 拉码 ===' -ForegroundColor Cyan
Set-Location $repo
git checkout master
git pull gitee master
if (-not $?) { git pull origin master }
git log -1 --oneline
if (-not (git log -1 --oneline | Select-String '日爆发')) { Write-Host '!! 未拉到目标提交，先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 重启后端（db.py 逻辑改动，必须重启 AI24X-a1-api）===' -ForegroundColor Cyan
if (Get-Service AI24X-a1-api -ErrorAction SilentlyContinue) { Restart-Service AI24X-a1-api } else { Write-Host '!! 未找到 AI24X-a1-api 服务' -ForegroundColor Red; exit 1 }
Start-Sleep -Seconds 3

Write-Host '=== 3/3 验收 ===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'http://127.0.0.1:18011/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $c = Invoke-WebRequest 'http://127.0.0.1:18011/api/public/invite/config' -UseBasicParsing -TimeoutSec 5; Write-Host "invite_config=$($c.StatusCode) $($c.Content)" } catch { Write-Host "invite_config FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'https://a.ai24x.com/account.html' -UseBasicParsing -TimeoutSec 10; Write-Host "account.html=$($r.StatusCode)（前端静态文件无需重启，浏览器 Ctrl+F5 刷新）" } catch { Write-Host "account.html FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1、health、invite_config 结果 ===' -ForegroundColor Green
```

## 三、上线后人工动作（后台配置 7 个键）

管理后台 `https://a.ai24x.com/admin20260501` →「系统管理」→ 邀请奖励配置（或 /api/admin/config 直接写入）：

| 键 | 值 |
|------|------|
| invite_reward_inviter_weekly | 100 |
| invite_reward_inviter_daily | 20 |
| invite_daily_cap | 200 |
| invite_weekly_cap | 1000 |
| invite_reward_invitee_weekly | 0 |
| invite_reward_invitee_daily | 0 |
| free_weekly / free_daily_cap | 100 / 20（如未设置） |

设完后 `GET /api/public/invite/config` 应返回：`invite_reward_inviter_weekly=100`、`invite_reward_inviter_daily=20`、`invite_daily_cap=200`、`invite_weekly_cap=1000`、`invite_reward_invitee_weekly=0`、`invite_reward_invitee_daily=0`。

## 四、回滚

```powershell
# 代码回滚：还原上次备份的 app 目录后重启
# Restart-Service AI24X-a1-api
# 配置回滚：后台把 invite_reward_inviter_daily 置 0、invite_daily_cap 置 0 即回到「仅周奖励」形态
# 数据库：无结构变更，无需回滚
```
