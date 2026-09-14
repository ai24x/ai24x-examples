# 副脑04 · 更新指令 · chat/run 认登录 JWT（试调用 401）

> 日期：2026-08-04  
> **执行机：副脑04（正式国际生产 · `api.ai24x.com`）**  
> 副脑03 Token 仅为备份，**日常勿在此指令下更新 03**。  
> 现象：控制台已登录，试调用点发送 →「登录未通过试调用」/ 后端 `无效的API Key或用户ID`  
> 根因：公网 `/v1/chat/run` **仍走旧鉴权**（把 Bearer JWT 当 API Key）；余额接口已认 JWT。  
> 进程：NSSM `AI24X-core`（**必须重启**）  
> 禁止整文件覆盖 `.env`

## 验证（更新前，应仍是旧行为）

```powershell
$jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.sig"
# 旧：无效的API Key或用户ID
# 新：登录已失效
try {
  Invoke-RestMethod -Uri "https://api.ai24x.com/v1/chat/run" -Method POST `
    -ContentType "application/json" -Headers @{ Authorization = "Bearer $jwt" } `
    -Body '{"prompt":"hi","model":"shared"}' -TimeoutSec 15
} catch { $_.ErrorDetails.Message }
```

## 更新步骤（副脑04）

1. 在 **副脑04** 仓库目录（`api.ai24x.com` 源站）进入 `C:\ai24x01`  
2. 拉齐含以下文件的版本：
   - `api/main.py`（`get_current_user` 认控制台 JWT；`chat_run` 正确注入 `Request`）
   - `api/free_shared.py`（shared junk）
   - `api/services.py`（shared remain 扣费后）
   - 静态：`web/console.html`、`web/js/api.js`、`web/js/console.js`（`?v=20260804n`）
3. 重启：

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 3
Get-Service AI24X-core | Format-Table Name, Status
```

4. 再跑假 JWT 探测：应变为 **`登录已失效`**（不再是 `无效的API Key或用户ID`）  
5. 浏览器硬刷新控制台 → 未勾选「用 API Key」→ shared/flash 发送应通

## 回滚（副脑04）

```powershell
# 还原 api/main.py 等到上一稳定提交后：
Restart-Service AI24X-core
```

## 说明

- 本机预览 ≠ 公网；未在 **04** 拉码重启前，公网仍可能是旧行为。  
- 临时绕过：试调用勾选「用 API Key」并用本账号完整 sk。  
- 发版总册：`docs/联调/Token发版-Gitee与副脑04.md`
