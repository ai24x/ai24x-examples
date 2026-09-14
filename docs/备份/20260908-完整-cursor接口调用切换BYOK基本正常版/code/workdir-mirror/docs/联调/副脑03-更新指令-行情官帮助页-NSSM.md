# 副脑03 · 更新指令（行情官使用帮助页）

> 发令：2026-07-30  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`、不必动支付。

## 本包内容

| 项 | 说明 |
|----|------|
| 新页 | `help.html` — AI行情官帮助指南（上手 / 圆点箭头 / 趋势线 / 副图 / 次数 / FAQ） |
| 导航 | 顶栏「帮助」、页脚「使用帮助」 |
| SW | 静态缓存 **v28**（用户需硬刷或等 SW 更新） |
| 文案 | 学习对照口径；不写算法细节；不作买卖建议 |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline
# 期望含：help.html / AI行情官帮助指南 相关提交

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status

# 静态由 Nginx 或 AI24X-a1-web 直出 p/a1/web：拉代码后一般立刻生效
# 可选：刷新 a1-web 进程（若用独立 http.server）
# Restart-Service AI24X-a1-web

# 本包无 API 逻辑硬依赖；若只更静态，可不重启 a1-api / core
Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. 打开 https://a.ai24x.com/help.html （**Ctrl+F5**）  
2. 顶栏可见「帮助」；页内有圆点色例、箭头、趋势线、副图说明  
3. 回报：`git log -1`、页面是否 200、验收是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git checkout HEAD~1 -- p/a1/web/help.html p/a1/web/js/shell.js p/a1/web/sw.js
# 并恢复各页 shell.js?v= 若需要
# Restart-Service AI24X-a1-web
```
