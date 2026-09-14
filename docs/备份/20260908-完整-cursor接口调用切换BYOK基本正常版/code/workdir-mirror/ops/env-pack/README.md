## env-pack（根目录覆盖式）——给副脑用的最省事配置包

目标：让副脑**只做环境配置**，不改代码、不点后台；把“必须放对位置的 `.env`”打包成一个目录结构，复制到 `C:\ai24x01\` 后即可覆盖到正确路径。

> 注意：真实 `.env` 含密钥/口令，**不要提交 Git**。本目录仅提供模板骨架与脚本。

---

## 1) 目录结构（你要发给副脑的私密包，就长这样）

把下面整个目录（`ENVROOT/`）通过内部安全渠道发给副脑，然后让副脑将其内容**合并覆盖**到 `C:\ai24x01\`：

```text
ENVROOT/
  api/
    .env
  p/
    a1/
      api/
        server/
          .env
    a/                       # 仅副脑03/生产灯塔版需要（可选）
      api/
        server/
          .env
```

你可以把 `ENVROOT/` 直接重命名为 `env-pack-root/`，然后把其中的 `api/`、`p/` 目录复制到 `C:\ai24x01\`。

---

## 2) 使用方式（副脑只需 3 步）

### Step A：覆盖到根目录（只改配置，不改代码）

副脑在 Windows PowerShell 执行（示例：你的包在 `C:\env-pack-root\`）：

```powershell
$ROOT="C:\ai24x01"
$PACK="C:\env-pack-root"
if(!(Test-Path $ROOT)){ throw "缺少根目录：$ROOT" }
if(!(Test-Path $PACK)){ throw "缺少 env-pack：$PACK" }

# 覆盖（只覆盖配置文件；目录结构会自动对齐）
Copy-Item -Force "$PACK\api\.env" "$ROOT\api\.env"
Copy-Item -Force "$PACK\p\a1\api\server\.env" "$ROOT\p\a1\api\server\.env"

# 可选：副脑03若仍跑灯塔版 a.ai24x.com（p/a）
if(Test-Path "$PACK\p\a\api\server\.env"){
  Copy-Item -Force "$PACK\p\a\api\server\.env" "$ROOT\p\a\api\server\.env"
}
```

### Step B：重启（只做运维）

```powershell
Set-Location C:\ai24x01
pm2 restart core-8000
pm2 restart a1-api-18011
pm2 restart a1-web-18001
pm2 save
pm2 list
```

### Step C：门禁（必须回传）

```powershell
(Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/docs").StatusCode
(Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:18011/health").StatusCode
```

---

## 3) 填值要点（避免副脑01用到 sqlite）

### a1（副脑01 预演）必须

在 `p/a1/api/server/.env`：

- `AI24X_DB_KIND=pgsql`
- `AI24X_DATABASE_URL=.../ai24x_a_pre`（预演库名口径）
- `AI24X_IDENTITY_API_BASE=http://127.0.0.1:8000`（若主站 core 在本机 8000）
- `AI24X_SMS_INTERNAL_KEY` 必须与主站 `SMS_INTERNAL_KEY` **完全一致**

### 主站 core 必须

在 `api/.env`：

- `SMS_INTERNAL_KEY=...`（与 a1 对齐）

