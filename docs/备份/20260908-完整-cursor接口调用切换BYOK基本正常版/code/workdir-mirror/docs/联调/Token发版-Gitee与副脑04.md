# Token 发版：本机推 Gitee → 副脑04 正式国际生产（含新表）

> **现行口径（2026-08-04）**：`www.ai24x.com` + `api.ai24x.com`（Token 聚合）= **副脑04 正式国际站生产**。  
> **副脑03**：行情官 `a.ai24x.com` 生产；Token/www/api 仅作**冷备份/灾备**，日常发版**不要**默认捅 03。  
> 旧文：`Token发版-Gitee与副脑03.md`（已降级为备份说明）。

## 原则
- **勿改** a1 支付回调 / `p/a1/**` 履约逻辑（a1 仍由副脑03）
- **勿提交** `api/.env`、密钥、证书 PEM
- Token 新表由 `api` 启动时 `init_db()` → `Base.metadata.create_all` **自动建表**
- 生产 API 进程：**NSSM `AI24X-core`**（常见反代 `127.0.0.1:8002`；以 04 机实际为准）
- Gitee 两仓保持**私有**；对外开放前轮换令牌 → [`docs/规划/Gitee仓库私有与凭据习惯备注.md`](../规划/Gitee仓库私有与凭据习惯备注.md)

---

## `.env` 编辑红线（生产事故）

- **禁止**用 Cursor Write **整文件覆盖** `api/.env`
- **只改需要的行**：StrReplace / 记事本；改完确认 `DATABASE_URL` 无 `…`
- 详情：[`docs/联调/事故-Cursor写env密码被省略号替换.md`](./事故-Cursor写env密码被省略号替换.md)

## 本次会新增/依赖的表（国际 core 库）
| 表名 | 说明 |
|------|------|
| `token_wallets` | 钱包余额 / VIP |
| `billing_ledger` | 流水 |
| `api_keys` | 用户 API Key（哈希存） |
| `token_invite_codes` | 邀请码 |
| `token_referrals` | 推荐关系 |
| `token_pay_orders` | Token 支付订单（`T…` 单号） |

> 与 a1 的 `pay_orders` **隔离**。库名以**副脑04** `api/.env` 的 `DATABASE_URL` 为准（国际库）。

---

## A. 本机推送（雷总 / 主脑）

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
git commit -m "feat(token): ship to intl prod (brain-04)" -m "why: www+api live on SG; 03 is Token backup only"

git push gitee master
git push origin master

git log -1 --oneline --decorate
```

---

## B. 副脑04 更新指令（正式生产 · 可直接转发）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
git log -1 --oneline

# 若 requirements 有变
Set-Location C:\ai24x01\api
python -m pip install -r requirements.txt

# 新表：重启即可自动 create_all
Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
# 若仍用 pm2 名（少见）：pm2 restart core-api-8002 --update-env ; pm2 save
Start-Sleep -Seconds 3
Get-Service AI24X-core | Format-Table Name, Status
```

### 门禁（副脑04 回传）
```powershell
# 环回端口以现网 Nginx upstream 为准（常见 8002）
curl.exe -sS http://127.0.0.1:8002/health
curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
curl.exe -sS -o NUL -w "%{http_code}" https://api.ai24x.com/health
curl.exe -sS -o NUL -w "%{http_code}" https://www.ai24x.com/console.html
```

期望：环回 health 与公网 `api.ai24x.com/health` 均为 **200**。

### 生产 `api/.env` 必查（Token · 实付）
```
TOKEN_PAY_ENABLED=true
TOKEN_PAY_MOCK_ENABLED=false
TOKEN_WECHAT_NOTIFY_URL=https://api.ai24x.com/v1/billing/wechat/notify
TOKEN_ALIPAY_NOTIFY_URL=https://api.ai24x.com/v1/billing/alipay/notify
TOKEN_ALIPAY_RETURN_URL=https://www.ai24x.com/console.html
# + PayPal Live、OR/DS Key、SMTP_*、国际库 DATABASE_URL
```

改完 env 后：`Restart-Service AI24X-core`（或 `pm2 restart … --update-env`）。

---

## C. 回滚（副脑04）
```powershell
Set-Location C:\ai24x01
git log -5 --oneline
git checkout <上一稳定 commit>
Restart-Service AI24X-core
```

紧急关支付：`TOKEN_PAY_ENABLED=false` → 重启 core。

---

## D. 副脑03（Token 仅备份）

- **日常 Token / www / api 发版：不要默认更新 03。**
- 03 职责：`a.ai24x.com` 行情官 + 微信/支付宝。
- 若主脑明确要求「同步冷备」：可在 03 上 `git pull` + 重启其本地 core（**勿切 DNS**；勿把国际流量指回 03）。
- a1 发版仍走：`docs/副脑03-生产环境更新指南-a1…`

---

## E. 相关指令

- 试调用 JWT：`docs/联调/副脑04-更新指令-试调用JWT鉴权.md`
- 切流归档：`docs/联调/副脑04-迁移指令-www与api从03同构切流.md`
- 岗位总纲：`docs/规划/主脑副脑岗位与国际Token供给-1.0.md`
