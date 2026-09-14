# 副脑03 更新指令 · 行情官后台「会员与支付 · 套餐与定价」页优化（自动读取/卡片化/按元/亮色分层/年卡额度可填）

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee（origin 与 gitee 两远端均已到 1f3cded），拉码后 `git log -1` 应含「亮色分层」（目标提交 1f3cded）

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 后台套餐与定价页 | `admin_ui.py`：进入页面自动读取配置（不再手动点「读取」）；布局改为 6 张卡片（体验卡/月卡/年卡/支付与联调开关/伙伴成长档/伙伴结算模式） |
| 价格口径 | 标价改按「元」显示、保存自动 ×100 存分（如 8.8 → 880 分）；保存时空值跳过，避免空串误关「微信/支付宝支付」「成长/专业档开放」等开关 |
| 视觉分层 | 页面主标题渐变亮字 + 副标题弱化；卡片主标题提亮 + 蓝色竖条；价格标签绿色高亮 |
| 年卡额度 | 年卡「日上限/周上限」由纯文字改为可填输入框，与月卡共用 `vip_daily_cap` / `vip_weekly`（后端 vip_month 与 vip_year_999 本就共用同一额度键） |
| 其他 | 本包同时带入 6b9c988 起至 1f3cded 的完整提交链（含 待对账「确认未收款」、预警中心实时聚合等 ops 变更，位于仓库根 api/ 目录，属 token 主站；如主站服务尚未更新请另行按主站流程重启） |

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
if (-not (git log -1 --oneline | Select-String '亮色分层')) { Write-Host '!! 未拉到目标提交（应含 1f3cded 亮色分层），先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 重启后端（admin_ui.py 服务端渲染，必须重启 AI24X-a1-api）===' -ForegroundColor Cyan
if (Get-Service AI24X-a1-api -ErrorAction SilentlyContinue) { Restart-Service AI24X-a1-api } else { Write-Host '!! 未找到 AI24X-a1-api 服务' -ForegroundColor Red; exit 1 }
Start-Sleep -Seconds 3

Write-Host '=== 3/3 验收 ===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'http://127.0.0.1:8001/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health(8001)=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health(8001) FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'http://127.0.0.1:18011/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health(18011)=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health(18011) FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'https://a.ai24x.com/admin20260501' -UseBasicParsing -TimeoutSec 10; $has = $r.Content.Contains('bill-plan-title') -and $r.Content.Contains('bill_vip_daily_cap_year'); Write-Host "admin页面=$($r.StatusCode) 新样式元素=$has（True=已生效；浏览器 Ctrl+F5 刷新）" } catch { Write-Host "admin页面 FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1、health、admin页面 has 结果 ===' -ForegroundColor Green
```

## 三、上线后人工动作

无新增必配键。如需调整月卡/年卡每日/每周额度上限，可在后台「会员与支付 · 套餐与定价」页直接填「日上限/周上限」保存即生效；不填则按默认（日 150 / 周 500）执行。

## 四、回滚

```powershell
# 代码回滚：还原上次备份的 app 目录后重启
# Restart-Service AI24X-a1-api
# 配置回滚：本次无新增配置键；若需恢复旧页面样式，仅做代码回滚即可
# 数据库：无结构变更，无需回滚
```
