# AI24X 网站 SEO 优化设计（自然引流为主 · 付费为辅）

> **版本**：1.0 · 2026-07-31  
> **策略**：后期主打 **SEO 自然引流**；履约与内容稳住后 **逐步** 做付费推广（Google/Bing Ads 等）。  
> **叙事唯一**：国外开发者痛点 × 中国模型极致性价比（Kimi / MiMo / MiniMax / 智谱 GLM / DeepSeek / Qwen…）。  
> **对齐**：`SEO引流核心与规划-1.0.md` · 统一优化批次（文案 / VIP 点名 / Integrations / AI Help）

---

## 0. 现状结论（主站 `web/`）

| 项 | 现状 | 风险 |
|----|------|------|
| `robots.txt` / `sitemap.xml` | **主站缺失**（仅行情官 a1 有） | 抓取与发现弱 |
| Title / Description | 写死在 HTML，偏中文泛聚合 | 英文意图难排；与主叙事不符 |
| 国际化 | `localStorage` 切语言，默认偏 zh | 搜索引擎常只看到中文壳 |
| canonical / hreflang | 基本无 | 中英重复、国际站信号弱 |
| OG / Twitter Card | 基本无 | 社媒分享弱 |
| 名模落地页 | 无 | 高热词（Kimi/MiMo…）无处承接 |
| noindex | admin/console 部分已做 | 保持；paypal 指南可改为 index（有搜索意图） |

**设计目标**：先把「可被抓、意图准、名模有页、英文可索引」做实，再谈投放。

---

## 1. 总原则

1. **自然流量优先**：90 日重心 = 技术 SEO + 名模/痛点内容；付费只做小预算验证，不烧在未转化页上。  
2. **一页一主意图**：禁止首页堆所有名模关键词。  
3. **英文为国际索引主语言**：国际生产默认 `en`；中文站/行情官词表隔离。  
4. **可索引 HTML**：关键 SEO 文案不能只靠 JS 写入；title/description/H1 服务端或构建时按语言输出（见 §3）。  
5. **履约门禁**：PayPal/API 不稳不做付费；自然流也可控量（先长尾再品牌）。

---

## 2. 信息架构（URL 设计）

```
/                     首页 · 主意图：China LLM API · value · PayPal
/pricing              定价 · credits / VIP
/product              产品能力（短）
/docs                 Quickstart 总览
/docs/errors          错误码 FAQ（401/402/429…）
/guides/              接入案例索引（Integrations）
/guides/openclaw
/guides/openai-sdk
/models/              名模中心索引（SEO 粮仓）
/models/deepseek
/models/kimi
/models/xiaomi-mimo
/models/minimax
/models/zhipu-glm
/models/qwen
/blog/ 或 /learn/     可选：对比文、性价比长文（P1）
/register · /login    转化；register 可 index，login noindex 可选
```

**规则**

- `/models/{slug}`：每页主攻 **一个厂牌词簇**（见名模词表 §3.1.1）。  
- 对外不暴露上游运维名；可写「via AI24X credits / named model on VIP」。  
- 行情官 **不进** `www` 名模 IA；用 `a.ai24x.com` 独立 sitemap。

静态站落地方式（与现架构兼容）：

- 短期：`web/models/kimi.html` 等真实文件（UTF-8），进 sitemap。  
- 中期：同模板生成；或轻量 SSG。勿只做 hash 路由 SPA。

---

## 3. 技术 SEO 清单（P0 必须）

### 3.1 抓取与发现

| 交付 | 说明 |
|------|------|
| `https://www.ai24x.com/robots.txt` | Allow 营销/docs/models/guides；Disallow `/token-admin` `/console` `/account` `/ai24x.html` `/command-center` 等 |
| `sitemap.xml` + 可选 `sitemap-models.xml` | 只列 **indexable** URL；提交 Google Search Console + Bing Webmaster |
| 404 页 | 已有则保持软文链回首页/models |

