# AI24X Token 安全与防拷贝说明

## 诚实边界

**没有任何软件能从物理上阻止别人复制源码或仿站。**  
我们能做的是提高「直接拖库、扫接口、转卖 Key、冒充调用」的成本，并保留追责线索。

| 风险 | 已采取的措施 |
|------|----------------|
| 拖库拿走全部 API Key | Key **仅存 HMAC-SHA256**，创建时只展示一次明文 |
| 用 `?user_id=` 白嫖 | `STRICT_AUTH=true`（默认）强制 `X-API-Key` |
| 刷接口 | chat 按 IP / Key 滑动窗口限流 |
| 生产泄露调试面 | `APP_ENV=production` 时默认关闭 `/docs` `/openapi.json` |
| 响应被洗白转卖 | 响应带 `attribution.trace` 溯源字段 |
| 浏览器 XSS 点一点 | 安全响应头（nosniff / DENY frame 等） |
| 跨站乱调 | `CORS_ORIGINS` 可收紧（生产勿长期 `*`） |

## 防「业务拷贝」建议（产品层）

1. **核心算法/路由权重/上游 Key 只放服务端**（已是）  
2. 上游 Key（DeepSeek 等）永不下发前端、永不进仓库  
3. 管理后台后续做：通道启停、按租户限速、异常 Key 一键吊销  
4. 合同 / 用户协议写明禁止转售、镜像；侵权走法务  
5. 行情官公式等知识产权与 Token 网关分开保护（勿混同一套泄露面）

## 生产 `.env` 最低安全集

```
APP_ENV=production
SECRET_KEY=换成足够长的随机串
STRICT_AUTH=true
DISABLE_DOCS_IN_PROD=true
CORS_ORIGINS=https://www.ai24x.com,https://api.ai24x.com
ENABLE_RATE_LIMITING=true
CHAT_RATE_PER_MINUTE=60
CHAT_RATE_PER_IP_PER_MINUTE=120
SMS_INTERNAL_KEY=强随机
DEEPSEEK_API_KEY=仅服务器持有
```

## 自检

```bash
# 1) 无 Key 应 401
curl -s -o - -w "%{http_code}" http://127.0.0.1:8000/v1/chat/run -H "Content-Type: application/json" -d "{\"prompt\":\"hi\"}"

# 2) 新建 Key 后库内应为 sha256: 开头，不是 sk-
# 3) 响应 JSON 含 attribution.trace
```

## 不能指望的

- 前端 JS「加密」挡不住爬虫  
- 混淆 HTML 挡不住仿站  
- 单机内存限流挡不住分布式打手（需 Nginx/Redis 前置）
