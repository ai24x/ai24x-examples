$ErrorActionPreference = 'Continue'
$base = 'E:\AI24X\ai24x-website\ai24x01\docs\营销\收发'
function Get-HashOf($p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash }

Write-Output "===== START 回复 root vs _sent ====="
$replyFiles = Get-ChildItem -Path (Join-Path $base '回复') -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' }
Write-Output ("reply root count: " + $replyFiles.Count)
foreach ($f in $replyFiles) {
  $sent = Join-Path (Join-Path $base '回复\_sent') $f.Name
  if (Test-Path -LiteralPath $sent) {
    $h1 = Get-HashOf $f.FullName; $h2 = Get-HashOf $sent
    $same = if ($h1 -eq $h2) { 'IDENTICAL' } else { 'DIFFERS' }
    Write-Output ("{0} | size={1} | sent={2}" -f $f.Name, $f.Length, $same)
  } else {
    Write-Output ("{0} | size={1} | sent=NONE" -f $f.Name, $f.Length)
  }
}

Write-Output ""
Write-Output "===== START 指令 root ====="
$instFiles = Get-ChildItem -Path (Join-Path $base '指令') -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' }
Write-Output ("inst root count: " + $instFiles.Count)
foreach ($f in $instFiles) {
  $baseName = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
  $outNames = @("$($f.Name)-out.txt", "$baseName-out.txt")
  $found = @()
  foreach ($n in $outNames) {
    if (Test-Path -LiteralPath (Join-Path $base (Join-Path '回复' $n))) { $found += "回复root:$n" }
    if (Test-Path -LiteralPath (Join-Path $base (Join-Path '回复\_sent' $n))) { $found += "_sent:$n" }
  }
  $foundStr = if ($found.Count -gt 0) { ($found -join ', ') } else { 'NO -out reply' }
  Write-Output ("{0} | size={1} | {2}" -f $f.Name, $f.Length, $foundStr)
}
Write-Output "===== END ====="
