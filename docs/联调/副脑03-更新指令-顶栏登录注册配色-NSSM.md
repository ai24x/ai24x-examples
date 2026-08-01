# 副脑03 · 更新指令（顶栏登录/注册配色与手机尺寸）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 免费注册 | 实心亮蓝主入口（去掉绿色高亮/外发光） |
| 登录 | 淡蓝描边 + 浅底，次级可见 |
| 手机端 | 顶栏按钮略缩小，避免撑开 |
| SW | 静态缓存 **v34**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：header auth colors / btn-auth / static-v34

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web

Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. https://a.ai24x.com/demo.html （未登录，**Ctrl+F5**）  
2. 顶栏「免费注册」为亮蓝实心；「登录」为淡蓝描边浅底  
3. 手机宽度下按钮不撑开页面  
4. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
