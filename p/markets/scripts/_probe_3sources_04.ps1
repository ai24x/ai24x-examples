$ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'

function Test-Url($name, $url, $headers) {
  try {
    if ($headers) {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5 -Headers $headers
    } else {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
    }
    Write-Output ("OK  {0} -> HTTP {1} len={2}" -f $name, [int]$r.StatusCode, $r.Content.Length)
  } catch {
    Write-Output ("FAIL {0} :: {1}" -f $name, $_.Exception.Message)
  }
}

Test-Url 'TX-US-Kline' 'https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param=usAAPL,day,,,5,qfq' $null
Test-Url 'TX-US-Quote' 'https://qt.gtimg.cn/q=usAAPL' $null
Test-Url 'EM-US-Kline' 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=105.AAPL&klt=101&fqt=1&lmt=5&end=20500101&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57' $null
Test-Url 'EM-US-Quote' 'https://push2.eastmoney.com/api/qt/stock/get?secid=105.AAPL&fields=f43,f57,f58,f60,f116,f117,f162,f167,f170' $null
Test-Url 'Sina-US-Kline' 'https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20_=/US_MinKService.getDailyK?symbol=AAPL' $null
Test-Url 'Sina-US-Quote' 'https://hq.sinajs.cn/list=gb_aapl' @{Referer='https://finance.sina.com.cn'}
