# Cursor 开发任务 · Token API 三接口补齐

> 目标：完成 Token 聚合平台 MVP 闭环
> 项目目录：`E:\AI24X\ai24x-website\ai24x01\api\`
> 当前状态：auth + chat/run 已实现，keys/billing/referrals 返回 501

---

## 一、API Keys 管理（`/v1/keys`）

**当前状态**：501 Not Implemented

**要做：**
```
GET  /v1/keys          → 列出当前用户的 API Key 列表
POST /v1/keys          → 创建新 API Key（含名称备注）
DELETE /v1/keys/{id}   → 删除指定 API Key
```

**数据模型**（`models.py` 或新建）：
```python
{
  id: string (uuid),
  user_id: string (auth_users.id),
  name: string ("默认密钥"),
  key: string ("sk-" + uuid),
  created_at: datetime,
  last_used_at: datetime?,
  is_active: bool
}
```

---

## 二、计费系统（`/v1/billing`）

**当前状态**：501 Not Implemented

**要做：**
```
GET  /v1/billing/balance    → 查询余额（token 数）
POST /v1/billing/topup      → 充值（兑换码/人工确认后手动加）
GET  /v1/billing/usage      → 查询用量记录（按天/模型汇总）
```

**计费逻辑**：
- 免费用户：每月赠送 10000 token
- VIP 用户：按套餐月付 ¥19.9（约 140M token 用量）
- 扣费：每次 chat/run 请求后，根据 model + token 数扣减余额
- 余额不足 → 返回 402 Payment Required

---

## 三、推荐返利（`/v1/referrals`）

**当前状态**：501 Not Implemented

**要做：**
```
GET  /v1/referrals/code     → 获取我的邀请码/链接
GET  /v1/referrals/stats    → 邀请统计（邀请人数、返利金额）
GET  /v1/referrals/earnings → 返利明细列表
```

**返利规则**：
- 二级返利：一级 10%，二级 2%
- 被邀请人首次充值后返利生效
- 返利金额可提现或抵扣 API 费用

---

## 实现提示

1. 参考 `auth_users` 表的模式，用 PostgreSQL 建新表
2. API Key 生成用 `uuid.uuid4().hex` 前缀 `sk-`
3. 计费先用 SQLite 或内存模式，MVP 验证后再切 PG
4. 所有接口需鉴权（Bearer token / JWT）
5. Nginx 同域反向代理配置见 `docs/AI行情官-Nginx同域反向代理模板-a1-a-a4.md`
