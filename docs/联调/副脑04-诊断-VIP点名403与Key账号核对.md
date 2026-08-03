# 副脑04 · 诊断（VIP 点名 403 · Key 与账号核对）

> 发令：2026-08-03 · 场景：控制台已是 Token VIP + 开发包余额，curl `vip-kimi` 仍 403  
> **结论先说**：VIP 绑在**账号钱包**，**不绑在 Key 上**；**无需**因「充值前生成」而重建 Key。  
> 403 = 当前这把 Key 解析到的账号 **`is_vip_active=false`**（或 Key 根本不是 lei@itxin.com 的）。

## 立刻自证（不换 Key）

用**调试同一把** `sk-…`：

```powershell
# 1) 看这把 Key 绑在谁、是否 VIP
curl.exe -sS "https://api.ai24x.com/v1/billing/balance" `
  -H "Authorization: Bearer sk-此处粘贴完整Key"

# 期望（与控制台一致）：
#   "email":"lei@itxin.com"
#   "is_vip_active": true
#   "prepaid_tokens": > 0
#   "balance_tokens": 约 4000万级

# 2) 再点名
curl.exe -sS -w "\nHTTP:%{http_code}\n" -X POST "https://api.ai24x.com/v1/chat/completions" `
  -H "Authorization: Bearer sk-此处粘贴完整Key" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"vip-kimi\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":16}"
```

| balance 结果 | 含义 | 动作 |
|--------------|------|------|
| email ≠ lei@itxin.com | **Key 不是这个账号的** | 控制台 lei 账号里复制/新建 Key，勿用旧串 |
| is_vip_active=false | 该 Key 账号无有效 VIP | 查钱包 plan / vip_expires_at |
| is_vip_active=true 且仍 403 | 平台路由异常 | 回报完整 JSON + `git log -1`，转科设 |
| 接口 401 / 无 email 字段 | 生产未拉「余额支持 API Key」包 | 先 SQL 核对（下节）或拉码重启 |

> `/v1/billing/balance` 支持 API Key 的改动若未上生产，用下面 SQL。

## 生产库核对（副脑04）

```sql
-- A) 账号钱包（控制台那个人）
SELECT u.id, u.email, w.plan, w.vip_expires_at, w.balance_tokens
FROM auth_users u
JOIN token_wallets w ON w.auth_user_id = u.id
WHERE u.email = 'lei@itxin.com';

-- B) 调试 Key 前缀（例 sk-228fd…）绑在谁
SELECT k.id, k.key_prefix, k.is_active, k.auth_user_id, u.email
FROM api_keys k
JOIN auth_users u ON u.id = k.auth_user_id
WHERE k.key_prefix LIKE 'sk-228fd%'
   OR k.auth_user_id = (SELECT id FROM auth_users WHERE email='lei@itxin.com' LIMIT 1);
```

若 A 是 VIP，B 的 email 不是 lei → **换对 Key**，不是重建玄学权限。

## 给副脑03 / 飞书口径（勿再误导）

- ❌「充值前生成的 Key 没有 VIP，要重建才同步」——**错误**  
- ✅「用同一把 Key 打 `/v1/billing/balance`，看 email / is_vip_active 是否等于控制台」  
- 月卡 = 会员；开发包 = 预充。点名两者都要；当前控制台已具备时，盯 **Key↔账号**。

## 相关代码包（若需拉码）

见同日提交：`billing/balance` 接受 API Key；`vip_required` 返回 `code` 提示核对 Key。拉码后 **重启 AI24X-core**。
