# AI24X API · 开发总纲（v3.3 · A+C 执行版）

> 基于 v3.2 科审结论修订。策略：**Phase 1 国内验证 → Phase 2 国际**；协议：**短期保持 `X-API-Key` + `prompt`**。  
> 本文替代「按 v3.2 从零重做 501」的误解；**已实现能力标 ✅，缺口标待办**。

---

## 一、一句话定位

**AI24X — 统一接入中国高性价比模型的 API 网关（先国内验证，再服务国际开发者）。**

Phase 1 卖点：同一套 Key / 计费 / 路由，免费层体验接近 DeepSeek，靠平台额度与防刷控成本。  
Phase 2 卖点：英文站 + 国际支付 + 海外节点，解决手机号 / 中文文档 / 微信支付宝障碍。

---

## 二、分阶段市场（强制）

| 阶段 | 市场 | 支付 | 文档语言 | 目标 |
|------|------|------|----------|------|
| **Phase 1（当前）** | 国内付费验证 | 微信/支付宝（Token 独立回调）+ mock | 中文优先 | 有人付费、链路稳定、毛利可算 |
| **Phase 2** | 国际 | PayPal/Stripe | 英文首页+文档 | 海外注册/支付/延迟可接受 |

**不做的承诺（Phase 1）**
- ❌ 宣称「全球最快最便宜 / 500 倍碾压」为主 slogan  
- ❌ 用户自带 Key 入公共池  
- ❌ 未上海外节点前宣传「国际低延迟」  
- ❌ 设备指纹作为国际 P0（合规未就绪）

---

## 三、品牌与 SKU（映射现网）

对外逻辑名默认用品牌档；底层可不对普通用户强调。

| 对外档 | 计费侧（现网） | 默认路由链 | 说明 |
|--------|----------------|------------|------|
| AI24X Free | `BillingPlan.FREE` | L1 DeepSeek → L0 硅基兜底 | 月赠 1 万 token；**日请求上限 100** |
| AI24X Flash | 加油包余额 / 同 FREE 路由 | L1 | 按量扣 token（加油包） |
| AI24X Pro | `BillingPlan.VIP` | L1 → L2 → L3 | VIP 日赠额度；增强模型 |
| AI24X Ultra | VIP + 显式选 L3 | L1→L2→L3（可指定 kimi 等） | Phase 1 先占位，L3 未配 Key 则 stub/失败 |

**协议（A+C）**
- 鉴权：`X-API-Key: sk-…`（创建时明文只显示一次，库内哈希）
- 请求体：`{"prompt":"…","model":"auto"}`  
- Phase 2 再做 OpenAI 兼容：`Authorization: Bearer` + `messages[]`

**高级用户切换底层**：Phase 1 控制台可选 `auto|deepseek-chat|siliconflow-free|…`；不单独做复杂 Dashboard 引擎页。

---

## 四、商业模式（Phase 1）

```
注册 →（可选邀请码）→ 月赠 10,000 token
     → 日上限 100 次请求（防刷）
     → 额度用尽提示加油包 / VIP
     → 邀请双方各得奖励 token（已实现，防刷后续加强）
```

| 套餐 plan_id | 作用 |
|--------------|------|
| `token_pack_10k` / `token_pack_100k` | 加油包到账 |
| `token_vip_month` / `token_vip_month_50w` | VIP + 可选到账 |

国际美元价（$0.03/M 等）仅作 Phase 2 定价草案，**不作为 Phase 1 计费真相**。

---

## 五、已实现 vs 缺口

### ✅ 已实现（根目录 `api/`，PM2 `core-8000`）

- `/v1/keys` 创建/列表/删除（哈希存储）
- `/v1/billing/balance|usage|topup|plans|orders` + 微信/支付宝下单与 notify（`TOKEN_PAY_ENABLED` 默认关）
- `/v1/chat/run` 接钱包扣费 + 路由
- `/v1/referrals/*` 邀请码与奖励
- `/v1/models` 就绪状态
- 控制台 / 登录注册 / 定价页（本机）
- 滑动限流、安全头、溯源字段、`STRICT_AUTH`
- 表隔离：`token_*` / 单号前缀 `T`（不写 a1 `pay_orders`）

