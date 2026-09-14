# 副脑03 · 更新指令（加载提示静默 + 手机行距适中）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 状态行 | 默认不显示「加载中…/查询中…」；仅错误、请输入、多结果等真实提示才出现 |
| 占位 | 加载时不再闪「—」假行情条 |
| 行距 | 手机卡片内周期/查询/白名单芯片间距略放宽（不过密） |
| SW | 静态缓存 **v40**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：quiet status / spacing / static-v40

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web
```

## 验收

1. 手机打开 https://a.ai24x.com/demo.html （**Ctrl+F5**）  
2. 默认进页 / 点查询：不应刷出「加载中…」；失败或需选择时才有提示  
3. 周期行、查询行、上证指数芯片之间间距适中（不过密）  
4. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
