# 副脑03 · 更新指令（手机查询一行紧凑）

> 发令：2026-08-02  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 查询行 | 手机一行：表单 50% + 查询/分享各约 25% |
| 空隙 | 收紧周期行、查询行与「上证指数」芯片之间间距 |
| SW | 静态缓存 **v39**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：compact mobile search row / static-v39

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；可选：Restart-Service AI24X-a1-web
```

## 验收

1. 手机打开 https://a.ai24x.com/demo.html （**Ctrl+F5**）  
2. 查询输入与「查询」「分享」同一行；输入约占一半  
3. 「上证指数」芯片上方无明显多余空白  
4. 回报：`git log -1`、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# Restart-Service AI24X-a1-web
```