### 3.2 国际与语言

| 方案 | 推荐 |
|------|------|
| **A（推荐）** | 国际默认英文 HTML：`lang="en"`；关键页提供 `/zh/` 镜像或 `?lang=zh` **且** 服务端/静态双份 meta；`hreflang` en/zh/x-default |
| **B（过渡）** | 单 URL + JS i18n：至少用 **爬虫可见的英文** 写死 title/description/H1（中文用户进站再切）；Search Console 验证抓取 |

> 现有「默认 zh + JS 换 en」对 SEO **不友好**。统一优化批次应改为：**www 国际站默认 en**（与副脑04/01 口径一致）。

### 3.3 每页 On-page 模板

```html
<title>{主词} · AI24X</title>          <!-- ≤60 字符级 -->
<meta name="description" content="..."> <!-- 痛点+性价比+CTA，≤155 -->
<link rel="canonical" href="https://www.ai24x.com/...">
<link rel="alternate" hreflang="en" href="...">
<link rel="alternate" hreflang="zh" href="...">  <!-- 若有 -->
<meta property="og:title" ...>
<meta property="og:description" ...>
<meta property="og:url" ...>
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
```

**首页示例意图（英文）**

- Title: `China LLM API · DeepSeek Kimi MiMo · PayPal | AI24X`  
- Desc: `Call top China models with one key and USD credits. Extreme value vs GPT. OpenClaw & OpenAI-compatible guides.`

**名模页示例（Kimi）**

- Title: `Kimi API · Affordable Moonshot Models via AI24X`  
- H1: `Kimi (Moonshot) API with PayPal`  
- 正文：痛点（跨境付费）→ 怎么用 flash 试 → VIP 点名 → CTA Register / Pricing  
- 内链：→ pricing、guides/openai-sdk、models/（其它名模互链，每页 3～5 条）

### 3.4 结构化数据（JSON-LD）

