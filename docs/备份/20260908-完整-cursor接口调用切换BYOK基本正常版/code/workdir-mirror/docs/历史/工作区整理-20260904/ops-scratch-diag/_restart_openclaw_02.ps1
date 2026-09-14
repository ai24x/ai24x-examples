$ErrorActionPreference = "Stop"
$env:Path = "C:\Users\Administrator\AppData\Roaming\npm;C:\Program Files\nodejs;" + $env:Path
Write-Host "=== openclaw gateway restart ==="
& openclaw.cmd gateway restart 2>&1 | Out-String | Write-Host
Write-Host "exit=$LASTEXITCODE"
Start-Sleep -Seconds 3
Write-Host "=== processes after ==="
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match 'openclaw\.mjs|openclaw gateway') } |
  ForEach-Object {
    $cl = $_.CommandLine
    if ($cl.Length -gt 200) { $cl = $cl.Substring(0,200) }
    Write-Host ("pid={0} cl={1}" -f $_.ProcessId, $cl)
  }
Write-Host "=== verify config baseUrl ==="
$py = (Get-Command py -ErrorAction SilentlyContinue); if (-not $py) { $py = Get-Command python }
& $py.Source -c "import json;d=json.load(open(r'C:\\Users\\Administrator\\.openclaw\\openclaw.json',encoding='utf-8'));p=d['models']['providers']['ai24x-byok'];print('baseUrl=',p.get('baseUrl'));print('key_pref=',(p.get('apiKey') or '')[:10])"
