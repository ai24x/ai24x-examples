$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "c7d41c7fc41d"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$core = Get-Content (Join-Path $work "api\openai_compat.py") -Raw -Encoding UTF8
$open = Get-Content (Join-Path $work "p\open\api\openai_compat.py") -Raw -Encoding UTF8
if ($core -notlike '*_default_max_tokens*') { throw "core missing _default_max_tokens" }
if ($core -notlike '*TOKEN_LLM_DEFAULT_MAX_TOKENS*') { throw "core missing env override" }
if ($core -notlike '*8192 if has_tools*') { throw "core missing 8192 tools default" }
if ($open -notlike '*_default_max_tokens*') { throw "open missing _default_max_tokens" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open + core ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("public core commit mismatch: " + $ph.commit) }
$py = @"
import sys
sys.path.insert(0, r'C:\ai24x01\api')
from openai_compat import _default_max_tokens, build_chat_request_schema, build_chat_request_from_responses
assert _default_max_tokens(has_tools=False) == 4096
assert _default_max_tokens(has_tools=True) == 8192
r = build_chat_request_schema({'model':'flash','messages':[{'role':'user','content':'hi'}]})
assert r.max_tokens == 4096
r2 = build_chat_request_from_responses({'model':'flash','input':'hi','tools':[{'type':'function','name':'x','parameters':{}}]})
assert r2.max_tokens == 8192
print('max_tokens_default_ok')
"@
$pyPath = "C:\Users\Administrator\ops\_check_max_tokens_default.py"
New-Item -ItemType Directory -Force -Path (Split-Path $pyPath) | Out-Null
Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8
$out = & python $pyPath
if ($out -notlike '*max_tokens_default_ok*') { throw ("max_tokens check failed: " + $out) }
Write-Host $out -ForegroundColor Green
Write-Host "public verify OK" -ForegroundColor Green
Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $ph.commit) -ForegroundColor Green
# ✅ 04更新完成｜Codex断片max_tokens｜EXP=c7d41c7fc41d HEAD=<HEAD> health=<commit>｜默认4096/8192｜aliases已改本机config