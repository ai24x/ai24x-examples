# 副脑03 · 更新指令（免费注册/登录仅顶栏）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 顶栏 | 游客仅顶栏「登录」+「免费注册」；注册高亮绿、登录冷蓝 |
| 行情页 | 去掉查询区旁注册/登录；邀请条只文案引导看顶部 |
| 次数弹层 | 游客不出现「免费注册」按钮，文案引导点顶部 |
| SW | 静态缓存 **v33**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：header-only register / auth CTA / btn-auth-register

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web

Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. https://a.ai24x.com/demo.html （未登录，**Ctrl+F5**）  
2. 仅顶栏有「登录」「免费注册」（注册为绿色高亮）  
3. 查询区旁、邀请条上**无**注册/登录按钮  
4. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
