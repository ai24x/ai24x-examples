# 副脑04 · 更新指令（收银台统一到控制台 + 支付提示可见）

> 状态：**等主脑本地验收 OK 后再发令**（勿抢跑）  
> 进程：NSSM `AI24X-core`（本包以静态页为主；无 `.env` 必改项则可不重启）  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（或 `gitee master`）

## 本包要解决什么

| 项 | 说明 |
|----|------|
| 收银台唯一落点 | **控制台**下单/支付；价格页只「去购买」带入套餐 |
| 提示可见 | 限购/失败/成功 → 支付卡片内 + 底部浮层 toast |
| 弹窗死循环 | 去掉价格页 `?pay=` 自动开支付；深链只引导一次并清 URL |
| VIP 文案 | 「VIP 点名清单」；去掉「上游厂商」等开发口吻 |

## 主要文件（静态）

- `web/pricing.html`
- `web/console.html` / `web/js/console.js` / `web/css/base.css`
- `web/models/vip-picks.html` / `web/config/locales.js`
- （可选自检）`scripts/check_user_facing_copy.py`

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望说明含：console checkout / pricing buy / toast / VIP list 一类

# 本包通常无需改 .env；勿动 DATABASE_URL

# 静态由站点根目录直接读仓库时，拉码即生效。若有 CDN/缓存再清。
# 仅当同批含 api 变更时再重启：
# Restart-Service AI24X-core
# Start-Sleep -Seconds 5

try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

curl.exe -sS -o NUL -w "pricing=%{http_code}`n" https://www.ai24x.com/pricing.html
curl.exe -sS -o NUL -w "console=%{http_code}`n" https://www.ai24x.com/console.html
curl.exe -sS -o NUL -w "vip=%{http_code}`n" https://www.ai24x.com/models/vip-picks.html
```

---

## 验收（回报主脑）

浏览器 **Ctrl+F5**：

1. https://www.ai24x.com/pricing.html  
   - 套餐卡只有 **「去购买」**（无微信/支付宝/PayPal 三按钮）  
   - 文案写清：支付在控制台完成  
2. 点「去购买」→ 进控制台并定位到套餐区（高亮对应套餐）  
   - **不会**自动弹支付窗 / 不会循环弹窗  
3. 在控制台点支付：  
   - 限购等错误：卡片内红字 + 底部浮层可见  
4. https://www.ai24x.com/models/vip-picks.html 标题为 **VIP 点名清单**

## 不要做

- 不要 `pm2 restart` core  
- 不要 Write 整份 `.env`  
- 主脑未说「已本地 OK、已推 Gitee」前不要执行本包  
