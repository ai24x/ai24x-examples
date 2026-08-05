# 副脑03 更新指令 · 行情官用户中心 Tab 化：默认会员 / 伙伴计划分步引导 / 城市合伙人申请支付后填写

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee，拉码后 `git log -1` 应含「Tab化」「分步引导」「城市合伙人」

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 前台-用户中心 | `account.html` 顶部改为「会员 / 邀请推广 / 伙伴计划」Tab 切换，默认进入「会员」；Tab 样式统一主题（去掉白底，深浅色主题自适应），移动端可横滑 |
| 前台-伙伴计划 | 改为三步引导：一、选择档位并支付 → 二、填写申请信息 → 三、审核签约协议；申请表单改为支付成功后解锁，未支付时只提示先完成第一步，不再挡住支付按钮 |
| 前台-进度 | 分步引导随状态自动点亮：已支付 / 已申请 / 已签约分别标记完成；已签约后协议归档展示在「三、审核签约协议」区 |
| 后端-接口 | `db.py` 的 `/api/agent/overview` 新增 `has_partner_plan`（是否已支付成长档/专业档），前端据此控制申请表单显隐（该字段补齐到实际生效的函数定义，修复重复定义覆盖问题） |
| 其他修复 | 修复 `agent-comm-hint` 重复 id（回馈明细提示现在正确显示在明细表下方）；非 VIP 进入「伙伴计划」时显示引导提示而非空白 |

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
if (-not (git log -1 --oneline | Select-String 'Tab化|分步引导|城市合伙人')) { Write-Host '!! 未拉到目标提交，先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 重启后端（account.html 静态文件无需重启；db.py 改动需重启生效）===' -ForegroundColor Cyan
if (Get-Service AI24X-a1-api -ErrorAction SilentlyContinue) { Restart-Service AI24X-a1-api } else { Write-Host '!! 未找到 AI24X-a1-api 服务' -ForegroundColor Red; exit 1 }
Start-Sleep -Seconds 3

Write-Host '=== 3/3 验收 ===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'http://127.0.0.1:18011/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'https://a.ai24x.com/account.html' -UseBasicParsing -TimeoutSec 10; Write-Host "account.html=$($r.StatusCode)（前端静态文件无需重启，浏览器 Ctrl+F5 刷新）" } catch { Write-Host "account.html FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1、health 结果 ===' -ForegroundColor Green
```

## 三、上线后人工动作

1. `https://a.ai24x.com/account.html` 登录后 Ctrl+F5：默认落在「会员」Tab，「邀请推广」「伙伴计划」可切换。
2. 未支付伙伴档位的账号：进「伙伴计划」看到「一、选择档位并支付」高亮，申请表单不显示，提示先完成第一步。
3. 已支付成长档/专业档的账号：第一步标记完成，第二步「填写申请信息」表单自动出现，可提交城市合伙人申请。
4. 已签约城市合伙人：第三步显示正式《城市合伙人合作协议》与往来材料下载。
5. 接口核对：登录后 `/api/agent/overview` 返回字段含 `has_partner_plan`（true/false）。

## 四、回滚

```powershell
# 代码回滚：还原上次备份的 app + web 目录后重启
# Restart-Service AI24X-a1-api
# 本次无数据库结构变更，无需回滚数据库
```