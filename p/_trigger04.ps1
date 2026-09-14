$ErrorActionPreference = 'Continue'
$log = "C:\Users\Administrator\ops\task-20260911-04-marketing-push.log"
$taskFile = "C:\Users\Administrator\ops\task-20260911-04-marketing-push.md"
$out = openclaw agent --agent main --message-file $taskFile --json --timeout 600 2>&1
$code = $LASTEXITCODE
"openclaw exit=$code" | Out-File $log -Encoding UTF8
$out | Out-File $log -Encoding UTF8 -Append
"done" | Out-File $log -Encoding UTF8 -Append
