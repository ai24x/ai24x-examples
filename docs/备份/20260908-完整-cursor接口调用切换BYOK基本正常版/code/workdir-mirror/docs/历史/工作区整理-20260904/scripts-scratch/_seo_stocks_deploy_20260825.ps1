$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$conf = "C:\nginx\conf\nginx.conf"
$stage = "C:\Users\Administrator\ops\seo-stocks-20260825"
$siteRoot = "C:\sites\markets.ai24x.com"
$nginxExe = "C:\nginx\nginx.exe"
$marker = "# SEO /stocks/ route 2026-08-25"

# 1) backup nginx.conf
Copy-Item $conf "$conf.bak-$ts" -Force
Write-Output "BACKUP nginx.conf.bak-$ts"

# 2) insert /stocks/ location into markets 443 block (idempotent)
$txt = [System.IO.File]::ReadAllText($conf, [System.Text.Encoding]::UTF8)
if ($txt.Contains($marker)) {
  Write-Output "SKIP insert (marker exists)"
} else {
  $anchor = "access_log logs/markets.ai24x.com.access.log;"
  $idx = $txt.IndexOf($anchor)
  if ($idx -lt 0) { throw "anchor not found: markets access_log" }
  $block = "        # SEO /stocks/ route 2026-08-25`n" +
           "        location ^~ /stocks/ {`n" +
           "            rewrite ^/stocks/([a-zA-Z0-9._-]+)/?$ /seo/`$1.html last;`n" +
           "            rewrite ^/stocks/?$ /seo/index.html last;`n" +
           "        }`n`n"
  $txt = $txt.Substring(0, $idx) + $block + $txt.Substring($idx)
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($conf, $txt, $utf8NoBom)
  Write-Output "INSERT /stocks/ location"
}

# 3) nginx -t (cmd wrapper merges stderr so PS does not treat as error)
$tOut = & cmd.exe /c "`"$nginxExe`" -t -p C:\nginx\ -c C:\nginx\conf\nginx.conf 2>&1"
$tOut | Out-String | Write-Output
if ($LASTEXITCODE -ne 0) { throw "nginx -t failed" }

# 4) reload
$rOut = & cmd.exe /c "`"$nginxExe`" -s reload -p C:\nginx\ -c C:\nginx\conf\nginx.conf 2>&1"
$rOut | Out-String | Write-Output
Write-Output "NGINX RELOADED exit=$LASTEXITCODE"

# 5) backup + sync seo stock pages + sitemap
$bakDir = "C:\Users\Administrator\ops\.bak-seo-stocks-$ts"
New-Item -ItemType Directory -Path $bakDir -Force | Out-Null
Get-ChildItem "$stage\*.html" | ForEach-Object {
  $dest = Join-Path "$siteRoot\seo" $_.Name
  if (Test-Path $dest) { Copy-Item $dest (Join-Path $bakDir $_.Name) -Force }
  Copy-Item $_.FullName $dest -Force
  Write-Output ("SYNC seo/{0}" -f $_.Name)
}
if (Test-Path "$stage\sitemap.xml") {
  Copy-Item "$siteRoot\sitemap.xml" (Join-Path $bakDir "sitemap.xml") -Force -ErrorAction SilentlyContinue
  Copy-Item "$stage\sitemap.xml" "$siteRoot\sitemap.xml" -Force
  Write-Output "SYNC sitemap.xml"
}

# 6) ledger note: append Discord status to accounts-registry.md
$reg = "C:\Users\Administrator\ops\accounts-registry.md"
$noteFile = "$stage\ledger-note.md"
if (Test-Path $noteFile) {
  $note = [System.IO.File]::ReadAllText($noteFile, [System.Text.Encoding]::UTF8)
  $old = [System.IO.File]::ReadAllText($reg, [System.Text.Encoding]::UTF8)
  if (-not $old.Contains("ai24xgo")) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($reg, $old.TrimEnd() + "`r`n" + $note, $utf8NoBom)
    Write-Output "LEDGER updated"
  } else {
    Write-Output "LEDGER already has ai24xgo"
  }
}

# 7) QA
function Probe($url, $needle) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20
    $ok = if ($needle) { $r.Content.Contains($needle) } else { $true }
    "{0} -> {1} needle={2} len={3}" -f $url, $r.StatusCode, $ok, $r.Content.Length
  } catch {
    "{0} -> ERROR {1}" -f $url, $_.Exception.Message
  }
}
Probe "https://markets.ai24x.com/stocks/nvda" "rel=""canonical"" href=""https://markets.ai24x.com/stocks/nvda"""
Probe "https://markets.ai24x.com/stocks/aapl" "rel=""canonical"" href=""https://markets.ai24x.com/stocks/aapl"""
Probe "https://markets.ai24x.com/stocks/NVDA" $null
Probe "https://markets.ai24x.com/seo/nvda.html" $null
Probe "https://markets.ai24x.com/sitemap.xml" "stocks/nvda"
Probe "https://markets.ai24x.com/stocks/" "AI24X Markets"
Write-Output "DONE"
