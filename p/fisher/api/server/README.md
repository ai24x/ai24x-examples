# 山海渔 · Fisher API（最小真源）

本地默认 **SQLite**：`./data/fisher.db`（相对本目录工作路径）。生产可改 `FISHER_DATABASE_URL` 为 PostgreSQL。

## 启动（Windows / PowerShell）

```powershell
cd "e:\AI24X\ai24x-website\ai24x01\p\fisher\api\server"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env：至少改 FISHER_JWT_SECRET
py -m uvicorn app.main:app --host 127.0.0.1 --port 18041 --reload
```

- 文档：`http://127.0.0.1:18041/docs`  
- 健康：`http://127.0.0.1:18041/health`

## 开发联调（无微信）

1. `POST /v1/auth/dev-login` body：`{"dev_key":"你的设备名"}` → 拿 `access_token`  
2. `Authorization: Bearer <token>` 调 `GET /v1/me`、`POST /v1/game/fish`、`POST /v1/game/sell`

## 与小程序

真机请求需 **HTTPS 合法域名**；本地可在微信开发者工具关闭域名校验，或内网穿透 HTTPS。小程序示例见 `../../miniprogram/`。

## Python 版本

若使用 **Python 3.14** 且 `pip install` 报 `pydantic-core` 编译失败，请使用本目录已放宽的版本范围（见 `requirements.txt`），或本地改用 **Python 3.12 / 3.13** 虚拟环境开发。
