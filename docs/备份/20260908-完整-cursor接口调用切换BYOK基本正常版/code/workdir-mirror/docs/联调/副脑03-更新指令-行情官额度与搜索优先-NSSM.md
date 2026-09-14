# 副脑03 · 更新指令（行情官额度防误扣 + 搜索个股优先）

> 发令：2026-07-28  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 勿整文件覆盖 `.env`；勿动支付回调。

## 本包内容

| 项 | 说明 |
|----|------|
| 防连点 | 查询进行中禁用查询/周期切换 |
| 计次 | **同标的自然日只扣 1 次**（换日/周/月、刷新不另扣；服务端兜底） |
| 周期切换 | 内存缓存，减轻卡顿；换周期不扣次 |
| 搜索 | 搜「东方财富」等：**个股优先**，不再被「热股 BK」顶掉 |
| 短信文案 | 内部密钥错误改为用户口吻（密钥对齐仍靠现网 `.env`，本包不改密钥） |
| SW | 静态缓存 **v26**（须让用户硬刷或清 SW） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
# 路径以现网为准（常见 C:\ai24x01）
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline

# 确认服务名（勿用 pm2）
Get-Service AI24X-core, AI24X-a1-api, AI24X-a1-web | Format-Table Name, Status

# 本包：a1 API 有 db.py 扣次逻辑；静态 demo/sw/shell 由 a1-web 目录直出
# 若 Nginx 直出 p/a1/web，拉代码后静态即更新；仍建议重启 a1-api 加载新 db.py
Restart-Service AI24X-a1-api
# 若 a1-web 为独立 Python http.server 且偶发缓存异常，可一并：
# Restart-Service AI24X-a1-web

# 主站仅短信文案软化（可选；密钥已对齐则可重启）
Restart-Service AI24X-core

Start-Sleep -Seconds 3
Get-Service AI24X-core, AI24X-a1-api, AI24X-a1-web | Format-Table Name, Status
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. https://a.ai24x.com/demo.html → **Ctrl+F5**（或注销 Service Worker 后再刷）  
2. 登录免费账号：查一只票只 −1；切日/周/月 **不减**；F5 同票 **不减**  
3. 搜「东方财富」：列表**先出个股 300059**，再才是热股 BK  
4. 回报：`git log -1`、三服务 Running、上述验收是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
# 回退到本包上一提交后：
# git checkout <上一好 commit> -- p/a1/web/demo.html p/a1/web/sw.js p/a1/web/js/shell.js p/a1/api/server/app/db.py
Restart-Service AI24X-a1-api
```
