$ErrorActionPreference = 'Continue'
$base = 'E:\AI24X\ai24x-website\ai24x01\docs\营销\收发'
Write-Output '=== 指令目录根层 *.txt（排除 _ 开头）==='
$cmds = Get-ChildItem -Path (Join-Path $base '指令') -File -Filter '*.txt' | Where-Object { -not $_.Name.StartsWith('_') }
if ($cmds) { $cmds | Select-Object -ExpandProperty FullName } else { Write-Output '(无)' }
Write-Output '=== 回复目录根层 *.txt（排除 _ 开头）==='
$reps = Get-ChildItem -Path (Join-Path $base '回复') -File -Filter '*.txt' | Where-Object { -not $_.Name.StartsWith('_') }
if ($reps) { $reps | Select-Object -ExpandProperty FullName } else { Write-Output '(无)' }
