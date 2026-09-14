# CX-Bridge v4：主脑 -> Codex 司令 的"类SSH"驱动入口（同步请求/响应 + 持久值守线程）
# 用法（主脑侧执行）：
#   powershell -ExecutionPolicy Bypass -File cx_bridge.ps1 -TaskFile <指令文件> -ReplyFile <回复文件> [-ThreadId <线程ID>]
# v4 改进（2026-08-07 23:40）：
#   - 默认写入【持久值守线程】01a08c71-b13a-75a2-9a94-9133e11c18ff：
#     （2026-09-11 重建：旧线程 019fdcdd-e3e7-7122-90a0-8ac181c9b141 被归档致 thread/resume -32600，cx 通道全挂）
#     用 `codex exec resume <ThreadId>` 处理任务，所有任务与回复都追加到该线程 jsonl，
#     形成老板要的"合格会话连续记录"（桌面侧边栏可打开该线程查看）。
#   - 超时语义改为"进行中"：超过 TimeoutSec 未出回复时写 [CX-Bridge 进行中] 状态（exit 0），
#     worker 后台继续跑，回复就绪后由主脑 cron 转达；不再视为失败。
#   - 保留派发+确认规则（P3 SIGKILL 根因修复）：长链条任务只派发不同步等待。
# 关键坑位：
#   - codex exec / resume 必须加 -c "notify=[]"：否则 turn-ended notify 钩子让进程写完回复不退出
#   - 模型用 config.toml 默认（deepseek-v4-flash），不传 -m/-c，避免 P1 短名问题
#   - ephemeral 模式用 --sandbox danger-full-access（P2）；resume 模式线程创建时已带权限
param(
  [ValidateSet("Bridge","Worker")][string]$Mode = "Bridge",
  [Parameter(Mandatory=$true)][string]$TaskFile,
  [Parameter(Mandatory=$true)][string]$ReplyFile,
  [string]$WorkDir = "E:\AI24X\ai24x-website\ai24x01",
  [int]$TimeoutSec = 115,
  [string]$ThreadId = "01a08c71-b13a-75a2-9a94-9133e11c18ff"
)
$replyDir = Split-Path -Parent $ReplyFile
if (-not (Test-Path -LiteralPath $replyDir)) { New-Item -ItemType Directory -Path $replyDir -Force | Out-Null }

if ($Mode -eq "Worker") {
  $task = Get-Content -LiteralPath $TaskFile -Raw -Encoding UTF8
  $budget = [Math]::Max(30, $TimeoutSec - 15)
  $prompt = "【CX-Bridge 任务】（执行预算 " + $budget + " 秒，超预算必须立即收尾回复）" + [Environment]::NewLine + "请处理以下指令：" + [Environment]::NewLine + "---" + [Environment]::NewLine + $task + [Environment]::NewLine + "---" + [Environment]::NewLine + [Environment]::NewLine + "执行规则（必须遵守）：" + [Environment]::NewLine + "1) 能直接执行的直接执行（写文件、跑命令都允许，工作目录 " + $WorkDir + "），但整体必须控制在预算内；" + [Environment]::NewLine + "2) 若任务需要主脑/副脑多步执行（如 SSH 派发多台副脑、汇总等待），【禁止】同步等待完整链条——采用派发+确认：把完整任务写成指令文件放 " + $WorkDir + "\docs\营销\收发\指令\（命名 YYYYMMDD-HHMM-codex-任务名.txt），再用 openclaw agent --agent main --message-file <该文件> --json --timeout 60 触发主脑，拿到主脑确认后立即回复'已派发，主脑执行中，结果由主脑飞书汇报'并结束；" + [Environment]::NewLine + "3) 若 openclaw agent 调用本身超时，直接回复'已派发（主脑异步执行中）'结束，不要重试超过 1 次；" + [Environment]::NewLine + "4) 需要老板拍板的事，给出建议并标注【待审批】；" + [Environment]::NewLine + "5) 最终用中文一句话总结处理结果，作为你的最后一条回复（会被写入回复文件）；" + [Environment]::NewLine + "6) 除非任务明确要求，不要修改无关代码。"
  $out = $null
  if ($ThreadId) {
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $out = $prompt | & codex exec resume $ThreadId -c "notify=[]" -o $ReplyFile - 2>&1
  } else {
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $out = $prompt | & codex exec --ephemeral -C $WorkDir --skip-git-repo-check --sandbox danger-full-access -c "notify=[]" -o $ReplyFile - 2>&1
  }
  $code = $LASTEXITCODE
  if ((-not (Test-Path -LiteralPath $ReplyFile)) -or ((Get-Item -LiteralPath $ReplyFile).Length -eq 0)) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $errText = "[CX-Bridge 异常] codex exec 退出码 " + $code + "，无回复输出。" + [Environment]::NewLine + ($out | Out-String)
    [System.IO.File]::WriteAllText($ReplyFile, $errText.Trim(), $utf8)
  }
  exit $code
}

# Bridge 模式：启动隐藏 Worker，轮询回复文件，一出现立即返回
Remove-Item -LiteralPath $ReplyFile -Force -ErrorAction SilentlyContinue
$args = @('-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-Mode','Worker','-TaskFile',$TaskFile,'-ReplyFile',$ReplyFile,'-WorkDir',$WorkDir,'-TimeoutSec',[string]$TimeoutSec,'-ThreadId',$ThreadId)
Start-Process -FilePath "powershell.exe" -ArgumentList $args -WindowStyle Hidden | Out-Null
$start = Get-Date
$deadline = $start.AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
  if (Test-Path -LiteralPath $ReplyFile) {
    $len = (Get-Item -LiteralPath $ReplyFile).Length
    if ($len -gt 0) {
      Write-Output "CX-Bridge OK: $ReplyFile (elapsed $([Math]::Round(((Get-Date) - $start).TotalSeconds,1))s)"
      exit 0
    }
  }
  Start-Sleep -Seconds 2
}
# 超时：写"进行中"状态（worker 后台继续，回复就绪由 cron 转达）
$utf8 = New-Object System.Text.UTF8Encoding($false)
$statusText = "[CX-Bridge 进行中] 已等待 " + $TimeoutSec + "s 未出回复，worker 仍在后台执行；回复就绪后主脑 cron 将自动转达，无需重试。"
[System.IO.File]::WriteAllText($ReplyFile, $statusText, $utf8)
Write-Output "CX-Bridge IN-PROGRESS: $ReplyFile"
exit 0