# 副脑04 · 迁移指令（www + api 从 03 同构切流）

> 发令口径：2026-08-01 · **切流完成标注：2026-08-04**  
> **现行**：`www.ai24x.com` + `api.ai24x.com` → **副脑04（SG）正式生产**；`a.ai24x.com` **留副脑03**  
> **副脑03 Token**：仅冷备份，日常发版见 `docs/联调/Token发版-Gitee与副脑04.md`  
> **原则**：同构搬迁（同一 `master` / 同一套 NSSM+Nginx），**不重做业务**  
> **禁止**：整文件覆盖 `.env`；在 03 上养大批 PayPal Live 国际用户再整库搬；DNS 未验绿就切

岗位总纲：`docs/规划/主脑副脑岗位与国际Token供给-1.0.md`（v1.0.6）  
过渡备注：`docs/规划/国际站PayPal与副脑04过渡备注.md`

---

## 0. 一句话

**DNS 已切：04 = 正式 www/api；03 只留行情官 + Token 冷备。** 下文为切流操作档案，新发版勿再按「迁机」执行。

---

## 1. 迁什么 / 不迁什么

| 迁到 04 | 留在 03 |
|---------|---------|
| `web/` 主站静态（Nginx 直出） | `a.ai24x.com` + `p/a1`（行情官） |
| `api/` Token（NSSM `AI24X-core` → 8002） | 微信 / 支付宝商户与 a1 回调 |
| PayPal（目标 Live）、国际库 | 国内支付相关进程 |
| OR / DeepSeek / 硅基等 Token 上游 Key | — |

不要把行情官整站搬到 04。

---

## 2. 最快路径（四段，可并行准备）

```
A 04 空机就绪（代码+依赖+空库+Nginx+证书）
    → B 从 03 抽配置清单 +（可选）库备份还原到国际库
        → C 04 环回验收绿（仍指旧 DNS）
            → D DNS 切 www/api → 04，再公网验收；03 摘 www/api
```

预计熟练机：**半日～1 日**（卡点通常是 DNS/证书/PayPal Webhook URL，不是代码）。

---

## 3. 段 A · 副脑04 空机就绪（DNS 未切）

在 **副脑04** PowerShell：

```powershell
# 1) 代码
Set-Location C:\
if (-not (Test-Path C:\ai24x01)) {
  git clone https://gitee.com/ai24x/ai24x-website.git ai24x01
}
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline

# 2) Python 依赖（与 03 同口径）
Set-Location C:\ai24x01\api
python -m pip install -r requirements.txt

# 3) 建国际库（例名，以实际为准）
# 用 pgAdmin / psql 建库 ai24x_core_intl（或你们约定名）
# 再按 api 现有建表/启动自建表逻辑起服务（与 03 一致即可）

# 4) 写本地 api\.env（记事本行级；禁止 Cursor Write 整文件）
# 从 03 抄「键清单」，值按国际库/国际回调改（见下节）

# 5) NSSM 注册 AI24X-core → 127.0.0.1:8002（与 03 同）
# Nginx：www 静态 → C:\ai24x01\web ； /v1 等反代 → 8002
# 先自签或临时证书；正式证书可在 DNS 切前用 DNS 验证申请

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 5
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }
```

---

## 4. 段 B · 从 03 带走的「配置清单」（行级）

在 **副脑03** 只导出**键名是否存在**（不要把密钥贴飞书）。04 上对照填写。

### 必拷（Token / 登录 / 支付）

| 类别 | 典型键 |
|------|--------|
| 库 | `DATABASE_URL` → **指向国际新库**（勿直连 03 国内库长期双写） |
| 鉴权 | `JWT_*` / `SMS_INTERNAL_KEY` / 邮件 SMTP |
| LLM | `TOKEN_LLM_UPSTREAM`、`OPENROUTER_*`、`DEEPSEEK_*`、`SILICONFLOW_*`、`TOKEN_LLM_DS_FAILOVER` |
| PayPal | `TOKEN_PAY_ENABLED`、`PAYPAL_*`、`TOKEN_PAYPAL_RETURN_URL`、`TOKEN_PAYPAL_CANCEL_URL` |
| 回调 | Return/Cancel/Webhook 一律改成 **https://www.ai24x.com / https://api.ai24x.com**（切 DNS 后生效） |
| 开关 | 与 03 当前绿配置对齐（支付开、mock 关等） |

