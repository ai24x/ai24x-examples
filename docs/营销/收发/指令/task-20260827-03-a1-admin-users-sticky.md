# 03 更新指令：管理后台用户页右侧管理卡置顶（admin sticky）

> 派发：司令 → 03（a.ai24x.com）· 无 DB 迁移 · 仅 `admin_ui.py`
> ⚠️ 03 无 D 盘：备份落 `C:\backup\ai24x_a\`；禁止改 `.env`

## 问题
`https://a.ai24x.com/admin20260501#p-users` 右侧管理卡片被长用户表顶到下方；本地用户少/窗口宽时不明显。

## 本包内容

| 路径 | 改动 |
|------|------|
| `p/a1/api/server/app/admin_ui.py` | 右栏 sticky 置顶；左表限高滚动；窄屏单列时管理卡 `order:-1` 仍在上方 |

目标 commit：`__COMMIT__`（推送后由司令填入；03 以本指令内 Step1 的 SHA 为准）

## Step 0 备份
```powershell
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$bk = "C:\backup\ai24x_a\a1-admin-sticky-$stamp"
New-Item -ItemType Directory -Force -Path $bk | Out-Null
$f = "C:\ai24x01\p\a1\api\server\app\admin_ui.py"
if (Test-Path $f) { Copy-Item -LiteralPath $f -Destination (Join-Path $bk "admin_ui.py") -Force }
Write-Output ("backup ok -> " + $bk)
```

## Step 1 git pull + 校验
```powershell
Set-Location C:\ai24x01
git fetch gitee master --quiet
git pull --ff-only gitee master 2>&1 | Select-Object -Last 8
$HEAD = (git rev-parse HEAD).Trim()
Write-Output ("HEAD=" + $HEAD)
$NEED = "__COMMIT__"
if (-not (git merge-base --is-ancestor $NEED HEAD)) { throw ("目标 commit 不在 HEAD: " + $NEED) }
Select-String -Path p\a1\api\server\app\admin_ui.py -Pattern "users-pane" | Select-Object -First 2
Select-String -Path p\a1\api\server\app\admin_ui.py -Pattern "position: sticky" | Select-Object -First 3
Write-Output "commit check PASS"
```

## Step 2 重启 a1-api
```powershell
Restart-Service AI24X-a1-api -Force
Start-Sleep -Seconds 10
$svc = Get-CimInstance Win32_Service -Filter "Name='AI24X-a1-api'"
Write-Output ("state=" + $svc.State + " pid=" + $svc.ProcessId)
try {
  $h = Invoke-RestMethod -Uri "https://a.ai24x.com/health" -UseBasicParsing -TimeoutSec 20
  Write-Output ("health=" + ($h | ConvertTo-Json -Compress))
} catch { Write-Output ("health fail: " + $_.Exception.Message) }
```

## Step 3 行为验收
1. 打开 `https://a.ai24x.com/admin20260501#p-users`（硬刷新一次，让 ui_build 更新）
2. 用户列表较长时：右侧「当前用户 / 配额套餐」管理区应在视口上方可见（sticky），不应被整表顶到最底部
3. 浏览器窗口缩窄到单列时：管理卡仍应出现在用户表上方

## Step 4 回执（飞书群）
- ✅ HEAD=…、users-pane / sticky 命中、API 重启、health ok
- ✅ 页面目视：右栏置顶/窄屏管理卡在上
- ⚠️ 问题项：无则写「无」
