$ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
$urls = @(
  'https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=5d',
  'https://query2.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=5d',
  'https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=5d'
)
foreach ($u in $urls) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 15 -Headers @{'User-Agent'=$ua}
    $head = $r.Content
    if ($head.Length -gt 160) { $head = $head.Substring(0,160) }
    Write-Output ("OK  {0} -> HTTP {1} len={2} :: {3}" -f $u, [int]$r.StatusCode, $r.Content.Length, $head)
  } catch {
    Write-Output ("FAIL {0} :: {1}" -f $u, $_.Exception.Message)
  }
}
