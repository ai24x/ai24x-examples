# 副脑04 · 更新指令（支付开关 + 商户验收）

> 发令：2026-08-01  
> **进程：NSSM `AI24X-core`（禁止 pm2 启停 core）**  
> **禁止**整文件覆盖 `api/.env`（只行级改；密钥勿贴回报）  
> 前提：主脑/运维已按清单把支付与 LLM 键写入 04 `.env`，私钥文件已落盘且 PATH 有效

## 本包目标

1. **关模拟到账**（生产禁止白嫖）  
2. 确认 **PayPal** 仍可用；**微信/支付宝** 若已配齐则 `ui_ready=true`  
3. 重启加载 `.env` → 公网验收

## 执行前自检（记事本打开 `C:\ai24x01\api\.env`，只看不贴密钥）

必须：

```
TOKEN_PAY_ENABLED=true
TOKEN_PAY_MOCK_ENABLED=false
```

建议已有：

```
TOKEN_WECHAT_NOTIFY_URL=https://api.ai24x.com/v1/billing/wechat/notify
TOKEN_ALIPAY_NOTIFY_URL=https://api.ai24x.com/v1/billing/alipay/notify
TOKEN_ALIPAY_RETURN_URL=https://www.ai24x.com/console.html
TOKEN_PAYPAL_RETURN_URL=https://www.ai24x.com/console.html
TOKEN_PAYPAL_CANCEL_URL=https://www.ai24x.com/console.html
```

微信/支付宝：`WECHAT_*` / `ALIPAY_*` 已填，且 `*_PATH` 指向 **本机真实 pem**。  
PayPal：`PAYPAL_MODE` / `CLIENT_ID` / `SECRET`（及 Webhook）已填。  
**不要**改 `DATABASE_URL`。

若曾用管理台开过「模拟支付」，覆盖文件也可能开着：优先在  
https://www.ai24x.com/token-admin.html →「开关与密钥」→ **模拟支付关** → 保存。

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若远端叫 gitee：git pull gitee master
git log -1 --oneline

# 行级确认（只打印键名是否存在，不打印值）
$envPath = "C:\ai24x01\api\.env"
@(
  "TOKEN_PAY_ENABLED",
  "TOKEN_PAY_MOCK_ENABLED",
  "TOKEN_WECHAT_NOTIFY_URL",
  "TOKEN_ALIPAY_NOTIFY_URL",
  "PAYPAL_MODE",
  "PAYPAL_CLIENT_ID",
  "WECHAT_MCH_ID",
  "ALIPAY_APP_ID",
  "DATABASE_URL"
) | ForEach-Object {
  $k = $_
  $hit = Select-String -Path $envPath -Pattern ("^" + [regex]::Escape($k) + "=") -ErrorAction SilentlyContinue
  if ($hit) { "OK_HAS $k" } else { "MISSING $k" }
}

# 模拟开关必须是 false（有值才打印；勿把整行发飞书）
Select-String -Path $envPath -Pattern "^TOKEN_PAY_MOCK_ENABLED=" | ForEach-Object { $_.Line }

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status

try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

# 支付状态（环回）
$ps = (Invoke-WebRequest "http://127.0.0.1:8002/v1/billing/pay/status" -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
"pay_enabled=$($ps.token_pay_enabled)"
"mock=$($ps.token_pay_mock_enabled)"
"paypal_ready=$($ps.paypal.ui_ready) mode=$($ps.paypal.mode)"
"wechat_cfg=$($ps.wechat.merchant_configured) wechat_ui=$($ps.wechat.ui_ready)"
"alipay_cfg=$($ps.alipay.merchant_configured) alipay_ui=$($ps.alipay.ui_ready)"
if ($ps.wechat.missing) { "wechat_missing=$($ps.wechat.missing -join ',')" }

# 公网
curl.exe -sS https://api.ai24x.com/health
curl.exe -sS https://api.ai24x.com/v1/billing/pay/status
```

---

## 验收（回报主脑，勿贴密钥）

1. `AI24X-core` = **Running**；环回 health = **200**  
2. **`mock=False` / `token_pay_mock_enabled=false`**（失败则立刻查 `.env` + token-admin 覆盖）  
3. `pay_enabled=True`  
4. `paypal_ready=True`（国际主通道）  
5. 若已配国内商户：`wechat_cfg=True` 且 `wechat_ui=True`；支付宝同理  
6. 浏览器 **Ctrl+F5**：  
   https://www.ai24x.com/console.html?plan=token_pack_10k&pay=paypal  
   - **不应**再出现「模拟到账」  
   - 应有 **PayPal**；微信/支付宝按钮仅在 `*_ui=True` 时出现  

### 小额实付（可选，主脑批准后再做）

- PayPal Live：1 笔最小套餐 → 回控制台确认余额增加  
- 微信/支付宝：小额一笔；若付了不加 Token → 订单点「确认到账」，并检查商户后台是否已登记 Token 回调 URL（**不要改 a1 原回调**）

---

## 回滚

- 仅支付开关：`.env` 行级改回 + `Restart-Service AI24X-core`  
- 或 token-admin 关真支付 / 临时开模拟（**仅排障，用完立刻关**）  
- 代码回滚：`git log -5` → `git revert` / `reset`（仅主脑明示）后再重启 core  

## 不要做

- 不要 `pm2 restart` core  
- 不要 Write 整份 `.env`  
- 不要把 `DATABASE_URL`、私钥、完整 `.env` 贴飞书  
- 不要生产长期 `TOKEN_PAY_MOCK_ENABLED=true`  
