# 副脑04 · 更新指令（微信/支付宝私钥同步包）

> 发令：2026-08-01  
> **进程：NSSM `AI24X-core`**  
> **禁止**整文件覆盖 `.env`；应用脚本会**备份**后按键 upsert  
> 前提：主脑已从本机导出 zip，并拷到 04（如 `C:\ai24x-transfer\token-pay-bundle.zip`）

## 本包做什么

- 把微信 `apiclient_key.pem` + 支付宝商户私钥落到 `C:\ai24x01\api\certs\`  
- `.env` 写入 `*_PRIVATE_KEY_PATH`，清空 PEM 内联  
- `TOKEN_PAY_MOCK_ENABLED=false`、`TOKEN_PAY_REUSE_A1=false`  
- 重启 core → `wechat/alipay merchant_configured=true`

## 执行（PowerShell · 整段）

```powershell
# 0) 确认 zip 已在本机（主脑拷过来的）
Test-Path C:\ai24x-transfer\token-pay-bundle.zip

Set-Location C:\ai24x01
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline

Set-Location C:\ai24x01\api
python scripts_apply_token_pay_bundle.py C:\ai24x-transfer\token-pay-bundle.zip
# 若脚本未自动重启：
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status

$ps = (Invoke-WebRequest "http://127.0.0.1:8002/v1/billing/pay/status" -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
"mock=$($ps.token_pay_mock_enabled)"
"paypal=$($ps.paypal.ui_ready)"
"wechat_cfg=$($ps.wechat.merchant_configured) wechat_ui=$($ps.wechat.ui_ready)"
"alipay_cfg=$($ps.alipay.merchant_configured) alipay_ui=$($ps.alipay.ui_ready)"
if ($ps.wechat.missing) { "wechat_missing=$($ps.wechat.missing -join ',')" }

curl.exe -sS https://api.ai24x.com/v1/billing/pay/status
```

## 验收回报（勿贴密钥）

1. `mock=False`  
2. `wechat_cfg=True` `wechat_ui=True`  
3. `alipay_cfg=True` `alipay_ui=True`  
4. 控制台套餐页可见微信/支付宝按钮（Ctrl+F5）  
5. （可选）小额实付；若付了不加 Token →「确认到账」，并确认商户后台已登记 Token 回调 URL  

## 不要做

- 不要把 zip / pem 贴飞书公开群或提交 git  
- 不要手改把多行拼进同一行（上次 `.env` 损坏根因）  
- 不要再开 `TOKEN_PAY_MOCK_ENABLED=true`  
