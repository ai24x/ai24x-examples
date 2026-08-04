# 副脑03 · 更新指令（顶栏导航统一居中）

> 发令：2026-08-04  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包为静态页；**不必**改 `.env`。

## 决策口径

全站顶栏与内容区统一 **居中**（`max-width: 1140px`），不要拉满视口左右边。

| 项 | 说明 |
|----|------|
| 原因 | 首页华为视口修正曾把 `.container`（含顶栏）写成 `100%`；本地旧 `header-inner:max-width:100%` 也会撑满 |
| 改动 | `base.css` 顶栏固定 1140 居中；首页 JS/CSS 撑宽只作用主内容，排除 header/footer |
| SW | 静态缓存 **v43**；`base.css`/`tool.css` 改为网络优先，减少「每次都要 F5」 |
| 页面 | 各页 `base.css?v=43` |

## 前置（主脑本机）

确认已 push 到 Gitee（含本包提交），再让副脑03 pull。

期望提交说明含：`header center` / `static-v43` / `顶栏导航统一居中`。

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：header / 居中 / static-v43

# 静态为主；可选重启 web 服务清静态句柄
Get-Service AI24X-a1-api, AI24X-a1-web | Format-Table Name, Status
Restart-Service AI24X-a1-web
Start-Sleep -Seconds 2
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }

# 确认关键文件已更新
Select-String -Path "p\a1\web\sw.js" -Pattern "static-v43" | Select-Object -First 1
Select-String -Path "p\a1\web\css\base.css" -Pattern "max-width: 1140px" | Select-Object -First 3
```

## 验收

1. 手机/桌面打开 https://a.ai24x.com/ （**首次可 Ctrl+F5 一次**，之后普通刷新应跟上）  
2. **首页**顶栏品牌 / 菜单 / 登录注册 与内容区同宽居中，**不贴左右边**  
3. **行情 / 帮助 / 我的** 顶栏宽度与首页一致（全站统一居中）  
4. 回报：`git log -1`、首页与其它页是否一致居中  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
Restart-Service AI24X-a1-web
```
