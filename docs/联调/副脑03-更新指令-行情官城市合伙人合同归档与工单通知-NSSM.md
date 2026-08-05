# 副脑03 更新指令 · 行情官城市合伙人「合同归档」与工单/审核自动通知

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee，拉码后 `git log -1` 应含「合同归档」「城市合伙人」

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 合同上传 | 新增表 `partner_contract_files`（服务启动自动建表，无需手动 SQL）；文件存 `api/server/data/contracts`，仅 PDF/JPG/PNG、≤10MB、随机文件名防路径穿越 |
| 前台 | `account.html` 城市合伙人区：申请后可上传补充材料（最多 4 份，可删除）；已签约后展示并下载「官方合同/往来材料」 |
| 后台 | 「城市合伙人申请审核」卡片每行新增「材料/合同」按钮：查看/下载/删除附件，上传正式《城市合伙人合作协议》归档 |
| 自动通知 | 审核通过/驳回、正式合同归档、工单回复/关闭 → 自动站内通知用户（user_notices，前台通知栏可见） |
| 工单系统 | 前台 `feedback.html` + 后台「用户反馈」面板为既有功能，本次补齐「回复后通知用户」闭环 |
| 安全 | 附件接口按「本人或管理员」鉴权；用户不能删除官方合同；上传限流 |

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
if (-not (git log -1 --oneline | Select-String '合同归档')) { Write-Host '!! 未拉到目标提交，先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 重启后端（启动时自动建表 partner_contract_files）===' -ForegroundColor Cyan
if (Get-Service AI24X-a1-api -ErrorAction SilentlyContinue) { Restart-Service AI24X-a1-api } else { Write-Host '!! 未找到 AI24X-a1-api 服务' -ForegroundColor Red; exit 1 }
Start-Sleep -Seconds 3

Write-Host '=== 3/3 验收 ===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'http://127.0.0.1:18011/health' -UseBasicParsing -TimeoutSec 5; Write-Host "health=$($r.StatusCode) $($r.Content)" } catch { Write-Host "health FAIL $($_.Exception.Message)" -ForegroundColor Red }
try { $r = Invoke-WebRequest 'https://a.ai24x.com/account.html' -UseBasicParsing -TimeoutSec 10; Write-Host "account.html=$($r.StatusCode)（前端静态文件无需重启，浏览器 Ctrl+F5 刷新）" } catch { Write-Host "account.html FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1、health 结果 ===' -ForegroundColor Green
```

## 三、上线后人工动作

1. 用 `iamlei` + 短信验证码登录 `https://a.ai24x.com/admin20260501/login`，打开「城市合伙人申请审核」卡片。
2. 待审核申请点「材料/合同」可查看用户上传材料并下载；点「通过」后自动签约生成协议号并通知用户。
3. 已通过/已驳回申请行点「材料/合同」→「上传归档」上传正式《城市合伙人合作协议》（PDF），用户前台立即可下载并收到通知。
4. 前台 `https://a.ai24x.com/account.html`：已付费账号申请后可上传材料；已签约账号显示「官方合同」下载入口。
5. 工单：`https://a.ai24x.com/feedback.html` 提交 → 后台「用户反馈」回复 → 用户前台收到「工单已回复」通知。

## 四、回滚

```powershell
# 代码回滚：还原上次备份的 app 目录后重启
# Restart-Service AI24X-a1-api
# 数据库：若已产生合同记录需回退，pg_restore 前次备份；仅清业务表 partner_contract_files 亦可（不影响 users/quota/pay_orders）
# 文件：api/server/data/contracts 下合同文件随表删除清理（勿删 signal_cache）
```
