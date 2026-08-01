# 副脑03 · 更新指令（邀请引导注册 + 行情页手机紧凑）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 邀请落地 | 未登录带邀请码时显示邀请条；顶栏/查询区主按钮「免费注册」、次「登录」 |
| 行情页 | 紧凑图例迁到 K 线下；去掉重复长图例；手机端主图更高、说明折叠 |
| SW | 静态缓存 **v31**（用户需 Ctrl+F5 或等 SW 更新） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：invite CTA / mobile compact / demo legend 相关

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选刷新 a1-web
# Restart-Service AI24X-a1-web

Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. https://a.ai24x.com/i/任意邀请码 （手机或窄窗，**Ctrl+F5**）  
   - 仍进查询页；可见「好友邀请你试用」+ **免费注册**  
2. 顶栏游客态：主「免费注册」、次「登录」  
3. 行情页：K 线下为紧凑图例（小底/关注…），**无**「小底（提前关注）」长列表重复  
4. 回报：`git log -1`、页面是否正常  

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
