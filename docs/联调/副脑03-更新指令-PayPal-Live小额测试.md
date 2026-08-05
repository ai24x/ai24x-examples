# 副脑03 · PayPal Live 生产小额测试（临时）

> 发令：2026-07-29  
> 说明：商户审核已通过、标准版 Checkout。规划上 Live 目标在副脑04；**本次主脑批准在 03 做小额实付验收**，测完可回滚 Sandbox。  
> **禁止**：整文件覆盖 `.env`；把 Client Secret / 任何密钥提交 Gitee / 贴回聊天。  
> **进程**：NSSM `AI24X-core`（不要用 pm2）。

## Gitee / 代码（主脑侧说明）

- **`.env` / 密钥：永不进 Gitee。**  
- PayPal Orders 代码此前已在仓库（Sandbox 已公网闭环），本次 Live **主要是生产行级改环境变量**，不是再推一套支付源码。  
- 可选：主脑若另推了文档/MiMo 等，03 可 `git pull`；与 Live 密钥无关。

## 你需要的 Live 凭证（主脑私发或记事本手填，勿回传完整 Secret）

| 键 | 值来源 |
|----|--------|
| `PAYPAL_CLIENT_ID` | PayPal 开发者后台 **Live** 应用（与 Sandbox 不同） |
| `PAYPAL_CLIENT_SECRET` | 同上 Live Secret |
| `PAYPAL_WEBHOOK_ID` | `15d01cd5-f9e1-4309-a09d-f9dc486e5634`（须与 Live 应用下该 Webhook 一致） |

Webhook URL（PayPal 后台已配则核对）：`https://api.ai24x.com/v1/billing/paypal/webhook`

---

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01   # 以现网路径为准

# 0) 可选：拉最新代码（无密钥；失败不阻断下面改 env）
git checkout master
git pull origin master
git log -1 --oneline

# 1) 备份 env（复制文件，勿用 Agent Write 覆盖）
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item api\.env "api\.env.bak_before_paypal_live_$stamp"

# 2) 记事本行级改 api\.env（保存后关闭）
#    确保有且仅为 Live（无引号、无省略号…）：
# PAYPAL_MODE=live
# PAYPAL_CLIENT_ID=<Live Client ID>
# PAYPAL_CLIENT_SECRET=<Live Secret>
# PAYPAL_WEBHOOK_ID=15d01cd5-f9e1-4309-a09d-f9dc486e5634
# TOKEN_PAYPAL_RETURN_URL=https://www.ai24x.com/console.html
# TOKEN_PAYPAL_CANCEL_URL=https://www.ai24x.com/console.html
# TOKEN_PAY_MOCK_ENABLED=false
notepad api\.env

# 3) 脱敏自检（不要贴出完整密钥）
Select-String -Path api\.env -Pattern '^PAYPAL_MODE=|^PAYPAL_WEBHOOK_ID=|^TOKEN_PAYPAL_|^TOKEN_PAY_MOCK'
Select-String -Path api\.env -Pattern '^PAYPAL_CLIENT_ID=|^PAYPAL_CLIENT_SECRET=' | ForEach-Object {
  $k,$v = $_.Line.Split('=',2)
  $v = $v.Trim()
  "$k set=$([bool]$v) len=$($v.Length) has_ellipsis=$($v -match [char]0x2026)"
}

# 4) 重启主站 API（NSSM）
Restart-Service AI24X-core
Start-Sleep -Seconds 3
Get-Service AI24X-core | Format-Table Name, Status
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }

# 5) 支付状态
curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
# 期望：paypal.mode=live，ui_ready/ready 类字段为 true，webhook_id_set=true
curl.exe -sS https://api.ai24x.com/v1/billing/pay/status
```

## 验收（浏览器）

1. 登录 https://www.ai24x.com/console.html  
2. 用 **PayPal Live** 小额买一笔（建议入门包或最小档）  
3. 回跳后余额/订单为已支付；管理台可见 `paid`  
4. 回报主脑：`pay/status` 摘要（mode/ready）+ 订单号前缀 `T…`（**禁止**回传 Secret）

## 回滚（测完或异常）

```powershell
# 行级改回：
# PAYPAL_MODE=sandbox
# PAYPAL_CLIENT_ID=<原 Sandbox>
# PAYPAL_CLIENT_SECRET=<原 Sandbox>
# （Webhook 可留或改回 Sandbox 的 ID）
notepad C:\ai24x01\api\.env
Restart-Service AI24X-core
curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
```

或从 `api\.env.bak_before_paypal_live_*` 对照恢复后重启。  
已 Live 成交资金不回滚，仅停新单。