| 类型 | 页面 |
|------|------|
| `Organization` + `WebSite` | 首页 |
| `SoftwareApplication` 或 `Product` | pricing / product |
| `FAQPage` | docs/errors、名模页 FAQ 块 |
| `HowTo` 或 `TechArticle` | guides/* |

### 3.5 性能与体验

- 首屏 CSS 不丢（遵守静态 HTML 安全规范）  
- 压缩无用脚本；docs/models 页避免大图表阻塞  
- HTTPS、移动可读（已有 viewport 则保持）  
- Core Web Vitals：不追求极限，避免明显巨图/未压缩字体

### 3.6 索引卫生

| noindex | index |
|---------|-------|
| token-admin, command-center, ai24x 指挥台, account, demo | index, pricing, product, docs, guides, models, about, register |
| 内页空壳 Coming soon **不要**进 sitemap | paypal 买家指南：可 index（支付意图） |

---

## 4. 内容 SEO 设计（自然流引擎）

### 4.1 页面优先级

| 级 | 页面 | 主意图 |
|----|------|--------|
| P0 | 首页改叙事 | China LLM · value · one key · PayPal |
| P0 | `/models/*` × 6 | Kimi / MiMo / MiniMax / GLM / DeepSeek / Qwen |
| P0 | `/docs` + errors | 集成与排错 |
| P0 | `/guides/openclaw` + `openai-sdk` | 案例词 |
| P1 | pricing 强化性价比模块 | credits / VIP named |
| P1 | learn 对比文 | `{Model} vs GPT cost` |
| P2 | 更多 guides | Continue / Open WebUI / LiteLLM |

### 4.2 内链拓扑

```
首页 ──→ models索引 ──→ 各名模页 ──→ pricing / register
  │              └──→ guides
  └──→ docs/errors ←── 名模页 FAQ「仍失败？」
```

每篇外发 SEO 文（01）必须链回 **对应 `/models/{slug}`**，不是只链首页。

### 4.3 更新节奏（自然流）

| 节奏 | 动作 |
|------|------|
| 上线周 | P0 页全部可抓 + GSC 提交 |
| 每周 | 01：1 名模长尾或 1 篇对比；更新名模页「当前代数」一句 |
| 每月 | 主脑/01：据 GSC 调整 title；淘汰无点击词 |
| 季度 | 观察池（StepFun/豆包…）是否升格为 `/models/*` |

---

## 5. 度量与工具

| 工具 | 谁 | 用途 |
|------|-----|------|
| Google Search Console | 01 看数；04 建站权 | 查询、索引、Core Web Vitals |
| Bing Webmaster | 01 | 补充国际流量 |
| GA4 或等价 | 04 装；01 看 | 落地页→注册漏斗 |
| UTM | 01 | 社媒/开源 vs 自然搜索拆分 |

**周报三行（01）**：Top 查询 · 名模页点击 · 注册归因（organic）。

---

## 6. 付费推广（后期 · 逐步）

**前提**：自然侧 P0 页上线 + PayPal 履约稳 + 注册→首调通率可接受。

| 阶段 | 动作 | 预算态度 |
|------|------|----------|
| **验证** | Google Ads 只投 2～3 个高意图词（如 `Kimi API` / `DeepSeek API PayPal`）→ 对应 `/models/*` | 小日预算，看 CPA |
| **扩展** | 效果好的名模加预算；差的停 | 不广撒 `AI API` 泛词 |
| **再后** | Bing Ads 镜像；慎用泛展示 | SEO 仍是主仓 |

**付费落地页纪律**：必须进名模页或 pricing，禁止进中文行情官；广告文案遵守推广红线（无官方代理/灰产 GPT）。

---

## 7. 分工与统一优化批次中的 SEO 项

| 谁 | SEO 相关 |
|----|----------|
| **主脑** | URL/模板、默认 en、meta 体系、models/guides 页骨架、sitemap/robots |
| **01** | 词表、名模正文、外链与社媒、GSC 运营、付费验证文案 |
| **04** | 生产部署、GSC/域名验证、HTTPS/性能、索引是否可访 |
| **02/03** | 不参与 www 国际 SEO；行情官独立 |

**并入「统一优化」的 SEO 工程清单（建议一次做完骨架）：**

1. `robots.txt` + `sitemap.xml`  
2. www 默认英文 + 首页/pricing title·desc·H1 按主叙事重写  
3. `/models/` 六页骨架（可先短文 + FAQ JSON-LD）  
4. canonical + 基础 OG  
5. guides 两篇入口  
6. GSC 提交（04）  

文案细修与 VIP/Integrations/AI Help 可同迭代，但 **无 models 页则名模词无承接**。

---

## 8. 成功标准（约 90 日）

| 信号 | 目标感（方向性） |
|------|------------------|
| 索引 | models + guides + docs 均在 GSC「已索引」 |
| 查询 | 品牌外出现 Kimi/MiMo/DeepSeek+API 类展示 |
| 转化 | organic 注册占比可统计；付费 CPA 不低于「先 organic 验证」 |
| 纪律 | 无灰产词排到官网；无 admin 误收录 |

---

## 9. 飞书摘要（可转副脑）

```
【AI24X 网站 SEO 设计 2026-07-31】
主打：SEO 自然引流；履约稳后再小步付费。
工程：robots+sitemap、www 默认英文、一页一意图、/models 名模落地（Kimi/MiMo/MiniMax/GLM/DS/Qwen）、guides、FAQ 结构化数据。
运营：01 周更名模长尾并链回 /models；04 保可抓取；付费只投高意图→名模页。
全文：docs/规划/网站SEO优化设计-自然引流-1.0.md
词表：docs/规划/SEO引流核心与规划-1.0.md §3.1.1
```

---

*主脑设计 · 2026-07-31*
