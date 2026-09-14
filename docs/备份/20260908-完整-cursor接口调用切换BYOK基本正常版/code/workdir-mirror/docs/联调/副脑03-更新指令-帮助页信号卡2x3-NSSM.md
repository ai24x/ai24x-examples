# 副脑03 · 更新指令（帮助页信号卡 2×3 布局）

> 发令：2026-07-30  
> **进程：NSSM（禁止 pm2）**  
> 仅静态 `help.html`；勿改 `.env` / 支付。

## 本包

- commit：拉最新 master 后以 `git log -1` 为准  
- `p/a1/web/help.html`：六个信号说明卡改为桌面端 **2 行 × 3 列**、卡片等高

## 执行（可整段转发 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline

Get-Service AI24X-a1-web, AI24X-a1-api, AI24X-core | Format-Table Name, Status
# 静态直出一般拉代码即生效；可选：
# Restart-Service AI24X-a1-web
```

## 验收

1. https://a.ai24x.com/help.html → **Ctrl+F5**  
2. 「圆点颜色」下方六个说明框为 **两行三列**（手机可两列）  
3. 回报：`git log -1`、布局是否正常  
