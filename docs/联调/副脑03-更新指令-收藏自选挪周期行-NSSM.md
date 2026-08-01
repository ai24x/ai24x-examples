# 副脑03 · 更新指令（收藏/自选挪到月线后 + 点亮配色）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 布局 | 查询行仅保留「输入 · 查询 · 分享」；「收藏 · 自选」移到日/周/月线后 |
| 配色 | 收藏琥珀金、自选青绿 |
| SW | 静态缓存 **v32**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：fav/watchlist beside period / chart-tools

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web

Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. https://a.ai24x.com/demo.html （**Ctrl+F5**，建议窄窗/手机）  
2. 日线/周线/月线右侧可见「收藏」「自选」（金/青绿）  
3. 查询行只有：输入框、查询、分享  
4. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
