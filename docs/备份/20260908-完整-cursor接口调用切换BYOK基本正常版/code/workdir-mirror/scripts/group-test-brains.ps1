param(
  [string[]]$Brains = @('01','02','03','04'),
  [string]$MessageText = ""
)
$ErrorActionPreference = 'Continue'
$ips   = @{ '01'='42.192.1.93'; '02'='118.89.111.23'; '03'='123.207.199.238'; '04'='43.160.246.30' }
$names = @{ '01'='AI24X游戏'; '02'='AI24X运营'; '03'='AI24X行情官'; '04'='AI24X国际token' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
if (-not $MessageText) { $MessageText = "✅ <脑名> 已接收 V2 作战体系 + 今日目标，群测回执 $stamp" }

$jobs = @()
foreach ($b in $Brains) {
  $ip = $ips[$b]; $nm = $names[$b]
  $task = "【司令群测 · $(Get-Date -Format 'yyyy-MM-dd HH:mm')】`n你是 $nm。现在用你的飞书应用向指挥部群（chat_id: oc_9b52710ed906aa19dbad7edf71cffa18）发送一条群消息，内容如下：`n$($MessageText.Replace('<脑名>', $nm))`n要求：`n1. 只做这一件事，不要读其他文件、不要做任何其他检查；`n2. 发送成功后，输出 SENT_OK（附消息内容）；失败则输出 SENT_FAIL（附原因），不重试超过 1 次。"
  $tf = "$env:TEMP\grouptest-$b-$stamp.txt"
  [System.IO.File]::WriteAllText($tf, $task, (New-Object System.Text.UTF8Encoding($false)))
  $h = "Administrator@$ip"
  $remote = "C:\Users\Administrator\ops\grouptest-$b-$stamp.txt"
  $jobs += Start-Job -Name "brain-$b" -ScriptBlock {
    param($h, $tf, $remote)
    scp -o ConnectTimeout=15 -o BatchMode=yes $tf "${h}:$remote" 2>&1 | Out-Null
    ssh -o ConnectTimeout=15 -o BatchMode=yes $h "openclaw agent --agent main --message-file $remote --json --timeout 300" 2>&1
  } -ArgumentList $h, $tf, $remote
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
Write-Output "并行驱动 $($jobs.Count) 个脑，等待回执..."
Wait-Job $jobs -Timeout 420 | Out-Null
$sw.Stop()
foreach ($j in $jobs) {
  $out = Receive-Job $j -ErrorAction SilentlyContinue | Out-String
  $sent = (@([regex]::Matches($out, 'SENT_OK|SENT_FAIL') | ForEach-Object { $_.Value }) | Select-Object -Unique) -join ','
  $target = (@([regex]::Matches($out, '"to":\s*"(oc_[a-z0-9]+)"') | ForEach-Object { $_.Groups[1].Value }) | Select-Object -Unique) -join ','
  Write-Output ("Brain {0}: 结果={1} 群目标={2}" -f $j.Name, $sent, $target)
  Remove-Job $j -Force
}
Write-Output ("总耗时: {0:N1}s" -f $sw.Elapsed.TotalSeconds)
