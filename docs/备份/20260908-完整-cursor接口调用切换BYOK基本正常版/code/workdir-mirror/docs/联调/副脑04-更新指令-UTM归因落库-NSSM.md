# 副脑04 · 更新指令（UTM 归因落库）

> 发令：2026-08-02 · 目标提交 `6c4bd82`  
> 进程：NSSM `AI24X-core`（**需重启**以加载模型列 / 新路由）  
> **禁止**整文件覆盖 `api/.env`；本包**无需**改 `.env`  
> 远端：`git pull origin master`（或 `gitee master`）

## 本包内容

| 项 | 说明 |
|----|------|
| 前端 | `web/js/utm.js`：URL UTM/gclid → `localStorage` 首触；注册提交 |
| 注册 | `POST /v1/auth/register` 收 `utm_*` / `gclid` → `auth_users` 首触落库 |
| 充值归因 | **不在** `token_pay_orders` 冗余 UTM；订单 join 用户首触 |
| 管理 | `GET /v1/admin/token/acquisition?days=14`；用户列表/订单列表带 UTM 字段 |
| 迁移 | `init_db` 软加列（`utm_*` / `gclid` / `acquired_at`） |

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望：6c4bd82（feat(ads): first-touch UTM…）

# 勿动 DATABASE_URL

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 6
Get-Service AI24X-core | Format-Table Name, Status

try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

# 管理端（填内部密钥）看归因漏斗
# $k = "<SMS_INTERNAL_KEY>"
# curl.exe -sS "http://127.0.0.1:8002/v1/admin/token/acquisition?days=14" -H "X-SMS-Internal-Key: $k"
```

## 验收（回报主脑）

1. health **200**；`AI24X-core` Running  
2. 无痕打开：`https://www.ai24x.com/pricing.html?utm_source=google&utm_medium=cpc&utm_campaign=test_a`  
   → Application → Local Storage 有 `ai24x_utm_first`  
3. 注册后管理台用户行或 `/v1/admin/token/acquisition` 可见对应 `utm_campaign`  
4. 已支付订单列表带用户侧 `utm_source`（join，非订单表新列）

## 不要做

- 不要 Write 整份 `.env`  
- 不要 `pm2 restart` core  
- 不要改 PayPal 商户号  

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
# 回退本包提交后 Restart-Service AI24X-core
# 新列可保留（空值无害）
```
