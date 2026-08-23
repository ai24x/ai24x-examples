$ErrorActionPreference = "Continue"
function Show-Plans($label, $url) {
  try {
    $j = Invoke-RestMethod -Uri $url -TimeoutSec 20 -UseBasicParsing
    $byok = @()
    foreach ($p in @($j.byok_plans)) {
      $byok += ($p.plan + "=" + $p.price_usd + " enabled=" + $p.enabled)
    }
    Write-Output ("[PLANS] " + $label + " byok_count=" + @($j.byok_plans).Count + " token_count=" + @($j.plans).Count)
    Write-Output ("[PLANS] " + $label + " byok=" + ($byok -join " | "))
    Write-Output ("[PLANS] " + $label + " dodo_configured=" + $j.pay.dodo_configured + " dodo_ready=" + $j.pay.dodo_ready + " dodo_mode=" + $j.pay.dodo_mode)
  } catch {
    Write-Output ("[PLANS] " + $label + " ERROR " + $_.Exception.Message)
  }
}

Show-Plans "public" "https://open.ai24x.com/v1/billing/plans"
Show-Plans "local18080" "http://127.0.0.1:18080/v1/billing/plans"

$ov1 = "C:\ai24x01\p\open\api\data\byok_plans_override.json"
$ov2 = "C:\ai24x01\p\open\api\data\token_plans_override.json"
foreach ($f in @($ov1, $ov2)) {
  if (Test-Path $f) {
    Write-Output ("[OVERRIDE] " + $f)
    Get-Content -LiteralPath $f -Encoding UTF8 | Select-Object -First 40
  } else {
    Write-Output ("[OVERRIDE] MISSING " + $f)
  }
}

try {
  $m = Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/admin/auth/mode" -TimeoutSec 15 -UseBasicParsing
  Write-Output ("[ADMIN-MODE] core require_sms=" + $m.require_sms + " sms_enabled=" + $m.sms_enabled + " sms_key_configured=" + $m.sms_key_configured)
} catch {
  Write-Output ("[ADMIN-MODE] core ERROR " + $_.Exception.Message)
}

foreach ($envf in @("C:\ai24x01\api\.env", "C:\ai24x01\p\open\api\.env")) {
  Write-Output ("[ENV] " + $envf)
  if (-not (Test-Path $envf)) { Write-Output "  MISSING"; continue }
  Select-String -LiteralPath $envf -Pattern "^ADMIN_|^DODO_" | ForEach-Object {
    $line = $_.Line
    $eq = $line.IndexOf("=")
    if ($eq -gt 0) {
      $k = $line.Substring(0, $eq)
      $v = $line.Substring($eq + 1)
      $short = if ($v.Length -gt 6) { $v.Substring(0, 6) } else { $v }
      Write-Output ("  " + $k + "=" + $short + "...")
    } else {
      Write-Output ("  " + $line)
    }
  }
}
