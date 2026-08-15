function Test-Url($name, $url, $headers) {
  try {
    if ($headers) {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10 -Headers $headers
    } else {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10
    }
    Write-Output ("OK  {0} -> HTTP {1} len={2}" -f $name, [int]$r.StatusCode, $r.Content.Length)
  } catch {
    Write-Output ("FAIL {0} :: {1}" -f $name, $_.Exception.Message)
  }
}

Test-Url 'Sina-US-Kline' 'https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20_=/US_MinKService.getDailyK?symbol=AAPL' $null
Test-Url 'Sina-US-Quote' 'https://hq.sinajs.cn/list=gb_aapl' @{Referer='https://finance.sina.com.cn'}
