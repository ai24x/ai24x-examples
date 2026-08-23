# 【04 更新部署验收】core 管理后台 ADMIN_API_KEY + 双因素短信上线 · 配置热修

> 老板反馈：管理后台「BYOK 套餐管理」报 `core 未配置 ADMIN_API_KEY`；按老板 2026-08-22 定案（六十一节）生产 core 应开启「管理密钥 + 管理员手机验证码」双因素。
> 本次为纯环境变量配置变更（代码无需改动），不新增 commit；执行人：副脑04。

## 一、背景与目标
- 现状：生产 `C:\ai24x01\api\.env` 与 `C:\ai24x01\p\open\api\.env` 均无 `ADMIN_API_KEY` → core 代理 `/v1/admin/products/open/plans`（token-admin BYOK 套餐管理）503。
- 目标配置（值由司令直接 scp 的补丁脚本写入，脚本内已打码回显）：
  - core：`ADMIN_API_KEY=<新生成>`、`ADMIN_REQUIRE_SMS=true`、`ADMIN_PHONE=18958992226`
  - open：`ADMIN_API_KEY=<与 core 相同>`（core 代理转发到 open 时用同一密钥；open 侧不开短信，只认密钥）
- 生效后：token-admin 登录 = 管理密钥 + 手机验证码双因素（30 分钟会话）；BYOK 套餐管理可正常加载/保存。

## 二、前置
- 司令已直接 scp：`C:\Users\Administrator\ops\admin_env_20260823.ps1`（含两处 .env 写入 + 两服务重启 + 本机验证）。
- **若该文件不存在，先停在这里联系司令，勿自行猜值。**

## 三、执行步骤（整段复制运行）
```powershell
$patch = "C:\Users\Administrator\ops\admin_env_20260823.ps1"
if (-not (Test-Path $patch)) { Write-Host "!! 缺少密钥补丁脚本，停住联系司令" -ForegroundColor Red; exit 1 }
powershell -NoProfile -ExecutionPolicy Bypass -File $patch
if ($LASTEXITCODE -ne 0) { Write-Host "!! 管理密钥补丁失败" -ForegroundColor Red; exit 1 }
Write-Host "ADMIN 配置已应用" -ForegroundColor Green
```

> 脚本内已包含：备份 .env（.bak-admin-时间戳）→ 幂等写入 → 重启 AI24X-core(8002) + AI24X-open-api(18080) → 验证：
> - core `/v1/admin/auth/mode`：require_sms=true、sms_enabled=true、sms_key_configured=true
> - open `/health` healthy + commit 不变
> - open `/v1/admin/byok/plans` 带 X-Admin-Key 返回 200（证明 open 接受该密钥）

## 四、公网验收（04 服务器侧）
```powershell
$m = Invoke-RestMethod -Uri "https://api.ai24x.com/v1/admin/auth/mode" -TimeoutSec 15 -UseBasicParsing
"www admin mode require_sms=" + $m.require_sms + " sms_enabled=" + $m.sms_enabled
$h = Invoke-RestMethod -Uri "https://open.ai24x.com/health" -TimeoutSec 15 -UseBasicParsing
"open health commit=" + $h.commit
$p = Invoke-RestMethod -Uri "https://open.ai24x.com/v1/billing/plans" -TimeoutSec 15 -UseBasicParsing
"open byok_count=" + @($p.byok_plans).Count + " token_count=" + @($p.plans).Count
```

## 五、验收清单（回执逐项列 ✅/⚠️）
1. core `.env` 含 ADMIN_API_KEY / ADMIN_REQUIRE_SMS=true / ADMIN_PHONE=18958992226（只确认存在，不回显值）
2. open `.env` 含 ADMIN_API_KEY
3. `https://api.ai24x.com/v1/admin/auth/mode` → require_sms=true、sms_enabled=true
4. open `/health` commit 与部署前一致（未动代码）
5. open `/v1/billing/plans` byok=2 / token=6（前台数据正常）
6. open `/v1/admin/byok/plans` 带新密钥 200

## 六、备注
- **密钥交接**：新的 ADMIN_API_KEY 由司令在本机会话单独告知老板（登录第一因子）；短信验证码发到 18958992226。
- **前台套餐显示**：生产 API 数据正常（BYOK 2 个、token 6 个）；若老板浏览器仍显示无套餐，先 Ctrl+F5 强刷（共享资源已升 v=20260823b），再报司令。
- 管理后台登录后：密钥（X-Admin-Key）→ 获取短信验证码 → 验证码登录签发 30 分钟会话 → 再进 BYOK 套餐管理等栏目。

## 七、回执格式（完成后发指挥部群）
```text
✅ 已完成项：
1. ...
⚠️ 问题项：
1. 无（或具体说明）
```
