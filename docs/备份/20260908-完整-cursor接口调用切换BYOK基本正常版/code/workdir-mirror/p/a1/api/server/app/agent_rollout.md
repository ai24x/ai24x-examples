# 三级推荐返佣（灰度上线与数据校验）

## 上线前（一次性）
- 确认数据库已执行自动迁移（服务启动时 `db.init_db()`）：
  - `invite_relations`：应包含 `inviter_l1_id`/`inviter_l2_id`/`inviter_l3_id`/`depth`/`updated_at`
  - `commission_ledger`：应包含 `level_depth` 且唯一约束为 `(out_trade_no, agent_user_id, level_depth)`
  - `agent_status`：应包含 `tier_points`/`tier_updated_at`/`tier_locked`

## 灰度开关（admin_config）
- **返佣开关**：`agent_commission_enabled=0/1`
- **比例**：
  - `agent_commission_rate_l1`（默认 0.20）
  - `agent_commission_rate_l2`（默认 0.05）
  - `agent_commission_rate_l3`（默认 0.02）
  - `agent_commission_rate_cap_total`（默认 0.30，超出会按比例缩放）
- **结算延迟**：`agent_settle_delay_days`（默认 7）
- **成长等级（可选）**：
  - `agent_tier_enabled=0/1`（默认 1）
  - `agent_tier_window_days`（默认 30）
  - `agent_tier_growth_team_gmv_fen`（默认 300000）
  - `agent_tier_growth_active_direct`（默认 3）
  - `agent_tier_pro_team_gmv_fen`（默认 2000000）
  - `agent_tier_pro_active_direct`（默认 10）

## 数据校验（上线当天）
### 1) 幂等与重复回调
- 同一 `out_trade_no` 重复回调/补单时：
  - 应最多新增 1~3 条 `commission_ledger`（按 depth），不会无限增长
  - 用管理员接口 `POST /api/admin/commissions/generate_for_order` 重跑应不报错

### 2) 账实一致（抽样 10~30 单）
- 在 `commission_ledger` 里按 `out_trade_no` 查询：
  - `amount_fen` 与 `pay_orders.amount_fen` 一致
  - `commission_fen ≈ round(amount_fen * rate)`（允许四舍五入差 1 分）
  - `level_depth` 为 1/2/3
- 用管理员页「代理与结算 → 代理与返佣」的 eligible 列表抽样核对。

### 3) 推荐链正确性（抽样 5 条链路）
- 在 `invite_relations` 中确认：
  - B 的 `inviter_l1_id` 是 A（直推）
  - 若 A 有邀请人 C，则 B 的 `inviter_l2_id` 是 C
  - 以此类推最多 3 层

## 回滚策略（最小可靠）
- 立即停止生成新返佣：把 `agent_commission_enabled=0`（不影响支付与 VIP 生效）
- 已生成的 `commission_ledger`：
  - 不建议删除（会破坏审计与提现流程）
  - 如需应急冻结提现：管理员将涉及代理的 `tier_locked=1` 并暂停「提现申请」审核

