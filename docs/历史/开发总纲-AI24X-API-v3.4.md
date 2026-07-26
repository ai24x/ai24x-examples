# AI24X API · 开发总纲（v3.4 · 副脑分工最终版）

> **版本**：v3.4 · 2026-07-25 23:05 · 主脑 AI24X永生
> **策略**：Phase 1 国内验证 → Phase 2 国际
> **协议**：短期 `X-API-Key` + `prompt`；Phase 2 再做 OpenAI 兼容

---

## 一、一句话定位

**AI24X — 统一接入中国高性价比模型的 API 网关（先国内验证，再服务国际开发者）。**

Phase 1 卖点：同一套 Key / 计费 / 路由，免费层体验接近 DeepSeek，靠平台额度与防刷控成本。
Phase 2 卖点：英文站 + 国际支付 + 海外节点。

---

## 二、分阶段市场

| 阶段 | 市场 | 支付 | 文档 | 目标 |
|------|------|------|------|------|
| **Phase 1（当前）** | 国内付费验证 | 微信/支付宝 + mock | 中文优先 | 有人付费、链路稳定、毛利可算 |
| **Phase 2** | 国际 | PayPal/Stripe | 英文首页+文档 | 海外注册/支付/延迟可接受 |

Phase 1 **不做**：❌ 全球最快最便宜 slogan、❌ 公共 Key 池、❌ 国际低延迟宣传

---

## 三、品牌与 SKU

| 对外档 | 现网计费 | 默认路由 | 说明 |
|--------|---------|---------|------|
| AI24X Free | `BillingPlan.FREE` | L1 DeepSeek → L0 硅基兜底 | 月赠 1 万 token · 日限 100 次 |
| AI24X Flash | 加油包 / FREE 路由 | L1 | 按量扣 token |
| AI24X Pro | `BillingPlan.VIP` | L1 → L2 → L3 | VIP 日赠额度 |
| AI24X Ultra | VIP + L3 | L1→L2→L3 | Phase 1 占位 |

协议：`X-API-Key: sk-…` + `{"prompt":"…","model":"auto"}`

---

## 四、商业模式（Phase 1）

```
注册 → 月赠 10,000 token · 日限 100 次
     → 用尽提示加油包 / VIP
     → 邀请双方各得奖励（已实现）
```

| 套餐 | 作用 |
|------|------|
| `token_pack_10k` / `100k` | 加油包到账 |
| `token_vip_month` / `50w` | VIP + 可选到账 |

国际美元价仅 Phase 2 草案。

---

## 五、已实现 vs 缺口

### ✅ 已实现（`api/` · PM2 `core-8000`）

- `/v1/keys` 创建/列表/删除
- `/v1/billing/*` + 微信/支付宝下单（`TOKEN_PAY_ENABLED` 默认关）
- `/v1/chat/run` 钱包扣费 + 路由
- `/v1/referrals/*` + `/v1/models`
- 控制台 / 登录注册 / 定价页
- 滑动限流 · 安全头 · 表隔离（`token_*`）

### ⬜ Phase 1 待办

1. DeepSeek Key 有效联调（等雷总换 Key）
2. FREE 日限 100 同步
3. model 别名 `flash|pro|ultra|auto`
4. 故障升档计费规则 + 日志
5. 成本/用量日报脚本
6. 邀请反作弊（P1）

### ⬜ Phase 2 待办

英文首页 · 邮箱验证 · PayPal · 副脑04 海外中转 · OpenAI 兼容 · Privacy Policy

---

## 六、技术架构

```
开发者 / 控制台 → api.ai24x / 本机 :8000（副脑01）
    → API Key + 钱包 + 限流
    → model_router：FREE=L1→L0 / VIP=L1→L2→L3
    → DeepSeek / SiliconFlow / VIP 扩展
```

升档计费：按最终成功层计费 · 全失败不扣费 · 禁止 FREE 偷用 VIP 层
缓存：仅 `/v1/models` 元数据 · 禁止缓存 chat 响应

---

## 七、副脑分工（v3.4 最终版）

| 副脑 | 配置 | 角色 | Phase 1 职责 | Phase 2 职责 |
|------|------|------|-------------|-------------|
| 01 | 4核8G | Token 核心 | API 网关 + 缓存 + 预发布 | 不变 |
| **02** | **2核8G** | **营销推广** | **中文文档 + 比价草稿 + 种子群运营** | **SEO 内容工厂总调度 + 30台PC** |
| 03 | 2核8G | 运维监控 | 公网服务 + 告警 + 止损（02同内网，可直连数据） | 不变 |
| 04 | 2核4G | 国际执行 | Phase 2 待命 | 英文 SEO + 社媒 + PayPal |

### 为什么副脑01 和 副脑02 不换位？
- 副脑01（4核8G）跑 API 网关+缓存刚好，拿去搞营销浪费
- 副脑02（2核8G）跑网关吃紧，但 8G 内存搞内容/营销绰绰有余
- 02 和 03 同内网是加分：直连生产数据写分析，给 03 做本地备份

### 30台机房电脑
后期归副脑02统调，按运营/内容/S EO/数据分组批量产出。

---

## 八、开发顺序

| 优先级 | 任务 | 状态 |
|--------|------|------|
| P0 | 总纲对齐 + SKU 映射 | ✅ 本文 |
| P0 | FREE 日限 100 + VIP 限额 | ⬜ |
| P0 | model 别名 flash/pro/ultra | ⬜ |
| P0 | DeepSeek 真 Key 联调 | ⚠ 等雷总 |
| P0 | 控制台验收 | ⬜ 晚间 21:00 |
| P1 | 成本日报 · 管理端毛利 · 邀请反作弊 | ⬜ |
| P2 | 英文站 · PayPal · 副脑04 · Privacy | ⬜ Phase 2 |

**不要再排入 Phase 1 的「从零实现 keys/billing」——已完成。**

---

## 九、晚间 21:00 自检

1. `/v1/models` → `l1_deepseek_ready`
2. 控制台创 Key → 试调 chat（期望 `provider=deepseek`）
3. 余额扣减 · mock 加油包
4. a1 `18001` 回归
5. `TOKEN_PAY_ENABLED` 保持 false

---

## 十、参考

| 文件 | 内容 |
|------|------|
| `开发任务-Token聚合MVP.md` | 接口细节 |
| `docs/DEEPSEEK-联调.md` | DeepSeek 联调 |
| `docs/TOKEN-PAY-RUNBOOK.md` | 支付隔离 |
| `api/main.py` / `model_router.py` / `token_mvp_service.py` | 实现 |
