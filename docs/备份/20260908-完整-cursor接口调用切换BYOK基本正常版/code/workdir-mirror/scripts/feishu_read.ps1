param(
  [int]$PageSize = 8,
  [int]$Minutes = 120
)
# AI24X Feishu reader - pull recent messages from the command group
$cfg = "$env:USERPROFILE\.openclaw\openclaw.json"
if (-not (Test-Path $cfg)) { Write-Error "openclaw.json not found"; exit 1 }
$j = Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
$appId = $j.channels.feishu.appId
$appSecret = $j.channels.feishu.appSecret
$grp = @($j.channels.feishu.groupAllowFrom)[0]
$tokenBody = @{ app_id = $appId; app_secret = $appSecret } | ConvertTo-Json
$tr = Invoke-RestMethod -Uri "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" -Method Post -ContentType "application/json" -Body $tokenBody -TimeoutSec 20
if ($tr.code -ne 0) { Write-Error "token fail: $($tr.msg)"; exit 1 }
$headers = @{ Authorization = "Bearer $($tr.tenant_access_token)" }
$r = Invoke-RestMethod -Uri "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=$grp&page_size=$PageSize&sort_type=ByCreateTimeDesc" -Method Get -Headers $headers -TimeoutSec 20
if ($r.code -ne 0) { Write-Error "read fail: $($r.msg)"; exit 1 }
$cut = (Get-Date).AddMinutes(-$Minutes)
foreach ($it in $r.data.items) {
  $t = [DateTimeOffset]::FromUnixTimeMilliseconds([long]$it.create_time).LocalDateTime
  if ($t -lt $cut) { continue }
  $txt = ""
  try {
    $c = $it.body.content | ConvertFrom-Json
    if ($it.msg_type -eq "text") { $txt = $c.text }
    elseif ($c.content) { $txt = (($c.content | ConvertTo-Json -Compress -Depth 5)) }
  } catch { $txt = $it.body.content }
  if ($txt.Length -gt 200) { $txt = $txt.Substring(0,200) + "..." }
  Write-Output "[$($t.ToString('HH:mm:ss'))] $($it.sender.id_type): $txt"
}