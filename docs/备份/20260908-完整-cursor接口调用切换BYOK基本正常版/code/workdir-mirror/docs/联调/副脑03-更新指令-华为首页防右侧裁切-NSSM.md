# 副脑03 · 更新指令（华为浏览器首页防右侧裁切）

> 发令：2026-08-04  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 本包主要为静态页；一般**不必**改 `.env`。

## 本包内容

| 项 | 说明 |
|----|------|
| 现象 | 部分华为浏览器打开首页：页面偏宽、右侧裁切（注册 tab / 我的·VIP 按钮看不到） |
| 首页 | viewport 限制缩放；早期 JS 校正 layout/visual 视口差；手机强制单列 + 按钮 2×2 网格 |
| 全局 CSS | 关闭手机 `scrollbar-gutter: stable`；header/wrap/footer/`max-device-width` 防撑宽 |
| 顶栏 | 极窄屏「免费注册」缩为「注册」 |
| SW | 静态缓存 **v41**（用户需 Ctrl+F5） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若无 gitee 远端：git pull origin master
git log -1 --oneline
# 期望含：Huawei / overflow / static-v41 / 右侧裁切

Get-Service AI24X-a1-api, AI24X-a1-web, AI24X-core | Format-Table Name, Status
# 静态为主；建议：
Restart-Service AI24X-a1-web
```

## 验收

1. 华为浏览器打开 https://a.ai24x.com/ （**Ctrl+F5** 或清站点数据）  
2. 登录卡完整可见：登录/注册 tab、进入行情/我的、邀请等按钮不裁切  
3. 页脚「产品」列不贴边裁字  
4. 回报：`git log -1`、机型/浏览器、是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
Restart-Service AI24X-a1-web
```
