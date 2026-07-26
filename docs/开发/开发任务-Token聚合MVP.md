> **状态（2026-07-26）**：keys / billing / chat 计费 / referrals / models / FREE 日限 100 / flash·pro·ultra / DeepSeek v4 / SMTP **已完成**。  
> **下一项**：Token 真支付（独立 notify）。总纲见 `docs/规划/开发总纲-AI24X-API-v3.5.md`。  
> 本文保留接口与 SQL 设计原文，实现以代码为准。

你是一个专业的 AI 编程助手。以下是你的任务。

---

## 使命

开发 **Token 聚合平台 MVP** — 国内中小开发者的一站式多模型 API 聚合平台。

**一句话**：把 DeepSeek、Kimi、智谱、豆包等国产模型的 API 统一到「一个入口、一套密钥、一个计费体系」。

**项目根目录**：`E:\AI24X\ai24x-website\ai24x01`

---

## 知识背景

### 现有完成的功能

| 模块 | 状态 | 代码位置 |
|------|------|---------|
| 用户注册/登录 | ✅ 已完成 | `api/main.py` `/v1/auth/*` |
| JWT 鉴权 | ✅ 已完成 | `api/auth_user_service.py` |
| 核心调用 /v1/chat/run | ✅ 已完成 | `api/main.py` |
| 前端页面 | ✅ 已完成 | `web/` |
| PostgreSQL 数据库 | ✅ 已运行 | `db/schema.sql` |
| 配置管理 | ✅ 已完成 | `api/config.py` |
| PM2 进程管理 | ✅ 已配置 | 本地 8000 / 生产 8002 |

### 模型路由策略（接入 MVP 后实现）

```
L0 免费引流层 → GLM-4-Flash(¥0) / SiliconFlow(低价)
L1 白菜主力层 → DeepSeek Flash (¥0.14/0.28 M token)
L2 VIP 增强层 → DeepSeek Pro (¥1.74/3.48)
L3 扩展层 → Kimi K3 / MiniMax / 通义 / 豆包 Pro
```

FREE/VIP 各有独立 fallback 链，逐级 3-5 秒超时。

---

## 你要做的：补完三个 501 接口

当前 `/v1/keys`、`/v1/billing`、`/v1/referrals` 返回 501 Not Implemented。
请在 `api/main.py` 中补完它们。

### ① API Keys 管理

```
GET  /v1/keys           → 当前用户 Key 列表
POST /v1/keys           → 创建新 Key（传 name）
DELETE /v1/keys/{id}    → 删除指定 Key
```

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth_users(id),
    name VARCHAR(64) NOT NULL DEFAULT '默认密钥',
    key VARCHAR(128) UNIQUE NOT NULL,        -- sk- + uuid
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

### ② 计费系统

```
GET  /v1/billing/balance   → 余额
POST /v1/billing/topup     → 充值（内部接口）
GET  /v1/billing/usage     → 用量明细
```

计费逻辑：
- 免费用户：每月赠 10,000 token，超限返回 429
- VIP 用户：¥19.9/月 ≈ 500,000 token/天
- 扣费：/v1/chat/run 响应后按实际 token + model 扣减
- 余额不足 → 402

```sql
CREATE TABLE billing_records (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth_users(id),
    type VARCHAR(16) NOT NULL,         -- consume / topup / bonus
    amount INTEGER NOT NULL,           -- 正=充值 负=消耗
    model VARCHAR(32),
    tokens INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### ③ 推荐返利

```
GET  /v1/referrals/code       → 我的邀请码
GET  /v1/referrals/stats      → 邀请数据
GET  /v1/referrals/earnings   → 返利明细
```

规则：一级 10%、二级 2%，被邀请人首次充值后生效。

```sql
CREATE TABLE referrals (
    id UUID PRIMARY KEY,
    referrer_id UUID NOT NULL REFERENCES auth_users(id),
    referee_id UUID NOT NULL REFERENCES auth_users(id),
    level INTEGER DEFAULT 1,
    reward INTEGER NOT NULL,
    status VARCHAR(16) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 开发顺序

1. **P0 先做** `/v1/keys`（2-4 小时）
2. **P0** chat/run 接入计费扣减（3-5 小时）
3. **P0** `/v1/billing` 余额 + 充值（4-6 小时）
4. P1 用量查询
5. P2 `/v1/referrals`

---

## 重要参考文件

| 文件 | 路径 |
|------|------|
| 主程序 | `api/main.py` |
| 数据模型 | `api/models.py` |
| Pydantic Schema | `api/schemas.py` |
| 业务逻辑 | `api/services.py` |
| 数据库连接 | `api/database.py` |
| 数据库 DDL | `db/schema.sql` |
| 配置 | `api/config.py` |
| 环境变量 | `api/.env` |

---

## 你可以优化和改动的权力

你是专业的 AI 编程工具。以下问题由你自主决定：

- 表结构是否可以复用已有表？可以
- 是否用 Pydantic 模型做校验？必须用（项目已引入）
- 鉴权直接用已有的 JWT 中间件？是的
- 计费用 SQLite 还是 PostgreSQL？MVP 可先用 SQLite 或项目已有的 PG
- 路由是否可以更合理？可以优化，改完在 main.py 注册即可
- 是否需要新建 services 文件？需要的话新建
- 是否需要改 models.py / schemas.py？需要就改

**原则**：变更好即可，无需拘泥于我的 SQL 示例。

---

## 每完成一步

在终端输出：
```
✅ ?? /v1/keys 完成  
下一步: ?? chat/run 接入计费  
```

然后继续下一步。

不要停下来问「可以吗」，直接开发，有问题自己决定。你是专业编程AI，我相信你的判断。开始吧。
