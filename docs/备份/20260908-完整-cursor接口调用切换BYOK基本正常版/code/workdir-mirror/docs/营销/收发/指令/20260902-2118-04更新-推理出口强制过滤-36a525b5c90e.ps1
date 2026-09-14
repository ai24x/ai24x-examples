$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "36a525b5c90e"
Set-Location $work
Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$core = Get-Content "api\reasoning_filter.py" -Raw -Encoding UTF8
$mr = Get-Content "api\model_router.py" -Raw -Encoding UTF8
if ($core -notlike '*extract_client_visible_text*') { throw "missing extract_client_visible_text" }
if ($core -notlike '*ThinkTagStreamScrubber*') { throw "missing ThinkTagStreamScrubber" }
if ($mr -notlike '*extract_client_visible_text*') { throw "model_router missing egress filter" }
if ($mr -notlike '*_INCLUDE_REASONING_CV*') { throw "missing ContextVar" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }
$py = @"
import sys
sys.path.insert(0, r'C:\ai24x01\api')
from reasoning_filter import extract_client_visible_text, stream_delta_visible_piece, ThinkTagStreamScrubber, scrub_think_tags
assert extract_client_visible_text({'content':'ok','reasoning_content':'EN'}) == 'ok'
assert extract_client_visible_text({'content':'','reasoning_content':'EN'}) == ''
assert stream_delta_visible_piece({'reasoning_content':'x'}) is None
assert 'SECRET' not in scrub_think_tags('a<think>SECRET</think>b')
s=ThinkTagStreamScrubber(); o=s.feed('hi<think>X</think>yo')+s.flush(); assert 'X' not in o and 'hi' in o
print('reasoning_egress_ok')
"@
$p='C:\Users\Administrator\ops\_check_reasoning_egress.py'
New-Item -ItemType Directory -Force -Path (Split-Path $p) | Out-Null
Set-Content -LiteralPath $p -Value $py -Encoding UTF8
$out = & python $p
if ($out -notlike '*reasoning_egress_ok*') { throw $out }
Write-Host $out -ForegroundColor Green
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜推理出口强制过滤｜EXP=36a525b5c90e HEAD=<HEAD> health=<commit>｜默认不向客户端回传reasoning