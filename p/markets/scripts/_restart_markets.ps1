$py = 'C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe'
$wd = 'E:\AI24X\ai24x-website\ai24x01\p\markets\api\server'
if (-not $env:MARKETS_FULFILL_SECRET) {
  $envLine = Select-String -Path 'E:\AI24X\ai24x-website\ai24x01\api\.env' -Pattern '^MARKETS_FULFILL_SECRET=' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($envLine) {
    $env:MARKETS_FULFILL_SECRET = ($envLine.Line -split '=', 2)[1].Trim()
  }
}
Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18012') -WorkingDirectory $wd -WindowStyle Hidden -RedirectStandardOutput (Join-Path $wd 'uvicorn-18012.out.log') -RedirectStandardError (Join-Path $wd 'uvicorn-18012.err.log')
Start-Sleep -Seconds 5
try {
  $r = Invoke-RestMethod -Uri 'http://127.0.0.1:18012/api/score?symbol=AAPL&period=day' -UseBasicParsing -TimeoutSec 12
  Write-Output ("MARKETS_OK score=" + $r.data.score)
} catch {
  Write-Output ("MARKETS_FAIL: " + $_.Exception.Message)
}
