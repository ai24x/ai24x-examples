# DeepSeek 联调（先通这一家）

## 1. 配 Key

编辑 `api/.env`：

```
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
TOKEN_LLM_TIMEOUT_S=30
```

> **注意（2026-07）**：新 DeepSeek 账号仅支持 `deepseek-v4-flash` / `deepseek-v4-pro`。  
> 请把 `DEEPSEEK_MODEL` 设为 `deepseek-v4-flash`（平台已默认映射 `flash`/`deepseek-chat` → v4-flash）。

然后：

```
pm2 restart core-8000 --update-env
```

## 2. 看是否已就绪（不泄露密钥）

浏览器打开：

http://127.0.0.1:8000/v1/models

看 `upstream`：

| 字段 | 期望 |
|------|------|
| `mode` | `live`（不是 `stub`） |
| `deepseek_ready` | `true` |
| `base` | `https://api.deepseek.com/v1` |

若仍是 `stub`：Key 没读到，检查 `.env` 与 `--update-env`。

## 3. 端到端调用

### 方式 A：控制台
1. http://127.0.0.1:8000/login.html 登录  
2. http://127.0.0.1:8000/console.html 创建 Key 并保存  
3. 底部「试调 chat」→ model=`auto` 或 `deepseek-chat` → 发送  

### 方式 B：curl（把 KEY 换成控制台创建的 sk-）

```bash
curl -s http://127.0.0.1:8000/v1/chat/run ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: sk-你的平台Key" ^
  -d "{\"prompt\":\"用一句话介绍你自己\",\"model\":\"deepseek-chat\"}"
```

## 4. 怎样算「打通了」

响应里：

```json
{
  "provider": "deepseek",
  "layer": "L1",
  "model": "deepseek-chat",
  "response": "（真实模型中文回复，不是 stub 占位）"
}
```

| provider | 含义 |
|----------|------|
| `stub` | 还没配 Key，本地假回复 |
| `deepseek` | 已打到 DeepSeek 官方接口 |

余额应减少（`remaining_quota` / 控制台余额）。

## 5. 常见失败

- **401 / Invalid API Key**：DeepSeek Key 错或过期 → 到 https://platform.deepseek.com 换新 Key，写入 `api/.env` 的 `DEEPSEEK_API_KEY=`（不要重复留注释行干扰），然后 `pm2 restart core-8000 --update-env`
- 全失败会暂时返回 stub，**且不计费**（`token_count=0`，见总纲 v3.3）
- **余额 402**：先控制台模拟到账加油包  
- **仍 stub 且 route 无 401**：`pm2 restart core-8000 --update-env`，确认进程 cwd 是 `api/`  
- **超时**：加大 `TOKEN_LLM_TIMEOUT_S=30`

## 6. 后续厂商

先只保 DeepSeek。Kimi / 智谱等进管理后台「模型通道」模块再加（按层配 `TOKEN_LLM_L0_*` / `L3_*`）。
