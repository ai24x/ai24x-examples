# 副脑04 · 更新指令（英文错误文案 + 主题下拉去前缀）

> 发令：2026-08-01 · 目标提交 `392c368`  
> 进程：NSSM `AI24X-core`（**本包含 api 变更，需重启**）  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（或 `gitee master`）

## 本包要解决什么

| 项 | 说明 |
|----|------|
| 英文 UI 不再漏中文报错 | 如限购「该优惠套餐每位用户限购一次…」→ 英文句；其余中文 detail 映射或通用英文兜底 |
| 后端双语 detail | `message_zh` / `message_en`（限购、余额、冻结等） |
| 主题下拉 | 去掉 `Theme:` 等前缀，只保留风格名（与中文「蓝白/深色/轻量」一致） |

## 主要文件

- `api/user_i18n.py`（新）
- `api/token_pay_service.py` / `api/auth_user_service.py` / `api/free_shared.py` / `api/token_mvp_service.py`
- `web/js/api.js`（`?v=20260801f`）
- `web/config/locales.js`（`?v=20260801g`）
- 各页 HTML 缓存戳

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望：392c368（fix i18n 英文错误与主题文案）

# 本包无需改 .env；勿动 DATABASE_URL

Restart-Service AI24X-core
Start-Sleep -Seconds 5

try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

curl.exe -sS -o NUL -w "health=%{http_code}`n" https://api.ai24x.com/health
curl.exe -sS -o NUL -w "pricing=%{http_code}`n" https://www.ai24x.com/pricing.html
curl.exe -sS -o NUL -w "console=%{http_code}`n" https://www.ai24x.com/console.html
```

---

## 验收（回报主脑）

浏览器 **Ctrl+F5**（英文界面）：

1. https://www.ai24x.com/ — 右上角主题下拉为 **Blue / White** / **Dark** / **Soft cards**（无 `Theme:`）
2. 控制台对已购入门包再下单限购：英文提示  
   `This promo plan is limited to one purchase per account. Please choose another plan.`  
   （不得出现中文限购句）
3. `https://api.ai24x.com/health` → **200**

## 不要做

- 不要 `pm2 restart`（副脑04 用 NSSM）
- 不要 Write 整份 `.env`
- 不要动 `DATABASE_URL`

## 回滚

```powershell
Set-Location C:\ai24x01
git log -3 --oneline
git checkout 47dba4b -- api/user_i18n.py api/token_pay_service.py api/auth_user_service.py api/free_shared.py api/token_mvp_service.py web/js/api.js web/config/locales.js
# 或整仓回退到上一已知好提交后再 Restart-Service AI24X-core
Restart-Service AI24X-core
```
