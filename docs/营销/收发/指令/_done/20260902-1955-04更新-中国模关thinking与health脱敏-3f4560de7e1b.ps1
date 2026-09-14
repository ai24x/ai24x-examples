$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "3f4560de7e1b"
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
$main = Get-Content (Join-Path $work "api\main.py") -Raw -Encoding UTF8
if ($core -notlike '*_apply_upstream_thinking_controls*') { throw "core missing _apply_upstream_thinking_controls" }
if ($core -notlike '*_cn_thinking_family*') { throw "core missing _cn_thinking_family" }
if ($core -notlike '*_should_inject_thinking_disable*') { throw "core missing inject gate" }
if ($core -notlike '*enable_thinking*') { throw "core missing Qwen enable_thinking" }
if ($open -notlike '*_apply_upstream_thinking_controls*') { throw "open missing _apply_upstream_thinking_controls" }
if ($main -notlike '*不返回上游厂商*') { throw "core /health docstring missing sanitize note" }
if ($main -notlike '*m.pop("upstream_mode"*') { throw "core /v1/models missing upstream_mode strip" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open + core ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("public core commit mismatch: " + $ph.commit) }
if ($null -ne $ph.upstream_mode) { throw "public /health still leaks upstream_mode" }
if ($null -ne $ph.layers) { throw "public /health still leaks layers" }

$py = @"
import sys
sys.path.insert(0, r'C:\ai24x01\api')
from model_router import (
    _apply_upstream_thinking_controls,
    _cn_thinking_family,
    _should_forward_reasoning_to_client,
    _should_inject_thinking_disable,
    _is_thinking_only_upstream,
)
assert _cn_thinking_family('mimo-v2.5', 'mimo') == 'mimo'
assert _should_inject_thinking_disable('mimo-v2.5', 'mimo')
assert _should_inject_thinking_disable('moonshotai/kimi-k3', 'openrouter')
assert _should_inject_thinking_disable('z-ai/glm-5.2', 'openrouter')
assert _should_inject_thinking_disable('qwen/qwen3.7-max', 'openrouter')
assert not _should_inject_thinking_disable('Qwen/Qwen2.5-7B-Instruct', 'siliconflow')
assert _is_thinking_only_upstream('moonshotai/kimi-k2.7-code')
assert not _should_forward_reasoning_to_client()
b = {'messages': [{'role': 'assistant', 'content': 'x', 'reasoning_content': 'SECRET'}]}
_apply_upstream_thinking_controls(b, model='mimo-v2.5', provider='mimo')
assert b.get('thinking') == {'type': 'disabled'}
assert 'reasoning_content' not in b['messages'][0]
print('cn_thinking_gate_ok')
"@
$pyPath = "C:\Users\Administrator\ops\_check_cn_thinking_gate.py"
New-Item -ItemType Directory -Force -Path (Split-Path $pyPath) | Out-Null
Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8
$out = & python $pyPath
if ($out -notlike '*cn_thinking_gate_ok*') { throw ("thinking gate check failed: " + $out) }
Write-Host $out -ForegroundColor Green
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $ph.commit) -ForegroundColor Green
# ✅ 04更新完成｜中国模关thinking+health脱敏｜EXP=3f4560de7e1b HEAD=<HEAD> health=<commit>｜MiMo/Kimi/GLM/Qwen已覆盖｜公网/health无layers