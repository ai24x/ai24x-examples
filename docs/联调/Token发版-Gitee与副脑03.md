# Token 发版：本机推 Gitee → 副脑03 更新（含新表）

## 原则
- **勿改** a1 支付回调 / `p/a1/**` 履约逻辑
- **勿提交** `api/.env`、密钥、证书 PEM
- Token 新表由 `api` 启动时 `init_db()` → `Base.metadata.create_all` **自动建表**（无需手写 SQL；软迁移含 `token_wallets.vip_expires_at`）
- 生产 API 进程：**`core-api-8002`**（`api.ai24x.com` → `127.0.0.1:8002`）
- Gitee 两仓保持**私有**；本机 remote 暂嵌令牌仅为便利。**主站对外开放推广前**须轮换令牌并拆掉 URL 内嵌凭据 → 见 [`docs/规划/Gitee仓库私有与凭据习惯备注.md`](../规划/Gitee仓库私有与凭据习惯备注.md)

---

## 对外开放推广前闸门（提醒）

正式获客 / 投放 / 公开注册推广之前，先完成规划备注第三节（确认私有 → 作废旧令牌 → remote 无密钥 → 凭据管理器或 SSH）。日常种子期可继续现用双推流程。

## 本次会新增/依赖的表（core 库）
| 表名 | 说明 |
|------|------|
| `token_wallets` | 钱包余额 / VIP |
| `billing_ledger` | 流水 |
| `api_keys` | 用户 API Key（哈希存） |
| `token_invite_codes` | 邀请码 |
| `token_referrals` | 推荐关系 |
| `token_pay_orders` | Token 支付订单（`T…` 单号） |

> 与 a1 的 `pay_orders` **隔离**。库名以副脑03 `api/.env` 的 `DATABASE_URL` 为准（常见 `ai24x_core_cn` 或与预演对齐的库）。

---

## A. 本机推送（雷总 / 主脑）

PowerShell（不要用 `&&`）：

```powershell
Set-Location E:\AI24X\ai24x-website\ai24x01

git status
git branch --show-current
git remote -v
git checkout master
git pull origin master

# 只加 Token / 主站相关，勿把无关 a1 脏改带上
git add api/ web/ docs/联调/ docs/规划/ docs/开发/ docs/决策/ memory/daily/

git status
git commit -m "feat(token): MVP billing pay console email invite" -m "why: ship Token platform to prod core-api-8002"

git push gitee master
git push origin master

git log -1 --oneline --decorate
```

---

## B. 副脑03 更新指令（可直接转发）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
git log -1 --oneline

# 若 requirements 有变（首次 Token 上线建议做一次）
Set-Location C:\ai24x01\api
python -m pip install -r requirements.txt

# 新表：重启即可自动 create_all（无需单独 migration 脚本）
Set-Location C:\ai24x01
pm2 restart core-api-8002 --update-env
pm2 save
pm2 list
```

### 门禁（副脑03 回传）
```powershell
curl.exe -sS http://127.0.0.1:8002/health
curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
curl.exe -sS -o NUL -w "%{http_code}" https://api.ai24x.com/health
curl.exe -sS -o NUL -w "%{http_code}" https://www.ai24x.com/console.html
```

期望：本机 `8002/health` 与公网 `api.ai24x.com/health` 均为 **200**（若公网 **502**，多半是 `core-api-8002` 未起来或 Nginx 反代指错端口）。

官网注册若出现英文 `Failed to fetch`：通常是浏览器跨域看到 Nginx 502 无 CORS，本质仍是 **API 502**，先修上游再测注册。

### 生产 `api/.env` 必查（Token · 实付联调）
```
TOKEN_PAY_ENABLED=true
TOKEN_PAY_MOCK_ENABLED=false
TOKEN_WECHAT_NOTIFY_URL=https://api.ai24x.com/v1/billing/wechat/notify
TOKEN_ALIPAY_NOTIFY_URL=https://api.ai24x.com/v1/billing/alipay/notify
TOKEN_ALIPAY_RETURN_URL=https://www.ai24x.com/console.html
# + WECHAT_* / ALIPAY_* 商户凭证、DEEPSEEK_API_KEY、SMTP_*
```

说明：
- **实付阶段务必 `TOKEN_PAY_MOCK_ENABLED=false`**：控制台不显示「模拟到账」，接口 `mock_fulfill` 返回 403
- **保留「确认到账」**：真支付回调延迟/丢失时的查单补履约（不是模拟）
- 本机开发可另开 `TOKEN_PAY_MOCK_ENABLED=true`（或关真支付 + local 环境自动允许 mock）

改完 env 后：`pm2 restart core-api-8002 --update-env`

### 实付门禁（`pay/status`）
```powershell
curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
```
期望 JSON 中大致：
- `"enabled": true`
- `"mock_allowed": false`
- `"wechat_ready"` / `"alipay_ready"` 至少一个为 `true`（商户齐）

### 商户平台（一次性）
- 微信 / 支付宝 **增加** Token 上述 notify（**保留** a1 原回调不动）

### 可选：确认新表已建
```powershell
# 按实际库名/账号替换
psql -h 127.0.0.1 -U <user> -d <core_db> -c "\dt token*"
psql -h 127.0.0.1 -U <user> -d <core_db> -c "\d token_pay_orders"
```

---

## C. 回滚（副脑03）
```powershell
Set-Location C:\ai24x01
git log -5 --oneline
git checkout <上一稳定 commit>
pm2 restart core-api-8002 --update-env
pm2 save
```
- 表已建一般可保留（空表无害）；勿回滚时 drop a1 表
- 紧急关支付：`TOKEN_PAY_ENABLED=false` → `pm2 restart core-api-8002 --update-env`

---

## D. 与 a1 更新的关系
- **纯 Token 发版**：只重启 `core-api-8002`，**不要**顺手改 a1 notify
- 若同日也发 a1：再按 `docs/副脑03-生产环境更新指南-a1…` 另走 `a-api-8001` + a1 库备份
