Write-Output "=== openclaw command ==="
$oc = Get-Command openclaw -ErrorAction SilentlyContinue
if ($oc) { $oc | Select-Object Name,Source,CommandType | Format-List } else { Write-Output "openclaw NOT in PATH" }

Write-Output "=== scheduled task state ==="
Get-ScheduledTaskInfo -TaskName "AI24X_Dev03_20260818165831" -ErrorAction SilentlyContinue | Select-Object TaskName,LastRunTime,LastTaskResult,NumberOfMissedRuns | Format-List

Write-Output "=== openclaw version (10s timeout) ==="
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $v = & openclaw --version 2>&1 | Out-String
    Write-Output $v
} catch {
    Write-Output ("ERR: " + $_.Exception.Message)
}
$sw.Stop()
Write-Output ("elapsed: " + $sw.Elapsed.TotalSeconds + "s")
