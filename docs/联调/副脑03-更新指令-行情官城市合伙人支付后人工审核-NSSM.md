# 副脑03 更新指令 · 行情官城市合伙人「支付后人工审核」流程

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee，拉码后 `git log -1` 应含「城市合伙人申请-支付后人工审核流程」

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 流程 | 城市合伙人改为「先付费（成长档5000/合作伙伴10000）→ 前台提交申请 → 后台人工审核 → 通过即签约」 |
| 数据库 | 新增表 `city_partner_applications`（id/用户/区域/联系人/身份证/手机/备注/状态/审核备注/时间）；服务启动自动建表，**无需手动 SQL** |
| 前台 | `account.html` 伙伴计划区新增申请表单；未付费/已签约/重复提交均拦截提示；被驳回显示原因可重新申请 |
| 后台 | 新增「城市合伙人申请审核」卡片：待审核优先、状态筛选、搜索；通过可改区域/协议号，自动生成协议号 `CP-年份-序号`；驳回需填原因 |
| 安全 | 审核接口走管理员鉴权（X-Admin-Key）；申请接口走用户登录态，校验已支付成长档/合作伙伴 |

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
if (-not (git log -1 --oneline | Select-String '城市合伙人')) { Write-Host '!! 未拉到目标提交，先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 重启后端（启动时自动建表）===' -ForegroundColor Cyan
if (Get-Service AI24X-a1-api -ErrorAction SilentlyContinue) { Restart-Service AI24X-a1-api } else { Write-Host '!! 未找到 AI24X-a1-api 服务' -ForegroundColor Red; exit 1 }
Start-Sleep -Seconds 3

Write-Host '=== 3/3 验收 ===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'http://127.0.0.1:18011/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'https://a.ai24x.com/account.html' -UseBasicParsing -TimeoutSec 10; Write-Host "account.html=$($r.StatusCode)（前端静态文件无需重启，浏览器 Ctrl+F5 刷新）" } catch { Write-Host "account.html FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1、health 结果 ===' -ForegroundColor Green
```

## 三、上线后人工动作

1. 用 `iamlei` + 短信验证码登录 `https://a.ai24x.com/admin20260501/login`，确认后台出现「城市合伙人申请审核」卡片。
2. 前台 `https://a.ai24x.com/account.html` 伙伴计划区，用已支付成长档/合作伙伴的账号提交申请 → 后台应出现待审核记录。
3. 后台点「通过」→ 该用户变「已签约」，自动生成协议号（如 `CP-2026-0001`）；点「驳回」填原因 → 前台显示原因、可重新申请。
4. 未付费账号提交申请 → 提示需先购买成长档/合作伙伴，符合「支付后人工审核」口径。

## 四、回滚

```powershell
# 代码回滚：还原上次备份的 app 目录后重启
# Restart-Service AI24X-a1-api
# 数据库：若已产生审核数据需回退，pg_restore 前次备份 或 仅清空业务表 city_partner_applications（不影响 users/quota/pay_orders）
```
