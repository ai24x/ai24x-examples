# AI24X 股票查询助手 · 后端（FastAPI）MVP

本目录是“阶段1（MVP）”后端骨架，用于：
- 登录/鉴权（MVP：开发态验证码）
- 次数系统（查询/扣减，含短时间重复不扣）
- 邀请码（一级绑定 + 发放次数）
- 数据代理（suggest/kline：后端请求外部，多源兜底可逐步加）

## 本地启动（Windows / PowerShell）

1) 进入目录

```powershell
cd "e:\AI24X\ai24x-website\ai24x01\p\a\api\server"
```

2) 创建虚拟环境并安装依赖

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -U pip
pip install -r requirements.txt
```

3) 启动（本地推荐端口：静态 18001，API 18031）

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 18031 --reload
```

打开：`http://127.0.0.1:18031/docs`

管理后台（浏览器）：默认 `http://127.0.0.1:18031/admin20260501/login`（工作台去掉 `/login`；路径由 `AI24X_ADMIN_MOUNT_PATH` 控制）。

## 安全基线（首推）

小项目建议：**长随机 `AI24X_ADMIN_KEY`**、有域名时 **HTTPS**、**勿公开**管理路径、依赖内置 **登录限流 + HttpOnly 会话**。可选：**`AI24X_ADMIN_OTP_PHONES`**（总管手机 CSV）与库表 `admin_operators` 并集非空时，浏览器登录须 **短信 OTP + 密钥**（`POST /api/admin/otp/send`）。启动时若密钥过弱会打 `[admin-security]` 日志。

**后期加强**（SSH 转发、Nginx IP 白名单、VPN 等）：见 `p/a/docs/管理后台-安全基线与后期加强预案.md`。

## 环境变量

复制 `.env.example` 为 `.env`（可选），或直接用默认值。

