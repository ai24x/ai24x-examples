# S8：让 /stocks/{sym}.html 与 /stocks/{sym} 双通（映射到 /seo/{sym}.html）
# 在装有生产 nginx 的机器执行（本机若无 C:\nginx 则跳过）。
# 幂等：已有 marker 则只补 .html rewrite。
$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$conf = "C:\nginx\conf\nginx.conf"
$nginxExe = "C:\nginx\nginx.exe"
$markerHtml = "# SEO /stocks/ .html alias 2026-09-08"

if (-not (Test-Path $conf)) {
  Write-Output "SKIP: nginx.conf not found at $conf (run on prod nginx host)"
  exit 0
}

Copy-Item $conf "$conf.bak-s8-$ts" -Force
Write-Output "BACKUP $conf.bak-s8-$ts"

$txt = [System.IO.File]::ReadAllText($conf, [System.Text.Encoding]::UTF8)
if ($txt.Contains($markerHtml)) {
  Write-Output "SKIP insert (html alias marker exists)"
} else {
  # 优先插在已有 /stocks/ location 内；若无则整块插入
  $htmlRewrite = "            # SEO /stocks/ .html alias 2026-09-08`n" +
                 "            rewrite ^/stocks/([a-zA-Z0-9._-]+)\.html$ /seo/`$1.html last;`n"
  $stocksOpen = "location ^~ /stocks/ {"
  $idx = $txt.IndexOf($stocksOpen)
  if ($idx -ge 0) {
    $brace = $txt.IndexOf("{", $idx)
    if ($brace -lt 0) { throw "stocks location brace not found" }
    $insertAt = $brace + 1
    $txt = $txt.Substring(0, $insertAt) + "`n" + $htmlRewrite + $txt.Substring($insertAt)
    Write-Output "PATCH existing /stocks/ location with .html rewrite"
  } else {
    $anchor = "access_log logs/markets.ai24x.com.access.log;"
    $aidx = $txt.IndexOf($anchor)
    if ($aidx -lt 0) { throw "anchor not found: markets access_log" }
    $block = "        # SEO /stocks/ route + .html alias 2026-09-08`n" +
             "        location ^~ /stocks/ {`n" +
             $htmlRewrite +
             "            rewrite ^/stocks/([a-zA-Z0-9._-]+)/?$ /seo/`$1.html last;`n" +
             "            rewrite ^/stocks/?$ /seo/index.html last;`n" +
             "        }`n`n"
    $txt = $txt.Substring(0, $aidx) + $block + $txt.Substring($aidx)
    Write-Output "INSERT full /stocks/ location with .html alias"
  }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($conf, $txt, $utf8NoBom)
}

$tOut = & cmd.exe /c "`"$nginxExe`" -t -p C:\nginx\ -c C:\nginx\conf\nginx.conf 2>&1"
$tOut | Out-String | Write-Output
if ($LASTEXITCODE -ne 0) { throw "nginx -t failed" }

$rOut = & cmd.exe /c "`"$nginxExe`" -s reload -p C:\nginx\ -c C:\nginx\conf\nginx.conf 2>&1"
$rOut | Out-String | Write-Output
Write-Output "NGINX RELOADED exit=$LASTEXITCODE"

# 探测
function Probe([string]$url) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20
    Write-Output ("OK {0} -> {1}" -f $url, [int]$r.StatusCode)
  } catch {
    Write-Output ("FAIL {0} -> {1}" -f $url, $_.Exception.Message)
  }
}
Probe "https://markets.ai24x.com/stocks/nvda"
Probe "https://markets.ai24x.com/stocks/nvda.html"
Probe "https://markets.ai24x.com/seo/nvda.html"
