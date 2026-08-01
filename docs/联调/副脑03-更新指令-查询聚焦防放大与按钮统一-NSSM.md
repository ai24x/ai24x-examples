# 副脑03 · 更新指令（查询聚焦防放大 + 按钮尺寸统一）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 防放大 | 点查询框不再整页放大：`maximum-scale=1` + 查询框 16px + `max-device-width` |
| 查询区 | 手机：输入独占一行，查询/分享下一行两列 |
| 按钮统一 | 查询/分享/日周月/收藏/自选：高 36px、字号 13px（配色仍区分） |
| SW | 静态缓存 **v38**（用户需 Ctrl+F5 / 清缓存） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：focus zoom / unify quote buttons / static-v38

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web

Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. 手机打开 https://a.ai24x.com/demo.html （**Ctrl+F5**）  
2. **点查询输入框**：页面不应再整页放大撑开  
3. 查询/分享/收藏/自选/日周月按钮高度与字号看起来一致  
4. 电脑端同样按钮尺寸统一  
5. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
