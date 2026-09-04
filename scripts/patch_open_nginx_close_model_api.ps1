# Patch open.ai24x.com nginx: hard-close public model API endpoints.
# Keep console/static + billing/byok/auth/admin via location /
# Core BYOK bridge uses http://127.0.0.1:18080 (bypasses nginx) — unaffected.
$ErrorActionPreference = "Stop"
$conf = "C:\nginx\conf\nginx.conf"
if (-not (Test-Path $conf)) { throw "nginx.conf missing: $conf" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bak = "C:\nginx\conf\nginx.conf.bak-open-api-hub-$stamp"
Copy-Item -LiteralPath $conf -Destination $bak -Force
Write-Host "backup=$bak"

$marker = "BYOK 2026-09-04: public model API closed"
$text = [IO.File]::ReadAllText($conf)
if ($text.Contains($marker)) {
  Write-Host "already patched; skip insert"
} else {
  $block = @"

        # $marker — use api.ai24x.com/v1 + Hub key
        location ~ ^/v1/(chat/completions|chat/run|responses|models)(/|$) {
            default_type application/json;
            add_header Content-Type "application/json; charset=utf-8" always;
            return 410 '{"error":{"message":"Please use https://api.ai24x.com/v1 with your Hub API key. open.ai24x.com is for console and BYOK key management only.","type":"invalid_request_error","code":"endpoint_moved"}}';
        }
"@
  $parts = [regex]::Split($text, '(?=^\s*server\s*\{)', [System.Text.RegularExpressions.RegexOptions]::Multiline)
  $out = New-Object System.Text.StringBuilder
  $patched = $false
  foreach ($part in $parts) {
    $isOpen443 = ($part -match 'server_name\s+open\.ai24x\.com') -and ($part -match 'listen\s+443')
    if ($isOpen443) {
      if ($part.Contains($marker)) {
        [void]$out.Append($part)
        $patched = $true
      } else {
        $p2 = [regex]::Replace($part, '(\r?\n)([ \t]*location\s+/\s*\{)', ("`$1" + $block + "`r`n`$2"), 1)
        if ($p2 -eq $part) { throw "failed to insert location block into open 443 server" }
        [void]$out.Append($p2)
        $patched = $true
      }
    } else {
      [void]$out.Append($part)
    }
  }
  if (-not $patched) { throw "open 443 server block not found/patched" }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [IO.File]::WriteAllText($conf, $out.ToString(), $utf8)
  Write-Host "nginx.conf written"
}

$nginx = "C:\nginx\nginx.exe"
if (-not (Test-Path $nginx)) { throw "nginx.exe missing" }
$test = & $nginx -t 2>&1 | Out-String
Write-Host $test
if ($LASTEXITCODE -ne 0) {
  Copy-Item -LiteralPath $bak -Destination $conf -Force
  throw "nginx -t failed; restored backup"
}
& $nginx -s reload 2>&1 | Out-String | Write-Host
Write-Host "nginx reloaded OK backup=$bak"
