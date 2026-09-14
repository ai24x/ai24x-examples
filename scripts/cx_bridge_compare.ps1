$ErrorActionPreference = 'SilentlyContinue'
$base = 'E:\AI24X\ai24x-website\ai24x01\docs\营销\收发'
function Get-HashOf($p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash }

Write-Output "===== 回复 root vs _sent ====="
Get-ChildItem -Path "$base\回复" -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' } | ForEach-Object {
  $sent = Join-Path "$base\回复\_sent" $_.Name
  if (Test-Path -LiteralPath $sent) {
    $h1 = Get-HashOf $_.FullName; $h2 = Get-HashOf $sent
    $same = if ($h1 -eq $h2) { 'IDENTICAL' } else { 'DIFFERS' }
    "{0} | size={1} | sent={2}" -f $_.Name, $_.Length, $same
  } else {
    "{0} | size={1} | sent=NONE" -f $_.Name, $_.Length
  }
}

Write-Output ""
Write-Output "===== 指令 root, matching reply files in 回复 root or _sent ====="
Get-ChildItem -Path "$base\指令" -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' } | ForEach-Object {
  $baseName = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
  $outNames = @("$($_.Name)-out.txt", "$baseName-out.txt")
  $found = @()
  foreach ($n in $outNames) {
    if (Test-Path -LiteralPath (Join-Path "$base\回复" $n)) { $found += "回复root:$n" }
    if (Test-Path -LiteralPath (Join-Path "$base\回复\_sent" $n)) { $found += "_sent:$n" }
  }
  $foundStr = if ($found.Count -gt 0) { ($found -join ', ') } else { 'NO -out reply' }
  "{0} | size={1} | {2}" -f $_.Name, $_.Length, $foundStr
}