### 数据怎么迁（选一）

| 方案 | 适用 | 做法 |
|------|------|------|
| **A 空库冷启动（最快）** | 国际用户尚少、可接受重新注册 | 04 空库上线；03 Token 库归档只读 |
| **B 一次性 pg_dump** | 要带走已有 Token 用户/余额 | 维护窗：03 `pg_dump` → 04 `pg_restore` → 切 DNS；迁后 03 停写 www/api |
| **C 双写过渡** | 高可用要求 | **本阶段不做**（一人公司成本过高） |

拍板建议：**国际用户少 → 选 A**；已有付费余额必须连续 → 选 B（短维护窗）。

### 03 导出备份示例（方案 B）

```powershell
# 副脑03：仅示例；库名以 api\.env 的 DATABASE_URL 为准
# pg_dump -Fc -f C:\backup\ai24x_core_cn_YYYYMMDD.dump <库名>
```

```powershell
# 副脑04：
# pg_restore -d ai24x_core_intl --clean --if-exists C:\backup\ai24x_core_cn_YYYYMMDD.dump
```

---

## 5. 段 C · 04 环回验收（DNS 仍指 03）

在 04 本机：

1. `8002/health` = 200  
2. 管理台密钥表可见 DeepSeek + planned（内部 Key 调 `GET /v1/admin/token/llm_keys`）  
3. hosts 临时把 `www`/`api` 指到 **04 公网 IP**，本机浏览器：  
   - 打开首页 / 登录 / 控制台  
   - PayPal Sandbox 或小额 Live（按主脑批准）  
4. 确认 **不依赖** 03 行情官进程

绿了再进入段 D。

---

## 6. 段 D · DNS 切流（最短维护窗）

1. **DNS**：`www`、`api` A/AAAA → **副脑04 IP**（TTL 先降到 60～300）  
2. **PayPal 后台**：Webhook / Return URL 确认已是 04 域名（与 `.env` 一致）  
3. **证书**：04 Nginx 正式证书生效  
4. 公网验收：

```text
https://api.ai24x.com/health
https://www.ai24x.com/
https://www.ai24x.com/token-admin.html   # Ctrl+F5
登录 → 控制台 →（可选）PayPal 小额
```

5. **副脑03 收口**（切流稳定 30～60 分钟后）：  
   - 停掉仅服务 `www`/`api` 的 Nginx server / 或摘监听（**不要停** `a.ai24x.com` / a1）  
   - 保留 `C:\ai24x01` 代码便于回滚对照；Token 库可只读归档  

### 回滚（5 分钟）

DNS `www`/`api` 指回 **03 IP** → 等 TTL → 公网 health；04 服务可留着不删。

---

## 7. 发给副脑03 / 副脑04 的口令（可转发）

### → 副脑03（运维CN）

- 继续保 `a.ai24x.com` 绿；**不要**在切流窗改国内支付商户。  
- 主脑下令时：按方案做 `pg_dump`（若选 B）；切流后停 www/api 写入。  
- 汇报：a 站 health + 行情官一页截图即可。

### → 副脑04（运维SG）

- 执行本文 **段 A→C**；环回绿后等主脑 **段 D DNS**。  
- `.env` 只行级改；进程 **NSSM `AI24X-core`**（勿 pm2 启停 core）。  
- 汇报：`git log -1`、`8002/health`、hosts 自测登录结果、PayPal ready 布尔值。

---

## 8. 不要做

- 不要指望「只 git pull」就算迁移完成（还差库、DNS、证书、PayPal URL）  
- 不要把 03 的 `DATABASE_URL` 长期指到 04（或反过来双写）  
- 不要迁完才发现 Webhook 仍指向旧机  
- 不要把微信 Native 回调改到 04（继续 a1 / 03）  