### ⬜ Phase 1 待办（本周优先）

1. DeepSeek Key **有效**并端到端 `provider=deepseek`（人工换 Key）
2. FREE **日请求 100** 与文档一致（网关用户同步限额）
3. 品牌 model 别名：`flash|pro|ultra|auto`
4. 故障升档计费规则写清并打日志（`route_attempts`）
5. 成本/用量日报草稿（可先本地脚本，飞书后接）
6. 邀请反作弊（同 IP/同设备，P1）

### ⬜ Phase 2 待办

- 英文首页 + 英文 API 文档
- 邮箱确认注册
- PayPal/Stripe
- 副脑04 海外中转
- OpenAI 兼容层
- 隐私政策 / ToS
- 状态页 + SLA 文案

---

## 六、技术架构（Phase 1）

```
开发者 / 控制台
    → api.ai24x / 本机 :8000（副脑01）
    → API Key + 钱包扣费 + 滑动限流
    → model_router：FREE=L1→L0；VIP=L1→L2→L3
    → DeepSeek / SiliconFlow /（VIP 扩展 stub）
```

**缓存**：仅缓存公开 `/v1/models` 类元数据（短 TTL）；**禁止**缓存 chat 响应按用户串用。

**升档计费（约定）**
- 同请求内 fallback 到下一层：按**最终成功层**的 `LAYER_COST_MULT` 计费
- 全失败：不扣成功费（可记 0 或最小探测费——MVP **不扣费**）
- 禁止静默把 FREE 升到 VIP 专属层且按 FREE 价

**版本**：`/v1/` 稳定；破坏性变更走 `/v2/`，旧版至少维护 6 个月。

---

## 七、开发顺序（执行表）

| 优先级 | 任务 | 状态 |
|--------|------|------|
| P0 | 总纲对齐 A+C + SKU 映射 | 本文 |
| P0 | FREE 日限 100 + 同步 VIP 限额 | 代码 |
| P0 | model 别名 flash/pro/ultra | 代码 |
| P0 | DeepSeek 真 Key 联调 | **等雷总换有效 Key** |
| P0 | 控制台试调 + mock 支付闭环验收 | 晚间 21:00 |
| P1 | 用量/成本日报脚本 | 待 |
| P1 | 管理端毛利视图增强 | 待 |
| P1 | 邀请反作弊 | 待 |
| P2 | 英文站 / PayPal / 海外节点 / OpenAI 兼容 | Phase 2 |

**不要再排进 Phase 1 的「从零实现 keys/billing」**——已完成，只做验收与补洞。

---

## 八、副脑与发布

| 副脑 | Phase 1 职责 |
|------|----------------|
| 01 | Token 核心、预发 |
| 03 | 公网、告警、止损 |
| 02/04 | 内容与国际 → **Phase 2 再重投入** |

推送：`git push gitee master && git push origin master`（发版前由雷总确认）。

**安全边界**：不改 `p/a1/**` 履约；不改 a1 支付 notify 指向 Token。

---

## 九、晚间 21:00 自检（雷总）

1. `http://127.0.0.1:8000/v1/models` → `upstream.l1_deepseek_ready` / `mode`
2. 登录控制台 → 创建 Key → 试调 chat（期望 `provider=deepseek`，否则看 Key）
3. 余额扣减；mock 加油包到账
4. a1 首页 `18001` 仍正常（回归）
5. `TOKEN_PAY_ENABLED` 生产保持 false，直至独立 notify URL 配好

---

## 十、参考

| 文件 | 内容 |
|------|------|
| `开发任务-Token聚合MVP.md` | 接口细节 |
| `docs/DEEPSEEK-联调.md` | DeepSeek 联调 |
| `docs/TOKEN-PAY-RUNBOOK.md` | 支付与隔离 |
| `docs/SECURITY.md` | 安全基线 |
| `api/main.py` / `model_router.py` / `token_mvp_service.py` | 实现 |
