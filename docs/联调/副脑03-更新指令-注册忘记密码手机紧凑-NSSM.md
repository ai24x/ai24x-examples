# 副脑03 · 更新指令（注册/忘记密码手机紧凑布局）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 首页账号区 | 登录/注册卡片保持两列；密码+忘记密码、验证码+获取验证码横排一行 |
| 忘记密码 | 弹层更短；验证码行横排；新密码/确认一行两列 |
| 加亮 | 「忘记密码」「发送验证码」淡蓝加强 |
| SW | 静态缓存 **v35**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：compact mobile auth / forgot password / static-v35

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web

Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. 手机宽度打开 https://a.ai24x.com/index.html?mode=register （**Ctrl+F5**）  
2. 「密码｜忘记密码」「验证码｜获取验证码」为一行两列；忘记密码按钮偏亮蓝  
3. 账户页打开忘记密码：验证码行横排，新密码/确认两列，表单明显变短  
4. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
