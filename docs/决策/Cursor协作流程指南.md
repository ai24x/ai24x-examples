# Cursor 编程协作流程

> 现行口径。旧「根目录散落 md」已汇总到 `docs/` 子目录。

---

## 一、整体开发流程

```
Cursor 写代码 → 雷总本地测试 → git push gitee && git push origin
                → 副脑01 后台 Review（不阻塞）
                → 发版：副脑01 预发 → 副脑03 生产 pm2 restart
```

**原则**：副脑01 不阻塞本地开发节奏。

---

## 二、文档放哪里（强制）

| 目录 | 放什么 |
|------|--------|
| `docs/规划/` | 总纲、产品定位、市场阶段 |
| `docs/开发/` | 接口任务、SQL/实现说明 |
| `docs/决策/` | 协作流程、拍板记录 |
| `docs/联调/` | DeepSeek / SMTP / 支付 / 安全 |
| `docs/历史/` | 旧版总纲（只读） |
| `memory/daily/` | 当日作战卡（可执行清单） |

**不要**在仓库根目录维护总纲/任务正文；根目录仅允许指向 `docs/` 的短 stub。

入口总纲：`docs/规划/开发总纲-AI24X-API-v3.5.md`

---

## 三、项目结构（Cursor 常改）

```
ai24x01/
├── api/           ← FastAPI（Token 平台主战场）
├── web/           ← 静态前端
├── db/            ← DDL
├── p/             ← 子项目（a1 / fisher…）；改 Token 时勿动 a1 履约
├── docs/          ← 见上表
└── memory/daily/  ← 作战卡
```

本地 API：PM2 `core-8000` → `http://127.0.0.1:8000`  
一键烟测：`cd api && python scripts_token_smoke.py`

---

## 四、开发规范

1. 已有代码风格：中文注释、英文标识；不大拆重写  
2. 改完先本地测（控制台 / 烟测脚本）  
3. 提交信息写清「为什么」；**不要提交** `.env` / 密钥  
4. 推送：`git push gitee master && git push origin master`（需雷总确认时再推）  
5. **禁止**把 a1 的微信/支付宝 notify 改成 Token 回调  

---

## 五、当前任务状态（2026-07-26）

| 项 | 状态 |
|----|------|
| keys / billing / chat 计费 / referrals / models | ✅ |
| FREE 日限 100 · flash\|pro\|ultra | ✅ |
| DeepSeek v4 联调 | ✅ |
| SMTP 邮箱注册 | ✅ |
| 成本/用量日报脚本 | ✅（飞书 Webhook 待配） |
| Token 真支付 | ⬜ 等独立 notify + 商户 |
| 反作弊 | ⬜ P1 |
| Phase 2 英文/PayPal/OpenAI 兼容 | ⬜ |

详细：`docs/规划/开发总纲-AI24X-API-v3.5.md`  
接口：`docs/开发/开发任务-Token聚合MVP.md`

---

## 六、常见问题

| 问题 | 解答 |
|------|------|
| 改文件前要问谁？ | 按总纲直接改；真支付/公网回调需雷总配合 |
| 改错了？ | git 回滚 |
| 新文档写哪？ | 规划/开发/决策/联调 四选一；勿堆根目录 |
| 不确定？ | 先读总纲 v3.5，再改最小闭环 |
