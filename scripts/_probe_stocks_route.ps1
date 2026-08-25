$ErrorActionPreference = "Continue"
$q = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
foreach ($u in @(
  "https://markets.ai24x.com/stocks/nvda?x=$q",
  "https://markets.ai24x.com/stocks/nvda",
  "https://markets.ai24x.com/stocks/NVDA?x=$q",
  "https://markets.ai24x.com/stocks/tsla?x=$q",
  "https://markets.ai24x.com/stocks/googl?x=$q",
  "https://markets.ai24x.com/stocks/nflx?x=$q"
)) {
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 20
    $has = $r.Content.Contains("rel=""canonical""")
    "{0} -> {1} canon={2} len={3}" -f $u, $r.StatusCode, $has, $r.Content.Length
  } catch {
    "{0} -> ERROR {1}" -f $u, $_.Exception.Message
  }
}
Write-Output "DONE"
