# 副脑03 · 更新指令（用量监控 + 国际名模 + 上游骨架）

> 发令：2026-07-31  
> **进程管理：NSSM / Windows 服务（禁止 pm2 启停本包）**  
> **禁止**整文件覆盖 `api/.env`（只行级增补；无强制新 Key）  
> 远端：`git pull gitee master`（若只有 origin 则 `git pull origin master`）

## 本包内容（主站 Token）

| 项 | 说明 |
|----|------|
| 管理台 | 「模型与系统」拆为：用量监控 / 开关与密钥 / 模型仓库 / 毛利与告警 / 免费共享 |
| API | `GET /v1/admin/token/usage_monitor`；告警含高耗用户/国际名模 |
| VIP | 国际旗舰+轻量梯队；倍率 GPT×14 / Claude×18 / Gemini×12；日赠有效期 2 天；幂等防双发 |
| 上游 | Together / OpenAI / Anthropic / Google 直连骨架（**未强制填 Key**，空=不启用） |
| 密钥 | 主/免费 OR+硅基切开；管理台可临时覆盖（`llm_keys_override.json`，不进 git） |
| 前端 | 协助浮钮、VIP 点名页、控制台等（随本包 web） |

## 生产 env（可选行级，本包可不改也能起）

若尚未切开免费 Key，建议稍后行级追加（**不要 Write 整文件**）：

```
OPENROUTER_API_KEY_FREE=（免费通道专用，可与主 Key 不同）
SILICONFLOW_API_KEY_FREE=（L0/共享专用）
# 以下晚些再配，空着即可
# TOGETHER_API_KEY=
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# GOOGLE_AI_API_KEY=
```

改完须：`Restart-Service AI24X-core`（NSSM 会带新环境；若服务不重载环境则按你机惯例 `--update-env` 等价操作）。

## 执行（PowerShell · 整段复制给 OpenClaw）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull gitee master
# 若 pull 失败且远端叫 origin：git pull origin master
git log -1 --oneline
# 期望含：usage monitor / VIP intl / upstream providers 一类说明

# 本包无新 pip 依赖则跳过；若 pull 后 requirements 有变再执行：
# Set-Location C:\ai24x01\api
# python -m pip install -r requirements.txt

Get-Service AI24X-core | Format-Table Name, Status
# 若为 Paused/Stopped：先 Start-Service AI24X-core；正常则 Restart
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status

# 门禁
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }
try { (Invoke-WebRequest "http://127.0.0.1:8002/openapi.json" -UseBasicParsing -TimeoutSec 15).Content.Contains("usage_monitor") } catch { $_.Exception.Message }
curl.exe -sS -o NUL -w "api_health=%{http_code}`n" https://api.ai24x.com/health
curl.exe -sS -o NUL -w "admin_page=%{http_code}`n" https://www.ai24x.com/token-admin.html
```

## 验收（回报主脑）

1. `git log -1 --oneline`  
2. `AI24X-core` = **Running**；本机 `8002/health` = **200**  
3. openapi 含 **`usage_monitor`** = True  
4. 浏览器打开 https://www.ai24x.com/token-admin.html （**Ctrl+F5**）  
   - 左侧「模型与系统」可见：**用量监控 / 开关与密钥 / 模型仓库 / 毛利与告警 / 免费共享**  
   - 「用量监控」能刷新，**不再**出现 `HTTP 404`  
5. （可选）控制台 VIP 点名下拉里有国际轻量档  

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
# 记下本包 hash 后：
git revert <本包提交hash> --no-edit
Restart-Service AI24X-core
Start-Sleep -Seconds 5
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 勿做

- 勿改 `p/a1` 支付回调  
- 勿用 Cursor **Write 整文件覆盖** `api/.env`  
- 勿在本包强行申请 Together/厂直连 Key（骨架已在，Key 后补）
