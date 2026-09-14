$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "b616ece7c0a7"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$core = Get-Content (Join-Path $work "api\model_router.py") -Raw -Encoding UTF8
$open = Get-Content (Join-Path $work "p\open\api\model_router.py") -Raw -Encoding UTF8
if ($core -notlike '*_should_disable_deepseek_thinking*') { throw "core model_router missing helper" }
if ($core -notlike '*_is_deepseek_v4_upstream_model*') { throw "core model_router missing v4 detector" }
if ($core -notlike '*disable_ds_thinking*') { throw "core model_router missing disable_ds_thinking" }
if ($open -notlike '*_should_disable_deepseek_thinking*') { throw "open model_router missing helper" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open + core ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("public core commit mismatch: " + $ph.commit) }

# Helper self-check on 04 (no live Codex key required)
$py = @"
import sys
sys.path.insert(0, r'C:\ai24x01\api')
from model_router import _should_disable_deepseek_thinking, _is_deepseek_v4_upstream_model
assert _is_deepseek_v4_upstream_model('deepseek/deepseek-v4-flash')
assert _should_disable_deepseek_thinking('deepseek/deepseek-v4-flash')
assert not _should_disable_deepseek_thinking('openai/gpt-5')
print('thinking_gate_ok')
"@
$pyPath = "C:\Users\Administrator\ops\_check_ds_thinking_gate.py"
Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8
$out = & python $pyPath
if ($out -notlike '*thinking_gate_ok*') { throw ("thinking gate check failed: " + $out) }
Write-Host $out -ForegroundColor Green
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $ph.commit) -ForegroundColor Green
# ✅ 04更新完成｜DeepSeek v4关thinking｜EXP=b616ece7c0a7 HEAD=<HEAD> health=<commit>｜OR前缀模型已覆盖｜Codex可复测Flash
