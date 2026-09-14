# 04 执行包：营销攻坚 D1 发布 + 核验

> 签发：司令 2026-09-11
> 交付物打包在 C:\ai24x01\p\deliverables-20260911\
> 执行顺序：GitHub 推送 → dev.to 发布 → HF Space → D1 核验回执

---

## 任务 1：GitHub ai24x-examples 推送代码（优先级最高）

### 交付物
`C:\ai24x01\p\deliverables-20260911\` 下已有：
- `README.md` — 仓库根 README
- `python/README.md` — Python 示例
- `node/README.md` — Node.js 示例
- `curl/README.md` — curl 示例

### 操作
1. 登录 GitHub（浏览器或 git CLI）
2. 进入仓库 https://github.com/ai24x/ai24x-examples
3. 用 Web 编辑器或本地 git 推送上述文件到 main 分支
4. 红线：示例 key 统一用 `sk-...` 占位符，不放真实密钥
5. 完成后回执：仓库链接、文件清单、红线自查

---

## 任务 2：dev.to 发布 DeepSeek 指南

### 交付物
`C:\ai24x01\p\deliverables-20260911\devto-deepseek-guide.md`

### 操作
1. 用 social@ai24x.com 登录 dev.to
2. 发布参数：
   - 标题：DeepSeek API Pricing in 2026: Peak/Off-Peak, Payment, and Getting Started
   - 标签：deepseek, api, pricing, llm, ai
   - 正文：复制 devto-deepseek-guide.md 全文
3. 发布后落盘回执：帖子链接、发布时间

---

## 任务 3：HF Space 文案就绪

### 交付物
`C:\ai24x01\p\deliverables-20260911\hf\` 下 3 份：
- `hf-org-readme.md`
- `hf-space-copy.md`
- `hf-copy-redlines.md`

### 操作
1. 检查 HF Org 状态（ai24x org 建了没）
2. 如果 Org 已建 → 更新 Org README
3. 如果 Space 已建 → 更新文案
4. 如果未建 → 记录阻塞（等雷总审批）
5. 落盘回执

---

## 任务 4：D1 只读核验回执（补交）

按之前任务书完成以下核验，落盘回执到 `C:\Users\Administrator\ops\receipts\2026-09-11\receipt-20260911-04.md`：

### 账号状态
- X @ai24xapp：公开？发帖权限？风控通知？
- GitHub @ai24x：仓库权限？协作权限？
- Reddit u/AI24X：状态？Karma？
- dev.to：social@ai24x.com 能登录？
- HF：Org 状态？发布权限？

### 发布权限
- www 静态文件发布流程
- open 静态+后端部署
- HF Org/Space

### 分析工具
- GSC 权限（www + open）
- 日志/订单来源区分

### 阻塞清单

---

## 回执格式

完成后飞书群回执：
```
✅ GitHub: 已推送 / 链接
✅ dev.to: 已发布 / 链接
✅ HF: 已就绪 / 阻塞项
✅ D1核验: 已落盘
⚠️ 问题项：...
```

*红线：不放真实密钥、不改生产配置、不注册新账号*
