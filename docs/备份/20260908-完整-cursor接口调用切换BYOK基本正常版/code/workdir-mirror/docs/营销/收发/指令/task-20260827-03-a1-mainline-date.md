# 03 更新指令：主线「数据截至」回写今日（6526fa7）

> 派发：司令 → 03 · 仅 `bj_screener.py` · 无 DB 迁移
> ⚠️ 禁止改 `.env`；备份落 `C:\backup\ai24x_a\`

## 现象
gd.html「主线 · 今天看什么」仍显示「数据截至 20260826」，即使当日复盘归档已有。

## 根因
掘金约 15:05 预扫时常早于复盘归档（约 15:10），缓存写入 `mainline_date=昨日`；读缓存时 `_reattach_ths` 已换主线名，但未回写 `mainline_date`。

## Step 0 备份
```powershell
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$bk = "C:\backup\ai24x_a\a1-ml-date-$stamp"
New-Item -ItemType Directory -Force -Path $bk | Out-Null
Copy-Item C:\ai24x01\p\a1\api\server\app\bj_screener.py (Join-Path $bk "bj_screener.py") -Force
Write-Output ("backup ok -> " + $bk)
```

## Step 1 git pull + 校验
```powershell
Set-Location C:\ai24x01
git fetch gitee master --quiet
git pull --ff-only gitee master 2>&1 | Select-Object -Last 8
$HEAD = (git rev-parse HEAD).Trim()
Write-Output ("HEAD=" + $HEAD)
$NEED = "6526fa7b212d2b930ead9223d6d65f42f817bfc0"
if (-not (git merge-base --is-ancestor $NEED HEAD)) { throw ("目标 commit 不在 HEAD: " + $NEED) }
Select-String -Path p\a1\api\server\app\bj_screener.py -Pattern "mainline_date" | Select-Object -First 5
Select-String -Path p\a1\api\server\app\bj_screener.py -Pattern "若不回写 mainline_date" | Select-Object -First 1
Write-Output "commit check PASS"
```

## Step 2 重启
```powershell
Restart-Service AI24X-a1-api -Force
Start-Sleep -Seconds 10
$svc = Get-CimInstance Win32_Service -Filter "Name='AI24X-a1-api'"
Write-Output ("state=" + $svc.State + " pid=" + $svc.ProcessId)
Invoke-RestMethod -Uri "https://a.ai24x.com/health" -UseBasicParsing -TimeoutSec 20 | ConvertTo-Json -Compress
```

## Step 3 验收
硬刷新 `https://a.ai24x.com/gd.html`：主线标题应为「数据截至 20260827」（或当日），不再卡在昨日。

## Step 4 回执
- ✅ HEAD / 文案命中 / API 重启 / health
- ⚠️ 问题项：无则写「无」
