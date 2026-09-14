$ErrorActionPreference = "Continue"
$log = "E:\AI24X\ai24x-website\ai24x01\ops\deploy04-9845592.log"
ssh -o ConnectTimeout=20 -o StrictHostKeyChecking=no -o BatchMode=yes Administrator@43.160.246.30 "openclaw agent --agent main --message-file C:\Users\Administrator\ops\task-04-deploy-9845592.md --json --timeout 600" *> $log
Write-Output "DONE exit=$LASTEXITCODE" >> $log