$ErrorActionPreference = 'Stop'
$base = 'E:\AI24X\ai24x-website\ai24x01\docs\营销\收发'
$replyDir = Join-Path $base '回复'
$files = @(
  '2026-08-09-2318-司令-回执Codex案例更新.txt',
  '2026-08-09-2347-主脑-回执司令-新规确认.txt',
  '2026-08-10-0046-主脑-回执司令-Codex切模型规划.txt',
  '2026-08-09-0235-司令在线回执.txt',
  '2026-08-09-0115-司令-确认回执.txt',
  '2026-08-09-1046-司令-回执Gitee凭据同步.txt'
)
foreach ($f in $files) {
  Write-Output ('===== ' + $f + ' =====')
  $p = Join-Path $replyDir $f
  if (Test-Path -LiteralPath $p) {
    Get-Content -LiteralPath $p -Raw -Encoding UTF8
  } else {
    Write-Output '(not found)'
  }
  Write-Output ''
}
