# 副脑03 · 更新指令（名模目录对齐 OR 现网 + 用户端文案）

> 发令：2026-08-01  
> **进程管理：NSSM / Windows 服务（禁止 pm2 启停本包）**  
> **禁止**整文件覆盖 `api/.env`（本包无强制新 Key；默认模型代码已改）  
> 远端：`git pull gitee master`（若只有 origin：`git pull origin master`）

## 本包内容（主站 Token）

| 项 | 说明 |
|----|------|
| VIP 点名 | 对齐 OR 现网：Kimi K3 / MiMo Pro / MiniMax M3 / Qwen Max / GLM-5.2；GPT-5.4·5·mini；Claude Opus/Sonnet 5、Haiku 4.5；Gemini 3.1 Pro / 3.6 Flash |
| 公开档默认 | `ultra`→`openai/gpt-5-mini`；EU→`qwen/qwen3.7-plus`（env 未写死时可直接吃代码默认） |
| 文案 | 去掉用户端 OR/挂牌腔；中英 Notes；名模首页加「国际名模」轻量入口 |
| 页面 | `/models/vip-picks.html`、`/models/index.html`、控制台下拉、locales |
| 指挥中心 | `web/ops/ai24x-command.json` 路由表同步 |

## 生产 env（本包通常不用改）

- **不要** Write 整份 `.env`  
- 若 `.env` 里曾**手工写死**旧值，请行级改掉或删掉该行（让代码默认生效）：

```
# 若存在则改为（或删除该行）：
# OPENROUTER_MODEL_L3=openai/gpt-5-mini
# OPENROUTER_MODEL_EU=qwen/qwen3.7-plus
```

改完必须：`Restart-Service AI24X-core`。

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull gitee master
# 若 pull 失败且远端叫 origin：git pull origin master
git log -1 --oneline
# 期望含：VIP catalog / named models / gpt-5 一类说明

# 本包无新 pip 依赖则跳过
# Set-Location C:\ai24x01\api
# python -m pip install -r requirements.txt

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status

# 门禁
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

# 点名清单：应含 Kimi K3 / GPT-5.4 / Claude Sonnet 5（标题字段）
$m = (Invoke-WebRequest "http://127.0.0.1:8002/v1/models" -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
$titles = @($m.vip_picks | ForEach-Object { $_.title }) -join " | "
"vip_count=$($m.vip_picks.Count)"
"l3=$($m.upstream.l3_model)"
"sample=$titles"

curl.exe -sS -o NUL -w "api_health=%{http_code}`n" https://api.ai24x.com/health
curl.exe -sS -o NUL -w "vip_picks=%{http_code}`n" https://www.ai24x.com/models/vip-picks.html
curl.exe -sS -o NUL -w "models_index=%{http_code}`n" https://www.ai24x.com/models/index.html
```

## 验收（回报主脑）

1. `git log -1 --oneline`（本包提交）  
2. `AI24X-core` = **Running**；`8002/health` = **200**  
3. `l3` = **`openai/gpt-5-mini`**（若仍是 gpt-4o-mini → 检查 `.env` 是否写死旧 L3）  
4. `vip_count` ≥ **17**；标题含 **Kimi K3**、**GPT-5.4**、**Claude Sonnet 5**（不要再出现「Kimi / Moonshot（OR）」）  
5. 浏览器 **Ctrl+F5**：  
   - https://www.ai24x.com/models/vip-picks.html （中文说明短词；切 English 后 Notes 为英文）  
   - https://www.ai24x.com/models/index.html （下方有「国际名模」入口）  
   - 控制台模型下拉可见新标题  

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
# 记下本包 hash 后：
git revert <本包提交hash> --no-edit
# 或硬回上一好包（仅主脑明示时）：
# git reset --hard <上一好包hash>
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }
```

## 不要做

- 不要 `pm2 restart` 本机 core（生产是 NSSM `AI24X-core`）  
- 不要整文件覆盖 `.env`  
- 不要把密钥贴回飞书/指挥中心  
