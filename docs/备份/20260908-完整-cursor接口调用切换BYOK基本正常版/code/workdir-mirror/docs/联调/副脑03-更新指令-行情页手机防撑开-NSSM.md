# 副脑03 · 更新指令（行情页手机防撑开 + 锁定深蓝）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 主题 | 去掉顶栏主题下拉，全站锁定深蓝 `calm` |
| 顶栏 | 手机品牌缩为「AI行情官」；去掉 auth `min-width`；栅格可收缩 |
| 查询行 | 网格布局防横向撑开；状态单独一行 |
| 中间区 | 保持原 `wrap` 最大宽度 `min(1360px,100%)`，不拉满屏 |
| SW | 静态缓存 **v36**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：mobile overflow / lock calm theme / static-v36

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web

Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. https://a.ai24x.com/demo.html （手机宽度，**Ctrl+F5**）  
2. 顶栏无主题下拉；品牌为短文案；登录/注册不撑开页面  
3. 查询框 + 查询/分享同一行且不横向溢出；中间内容区仍为居中统一宽度（非全屏拉满）  
4. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
