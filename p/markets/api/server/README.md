# markets api\server

独立产品后端，端口 18012，服务名 AI24X-markets-api。

## 启动（开发）

```powershell
cd p\markets\api\server
python -m uvicorn app.main:app --host 127.0.0.1 --port 18012
```

## 依赖

```powershell
pip install -r requirements.txt
```

## 环境变量

复制 `.env.example` 为 `.env` 使用；密钥类勿入 git / ops / 公网。

## 目录

- `app\main.py` FastAPI 入口（/health 探针）
- `data\` 日缓存 / 归档（运行时数据，git 忽略）

## 当前状态

Phase 0 骨架：仅 /health 可用；行情 / 信号 / AI 点评 / 订阅见 MVP 清单 Phase 1-3。
