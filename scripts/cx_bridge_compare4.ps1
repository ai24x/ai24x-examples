param([string]$Base)
$ErrorActionPreference = 'Continue'
$instDir = $Base + [string]([char]0x5C) + [char]0x6307 + [char]0x4EE4   # \指令
$replyDir = $Base + [string]([char]0x5C) + [char]0x56DE + [char]0x590D  # \回复
$sentDir = $replyDir + [string]([char]0x5C) + '_sent'
function Get-HashOf($p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash }

Write-Output "===== START reply root vs _sent ====="
$replyFiles = Get-ChildItem -Path $replyDir -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' }
Write-Output ("reply root count: " + $replyFiles.Count)
foreach ($f in $replyFiles) {
  $sent = Join-Path $sentDir $f.Name
  if (Test-Path -LiteralPath $sent) {
    $h1 = Get-HashOf $f.FullName; $h2 = Get-HashOf $sent
    $same = if ($h1 -eq $h2) { 'IDENTICAL' } else { 'DIFFERS' }
    Write-Output ("{0} | size={1} | sent={2}" -f $f.Name, $f.Length, $same)
  } else {
    Write-Output ("{0} | size={1} | sent=NONE" -f $f.Name, $f.Length)
  }
}

Write-Output ""
Write-Output "===== START inst root ====="
$instFiles = Get-ChildItem -Path $instDir -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' }
Write-Output ("inst root count: " + $instFiles.Count)
foreach ($f in $instFiles) {
  $baseName = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
  $outNames = @("$($f.Name)-out.txt", "$baseName-out.txt")
  $found = @()
  foreach ($n in $outNames) {
    if (Test-Path -LiteralPath (Join-Path $replyDir $n)) { $found += "replyroot:$n" }
    if (Test-Path -LiteralPath (Join-Path $sentDir $n)) { $found += "_sent:$n" }
  }
  $foundStr = if ($found.Count -gt 0) { ($found -join ', ') } else { 'NO -out reply' }
  Write-Output ("{0} | size={1} | {2}" -f $f.Name, $f.Length, $foundStr)
}
Write-Output "===== END ====="
