$ErrorActionPreference = "SilentlyContinue"
$out = @()
$out += "=== ops subdirs ==="
Get-ChildItem "C:\Users\Administrator\ops" -Directory | ForEach-Object { $out += $_.Name }
$out += "=== seo-pending files ==="
foreach ($p in @("C:\Users\Administrator\ops\seo-pending","C:\Users\Administrator\ops\seo\pending","C:\Users\Administrator\ops\seo-drafts-20260821")) {
  if (Test-Path $p) {
    $files = Get-ChildItem $p -File -ErrorAction SilentlyContinue
    $out += "PATH=$p COUNT=$($files.Count)"
    $files | Select-Object -First 5 | ForEach-Object { $out += "  $($_.Name) LEN=$($_.Length)" }
  } else { $out += "PATH=$p MISSING" }
}
$out += "=== www stocks path ==="
foreach ($p in @("C:\ai24x01\web\stocks","C:\ai24x01\web\stocks\index.html","C:\sites\markets.ai24x.com\stocks")) {
  $out += "PATH=$p EXISTS=$(Test-Path $p)"
}
$out += "=== sitemap ==="
foreach ($p in @("C:\ai24x01\web\sitemap.xml","C:\nginx\html\sitemap.xml")) {
  if (Test-Path $p) { $f=Get-Item $p; $out += "PATH=$p LEN=$($f.Length) T=$($f.LastWriteTime)" } else { $out += "PATH=$p MISSING" }
}
$out | Out-File -FilePath "C:\Users\Administrator\ops\_probe04.txt" -Encoding UTF8
