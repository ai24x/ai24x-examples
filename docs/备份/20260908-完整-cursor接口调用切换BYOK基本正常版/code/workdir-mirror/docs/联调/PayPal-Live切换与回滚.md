# PayPal Live 切换与回滚（短 runbook）

> 前提：Sandbox 公网已闭环（`paypal-sandbox-ok-20260728` / `4016597`）。  
> **Live 只开在副脑04**（`www`+`api` 迁新加坡后）；副脑03 过渡期继续 Sandbox。  
> 禁止整文件覆盖 `.env`。

## 上线前检查（P0）

1. PayPal 商户审核已通过  
2. `www` / `api` 已在 **副脑04**（或你明确批准临时在 03 开 Live——默认不建议）  
3. Live 应用的 Client ID / Secret 已准备（与 Sandbox **不同**）  
4. RETURN/CANCEL：`https://www.ai24x.com/console.html`  
5. （建议）Webhook：`https://api.ai24x.com/v1/billing/paypal/webhook` + `PAYPAL_WEBHOOK_ID`  
6. `TOKEN_PAY_MOCK_ENABLED=false`  
7. 入门包是否已从联调价改回正式国际价（产品拍板）

## 切换步骤（约 10 条）

1. 备份当前生产 `api/.env`（复制为 `.env.bak_before_paypal_live_时间戳`）  
2. 行级改：
   ```
   PAYPAL_MODE=live
   PAYPAL_CLIENT_ID=<Live>
   PAYPAL_CLIENT_SECRET=<Live>
   TOKEN_PAYPAL_RETURN_URL=https://www.ai24x.com/console.html
   TOKEN_PAYPAL_CANCEL_URL=https://www.ai24x.com/console.html
   ```
3. 自检：无省略号 `…`、无引号包裹密钥  
4. `pm2 restart core-api-8002 --update-env`（或 delete+start 门禁）  
5. `GET /v1/billing/pay/status` → `paypal.mode=live`，`ui_ready=true`  
6. 小额 Live 实付 1 笔（真实卡/余额）  
7. 确认回跳到账、管理后台订单 `paid`  
8. 看错误日志无 `invalid_client`  
9. 通知主脑：Live 首单 OK  
10. 更新指挥中心/作战卡状态

## 回滚（约 6 条）

1. 行级改回 `PAYPAL_MODE=sandbox` + Sandbox ID/Secret（或注释 PayPal 键隐藏按钮）  
2. `pm2 restart … --update-env`  
3. 验收：`pay/status` 为 sandbox 或 `paypal_ready=false`  
4. 已 Live 成交订单不回滚资金；仅停新单  
5. 若密钥写坏导致 API 起不来：用 `.env.bak_before_paypal_live_*` 对照恢复  
6. 回报主脑

## 明确不做

- 不在副脑03 长期养 PayPal Live 国际用户再整库搬 04  
- 不把 Live 密钥写入 git / 公开页 / 飞书群  
