$log = "C:\Users\Administrator\ops\task03-trigger.log"
$err = "C:\Users\Administrator\ops\task03-trigger-err.log"
Start-Process -FilePath "openclaw.cmd" -ArgumentList @("agent","--agent","main","--message-file","C:\Users\Administrator\ops\任务书-03-市场已验证类型榜.md","--timeout","900") -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err
Start-Sleep -Seconds 2
Write-Output "dispatched"
