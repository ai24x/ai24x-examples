## PM2 统一管理（副脑03 推荐）

目标：让 `a.ai24x.com` / `api.ai24x.com` **7×24 稳定运行**，并且能一条命令查看状态/日志、自动重启、开机自启。

本仓库已提供 PM2 配置文件：仓库根目录 `ecosystem.config.cjs`。

### 1) 前置条件

- 服务器已安装 `node` / `npm`
- Python 依赖已安装（各服务目录自带 `requirements.txt`）

安装 PM2（全局）：

```bash
npm i -g pm2
pm2 -v
```

### 2) 准备两个后端（建议各自虚拟环境）

#### 2.1 a.ai24x.com（AI 行情官｜灯塔版（1.01），端口 8001）

```bash
cd /path/to/ai24x01/p/a/api/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

#### 2.2 api.ai24x.com（AI24X 统一 API，端口 8002）

```bash
cd /path/to/ai24x01/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2.3 国际（intl）建议（同代码分环境）

若后期部署 intl 环境（出海复制），建议保持同一份代码，但做到：

- **分库**（intl 与 cn 不混）
- **环境变量独立**（支付/上游/回调域名/CORS）
- **PM2 进程名区分**（避免误操作）

端口与进程名建议见 `docs/PORTS.md`（例如 9000+ 段、`ai24x-intl-core-api`）。

> 说明：PM2 默认执行 `python3 -m uvicorn ...`。如果你希望强制走某个 venv 的 python，
> 建议在 `ecosystem.config.cjs` 里把 `script` 改成 venv 路径，例如：
> `script: "./.venv/bin/python"`（Linux）或 `script: ".\\.venv\\Scripts\\python.exe"`（Windows）。

### 3) 启动/停止/查看

在仓库根目录：

```bash
cd /path/to/ai24x01
pm2 start ecosystem.config.cjs
pm2 status
pm2 logs
```

停止/重启：

```bash
pm2 stop a-api-8001
pm2 restart a-api-8001

pm2 stop core-api-8002
pm2 restart core-api-8002
```

### 4) 开机自启（必须做）

```bash
pm2 startup
pm2 save
```

执行 `pm2 startup` 后，按提示把那条 `sudo ...` 命令复制执行一次即可。

### 5) 发布更新的标准流程（建议）

```bash
cd /path/to/ai24x01
git pull

# 如有依赖变更：进入对应服务目录 pip install -r requirements.txt

pm2 restart ecosystem.config.cjs
pm2 status
```

### 6) 与 Nginx 配合（同域最省心）

- `a.ai24x.com/` → 静态目录（`p/a/web/`）
- `a.ai24x.com/api/*` → `http://127.0.0.1:8001/api/*`
- `api.ai24x.com/*` → `http://127.0.0.1:8002/*`

这样 `demo.html` 会以 **同域 API** 调用，避免 CORS 与“本地能用、线上失败”的典型坑。

