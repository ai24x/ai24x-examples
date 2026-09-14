$ErrorActionPreference = "Stop"
$base = "E:\AI24X\ai24x-website\ai24x01\docs\营销\收发"

function Dump-Dir($dir, $label) {
  Write-Output "========== $label =========="
  Get-ChildItem -LiteralPath $dir -File -Filter *.txt | Where-Object { $_.Name -notlike "_*" } | ForEach-Object {
    Write-Output "----- FILE: $($_.Name) (size=$($_.Length), mtime=$($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))) -----"
    $content = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
    Write-Output $content
    Write-Output ""
  }
}

Dump-Dir "$base\指令" "指令"
Dump-Dir "$base\回复" "回复"
