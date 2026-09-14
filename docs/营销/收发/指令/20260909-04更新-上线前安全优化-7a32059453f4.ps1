# 【04 更新】上线前安全优化（S1-S5/S8）— 7a32059453f4

> 通道：司令 → 04（同步）｜ 密钥：全程未动

## 变更范围

| 模块 | 文件 | 改动 |
|------|------|------|
| core api/ | main.py / model_router.py / models.py / oauth_social.py / services.py / token_mvp_service.py | S1-S5 代码优化 |
| open p/open/api/ | byok.py / byok_routes.py / main.py / model_router.py / models.py / services.py / token_mvp_service.py | S1-S5 同步 |
| 前端 web/js/ | api.js / ai24x-chrome.js（三站） | OAuth HttpOnly 前端适配 |
| 脚本 scripts/ | _seo_stocks_deploy_20260825.ps1 / _seo_stocks_html_alias_20260908.ps1 | S8 nginx 别名 |

## 执行步骤

### Step 1：git pull
```powershell
Set-Location C:\ai24x01
git pull
$HEAD = git rev-parse --short=12 HEAD
Write-Host "HEAD=$HEAD"
# 预期：7a32059453f4
```

### Step 2：重启 core（www）
```powershell
Restart-Service AI24X-core -Force
Start-Sleep 5
# 验证
curl.exe -s "https://www.ai24x.com/health" | Select-Object -First 1
```

### Step 3：重启 open（BYOK）
```powershell
Restart-Service AI24X-open-api -Force
Start-Sleep 5
curl.exe -s "https://open.ai24x.com/health" | Select-Object -First 1
```

### Step 4：执行 nginx 别名脚本（S8）
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\ai24x01\scripts\_seo_stocks_html_alias_20260908.ps1
```

### Step 5：公网验收
- [ ] www.ai24x.com/health → commit=7a32059*
- [ ] open.ai24x.com/health → status ok
- [ ] 密码登录 www → console → 余额显示正常
- [ ] Chat completion 返回正常
- [ ] /v1/auth/logout → {"ok":true}
- [ ] markets.ai24x.com/stocks/nvda.html → 200（脚本执行后）
- [ ] 版本号：全站 39 页 locales.js/api.js/shell.js 版本号未变

## 回执
✅ 完成项 / ⚠️ 问题项（无则写「无」）
