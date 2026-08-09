param(
  [Parameter(Mandatory=$true)][string]$Msg,
  [ValidateSet("user","group")][string]$To = "user",
  [string]$AtId = "",
  [string]$AtName = "AI24X指挥"
)
# AI24X Feishu sender - reads app credentials from ~/.openclaw/openclaw.json
$cfg = "$env:USERPROFILE\.openclaw\openclaw.json"
if (-not (Test-Path $cfg)) { Write-Error "openclaw.json not found"; exit 1 }
$j = Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
$appId = $j.channels.feishu.appId
$appSecret = $j.channels.feishu.appSecret
if ($To -eq "group") {
  $rid = @($j.channels.feishu.groupAllowFrom)[0]
  $rtype = "chat_id"
} else {
  $rid = @($j.channels.feishu.allowFrom)[0]
  $rtype = "open_id"
}
if ($AtId) { $Msg = '<at user_id="' + $AtId + '">' + $AtName + '</at> ' + $Msg }
# 用 ConvertTo-Json 生成 content 双层 JSON，正确处理引号/反斜杠/换行
$contentVal = @{ text = $Msg } | ConvertTo-Json -Compress -Depth 5
$body = @{ receive_id = $rid; msg_type = "text"; content = $contentVal } | ConvertTo-Json -Compress -Depth 5
$tokenBody = @{ app_id = $appId; app_secret = $appSecret } | ConvertTo-Json
$tr = Invoke-RestMethod -Uri "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" -Method Post -ContentType "application/json" -Body $tokenBody -TimeoutSec 20
if ($tr.code -ne 0) { Write-Error "token fail: $($tr.msg)"; exit 1 }
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$headers = @{ Authorization = "Bearer $($tr.tenant_access_token)" }
$sr = Invoke-RestMethod -Uri "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=$rtype" -Method Post -Headers $headers -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec 20
if ($sr.code -eq 0) { Write-Output "sent to $To : $($sr.data.message_id)" } else { Write-Error "send fail: $($sr.msg)"; exit 1 }