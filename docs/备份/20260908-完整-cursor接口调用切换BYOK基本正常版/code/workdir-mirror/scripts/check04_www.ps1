$ErrorActionPreference = 'SilentlyContinue'
Write-Output '--- 04 curl www.ai24x.com/product.html ---'
try { $r = Invoke-WebRequest -Uri 'https://www.ai24x.com/product.html' -UseBasicParsing -TimeoutSec 20; $hasVip = $r.Content -match 'matrix\.vip|名模清单'; $hasOld = $r.Content -match 'matrix\.more'; Write-Output ('status=' + $r.StatusCode + ' hasVIP=' + $hasVip + ' hasOld=' + $hasOld) } catch { Write-Output ('ERR: ' + $_.Exception.Message) }
Write-Output '--- 04 curl www.ai24x.com/ ---'
try { $r2 = Invoke-WebRequest -Uri 'https://www.ai24x.com/' -UseBasicParsing -TimeoutSec 20; $hasLink = $r2.Content -match 'tag tag-value" href="pricing\.html'; Write-Output ('status=' + $r2.StatusCode + ' hasTagLink=' + $hasLink) } catch { Write-Output ('ERR: ' + $_.Exception.Message) }