# AI24X API · 开发总纲（v3.5 · 执行对齐版）

> **版本**：v3.5.2 · 2026-07-26 · 定价：国内外统一国际口径  
> **策略**：产品与售价对齐国际；国内仅测试场（不主攻国内开发者市场）  
> **协议**：`X-API-Key` + `prompt`；Phase 2 再做 OpenAI 兼容（`Bearer` + `messages`）

现行入口：本文件。旧版见 `docs/历史/`。

---

## 一、一句话定位

**AI24X — 中国高性价比模型的全球 API 入口（对标 OpenRouter 中国模型线：更好用，价格贴近或略高，整体性价比打得过）。**

---

## 二、市场与定价（2026-07-26 拍板）

| 项 | 口径 |
|----|------|
| **主力市场** | 国际开发者（USD · PayPal/Stripe） |
| **国内** | **仅测试/联调**；不主攻国内付费开发者（该人群会直连大厂） |
| **售价** | **国内外统一国际价表**（USD 锚定；CNY 按汇率展示） |
| **结算** | **国内站**：微信/支付宝 · **CNY** · 中文模板（体验测试为主）；**国际站**：PayPal 等 · **USD** · 国际站页面 |
| **对标** | OpenRouter 等中国模型聚合价 **+10%～25% 便利溢价**；相对 GPT/Claude 仍一个数量级以上更便宜 |
| **例外预留** | 若未来把**国外大模型优惠版引进国内**，再单开国内 SKU，不与中国模型国际价表混用 |

Phase 1 国内仍用微信/支付宝验支付与履约；价与权益按国际逻辑，不保留「超低价包 + 超大日赠」双轨。

| 阶段 | 支付 | 文档 | 说明 |
|------|------|------|------|
| **Phase 1** | 微信/支付宝（独立 notify）+ mock | 中文 | 测通链路；售价已按国际对齐 |
| **Phase 2** | + PayPal/Stripe | 英文为主 | 海外节点 + OpenAI 兼容 |
---

## 三、品牌与 SKU

| 对外档 | 计费侧 | 默认路由 | 限制 |
|--------|--------|----------|------|
| Free | `FREE` | L1 DeepSeek → L0 硅基 | 月赠 1 万 token；**日请求 100** |
| Flash | 加油包余额 | L1 | `model=flash` |
| Pro | `VIP` | L1→L2→L3 | `model=pro` |
| Ultra | VIP + L3 | L1→L2→L3 | `model=ultra`（占位） |

鉴权示例：

```bash
curl http://127.0.0.1:8000/v1/chat/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-..." \
  -d "{\"prompt\":\"你好\",\"model\":\"flash\"}"
```

---

## 四、副脑分工（摘要）

| 副脑 | 角色 | Phase 1 |
|------|------|---------|
| 01 | 增长/预发 | VPN 国际内容储备（不阻塞研发） |
| 02 | 国内运营 | 教程/社媒 |
| 03 | 运维+API | 公网、`core-8000`、告警 |
| 04 | 国际节点 | Phase 2：支付/CDN/英文 |

---

## 五、已实现 vs 缺口（2026-07-26）

### ✅ 已实现（`api/` · PM2 `core-8000`）

- `/v1/keys` · `/v1/billing/*` · `/v1/chat/run` 扣费 + 路由
- `/v1/referrals/*` · `/v1/models`
- FREE **日限 100** · 品牌别名 **flash|pro|ultra|auto**
- DeepSeek **v4-flash 真通**（`provider=deepseek`）
- QQ 邮箱 **SMTP** 验证码；测试邮箱 `*.ai24x.local` 走 local
- 邀请注册双方各 **+5000**；充值仍按比例返利
- mock 支付履约；真支付默认关（`TOKEN_PAY_ENABLED=false`）
- 烟测：`api/scripts_token_smoke.py`；日报：`api/scripts_token_daily_report.py`
- 控制台密钥卡片 / 邮箱注册（手机入口已停）

### ⬜ Phase 1 待办

1. Token **真支付**（独立 notify + 小额实付）— 需雷总配商户/公网回调
2. 飞书接日报（`FEISHU_WEBHOOK_URL`）
3. 副脑01 VPN / SEO 内容生产（运营轨，不阻塞代码）

### ✅ 近期补齐

- 邀请即时奖励反作弊：每邀请人 24h ≤30、每 IP 24h ≤8（仅限即时 +5000，不挡注册）

### ⬜ Phase 2

英文站 · PayPal · 海外节点 · OpenAI 兼容 · Privacy/ToS

---

## 六、技术要点

```
用户 → core-8000
  → API Key（哈希）+ 钱包 + 日限/滑动限流
  → model_router：FREE=L1→L0；VIP=L1→L2→L3
  → DeepSeek v4 / SiliconFlow / 扩展 stub
```

- 升档计费：按**最终成功层**；全上游失败落 stub **不扣费**
- 表隔离：`token_*` / 单号前缀 `T`；**不改 a1 履约**
- 缓存：仅公开元数据；禁止缓存 chat

---

## 七、开发与文档目录

```
docs/
  规划/   ← 总纲、产品规划（本文件）
  开发/   ← 接口任务、实现说明
  决策/   ← Cursor 协作、拍板记录
  联调/   ← DeepSeek / SMTP / 支付 / 安全
  历史/   ← 旧版总纲（只读）
  archive/← 更早过时材料
```

推送：`git push gitee master && git push origin master`（发版前由雷总确认）。

---

## 八、参考

| 路径 | 内容 |
|------|------|
| `docs/开发/开发任务-Token聚合MVP.md` | 接口与表设计 |
| `docs/决策/Cursor协作流程指南.md` | 日常开发流 |
| `docs/联调/DeepSeek联调.md` | DeepSeek |
| `docs/联调/邮箱验证码-SMTP联调.md` | SMTP |
| `docs/联调/TOKEN支付上线清单.md` | 真支付 |
| `memory/daily/2026-07-26.md` | 当日作战卡 |
| `api/main.py` / `model_router.py` / `token_mvp_service.py` | 实现 |
