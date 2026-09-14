# 副脑03 更新指令 · 行情官月卡/年卡额度拆分（年卡独立键 vip_year_daily_cap / vip_year_weekly）

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee（origin 与 gitee 两远端均已到 0f23055），拉码后 `git log -1` 应含「额度拆分」（目标提交 0f23055）

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 后端额度解析 | `db.py`：`vip_year_999` 计划改为读取年卡独立键 `vip_year_daily_cap` / `vip_year_weekly`；未设置时自动回退月卡键 `vip_daily_cap` / `vip_weekly`（现有配置不设新键也照常工作） |
| 后台配置页 | `admin_ui.py`：年卡卡片「日上限/周上限」改为独立输入框，对应新键；月卡/年卡互不影响 |
| 口径说明 | 额度在购买/改档时定格写入账号，改后台配置只影响之后的新购/改档用户，不影响已购用户（月卡/年卡均为该口径） |

## 二、执行（PowerShell · 整段复制给 OpenClaw）

```powershell
$ErrorActionPreference = 'Stop'
$repo = 'C:\ai24x01'

Write-Host '=== 1/3 拉码 ===' -ForegroundColor Cyan
Set-Location $repo
git checkout master
git pull gitee master
if (-not $?) { git pull origin master }
git log -1 --oneline
if (-not (git log -1 --oneline | Select-String '额度拆分')) { Write-Host '!! 未拉到目标提交（应含 0f23055 额度拆分），先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 重启后端（db.py + admin_ui.py 改动，必须重启 AI24X-a1-api）===' -ForegroundColor Cyan
if (Get-Service AI24X-a1-api -ErrorAction SilentlyContinue) { Restart-Service AI24X-a1-api } else { Write-Host '!! 未找到 AI24X-a1-api 服务' -ForegroundColor Red; exit 1 }
Start-Sleep -Seconds 3

Write-Host '=== 3/3 验收 ===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'http://127.0.0.1:8001/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health(8001)=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health(8001) FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'http://127.0.0.1:18011/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health(18011)=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health(18011) FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'https://a.ai24x.com/admin20260501' -UseBasicParsing -TimeoutSec 10; $has = $r.Content.Contains('bill_vip_year_daily_cap') -and $r.Content.Contains('vip_year_daily_cap'); Write-Host "admin页面=$($r.StatusCode) 年卡独立键元素=$has（True=已生效；浏览器 Ctrl+F5 刷新）" } catch { Write-Host "admin页面 FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1、health、admin页面 has 结果 ===' -ForegroundColor Green
```

## 三、上线后人工动作

无新增必配键。如需给年卡单独设额度：后台「会员与支付 · 套餐与定价」页年卡卡片填「日上限/周上限」保存即生效；不填则回退月卡值（默认 150/500）。月卡与年卡已互不影响。

## 四、回滚

```powershell
# 代码回滚：还原上次备份的 app 目录后重启
# Restart-Service AI24X-a1-api
# 配置回滚：删除/置空 vip_year_daily_cap、vip_year_weekly 即回到「年卡跟随月卡」形态（置空=回退）
# 数据库：无结构变更，无需回滚
```
