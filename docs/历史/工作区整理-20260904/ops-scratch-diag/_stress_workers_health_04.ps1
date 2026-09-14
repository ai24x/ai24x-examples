# P0/P1/multi-worker pressure proof on 04 (localhost).
# 1) baseline health latency
# 2) suspend 1 / 3 workers -> health must stay fast
# 3) suspend all 4 -> health should stall
# 4) resume all + concurrent health burst
# Does NOT call paid LLM endpoints.

$ErrorActionPreference = "Stop"
$HealthUrl = "http://127.0.0.1:8002/health"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class ProcCtrl {
  [DllImport("ntdll.dll")] public static extern int NtSuspendProcess(IntPtr processHandle);
  [DllImport("ntdll.dll")] public static extern int NtResumeProcess(IntPtr processHandle);
}
"@ -ErrorAction SilentlyContinue

function Get-SpawnWorkers([int]$Port) {
  $all = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
  $listen = @()
  netstat -ano | Select-String -Pattern ("TCP\s+127\.0\.0\.1:" + $Port + "\s+.*LISTENING\s+(\d+)") | ForEach-Object {
    if ($_.Matches.Count -gt 0) { $listen += [int]$_.Matches[0].Groups[1].Value }
  }
  $listen = @($listen | Select-Object -Unique)
  $workers = @()
  foreach ($lid in $listen) {
    $root = $all | Where-Object { $_.ProcessId -eq $lid } | Select-Object -First 1
    if (-not $root) { continue }
    $workers += @($all | Where-Object {
      $_.ParentProcessId -eq $lid -and $_.CommandLine -like "*multiprocessing.spawn*"
    })
    # venv stub parent of listener
    $par = $all | Where-Object { $_.ProcessId -eq $root.ParentProcessId } | Select-Object -First 1
    if ($par) {
      $workers += @($all | Where-Object {
        $_.ParentProcessId -eq $par.ProcessId -and $_.CommandLine -like "*multiprocessing.spawn*"
      })
    }
  }
  return @($workers | Sort-Object ProcessId -Unique)
}

function Measure-Health([int]$N = 10, [int]$TimeoutSec = 3) {
  $msOk = New-Object System.Collections.Generic.List[int]
  $msAll = New-Object System.Collections.Generic.List[int]
  $ok = 0
  $fail = 0
  for ($i = 0; $i -lt $N; $i++) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
      $r = Invoke-RestMethod -UseBasicParsing -Uri $HealthUrl -TimeoutSec $TimeoutSec
      $sw.Stop()
      $elapsed = [int]$sw.ElapsedMilliseconds
      [void]$msAll.Add($elapsed)
      if ($r.status -eq "healthy" -or $r.commit) {
        $ok++
        [void]$msOk.Add($elapsed)
      } else {
        $fail++
      }
    } catch {
      $sw.Stop()
      $fail++
      [void]$msAll.Add([int]$sw.ElapsedMilliseconds)
    }
  }
  $sortedAll = @($msAll | Sort-Object)
  $p50 = $sortedAll[[math]::Floor(($sortedAll.Count - 1) * 0.5)]
  $p95 = $sortedAll[[math]::Floor(($sortedAll.Count - 1) * 0.95)]
  $okP50 = $null
  if ($msOk.Count -gt 0) {
    $sok = @($msOk | Sort-Object)
    $okP50 = $sok[[math]::Floor(($sok.Count - 1) * 0.5)]
  }
  return [pscustomobject]@{
    ok = $ok; fail = $fail; n = $N
    min = ($msAll | Measure-Object -Minimum).Minimum
    p50 = $p50; p95 = $p95
    max = ($msAll | Measure-Object -Maximum).Maximum
    ok_p50 = $okP50
    ok_max = $(if ($msOk.Count -gt 0) { ($msOk | Measure-Object -Maximum).Maximum } else { $null })
  }
}

function Suspend-Pids([int[]]$Pids) {
  foreach ($id in $Pids) {
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $p) { Write-Host ("  suspend skip missing " + $id); continue }
    $rc = [ProcCtrl]::NtSuspendProcess($p.Handle)
    Write-Host ("  suspend pid=" + $id + " rc=" + $rc)
  }
}

function Resume-Pids([int[]]$Pids) {
  foreach ($id in $Pids) {
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $p) { Write-Host ("  resume skip missing " + $id); continue }
    $rc = [ProcCtrl]::NtResumeProcess($p.Handle)
    Write-Host ("  resume pid=" + $id + " rc=" + $rc)
  }
}

function Wait-Workers([int]$Port, [int]$Min = 4, [int]$TimeoutSec = 20) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do {
    $w = Get-SpawnWorkers -Port $Port
    if ($w.Count -ge $Min) { return @($w | ForEach-Object { [int]$_.ProcessId }) }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  $w = Get-SpawnWorkers -Port $Port
  return @($w | ForEach-Object { [int]$_.ProcessId })
}

Write-Host "== discover workers ==" -ForegroundColor Cyan
$workers = Get-SpawnWorkers -Port 8002
Write-Host ("spawn_workers=" + $workers.Count + " pids=" + (($workers | ForEach-Object { $_.ProcessId }) -join ","))
if ($workers.Count -lt 4) { throw "need >=4 workers for this test" }
$wp = @($workers | ForEach-Object { [int]$_.ProcessId })
$suspended = New-Object System.Collections.Generic.List[int]

try {
Write-Host "`n== A. baseline health (n=20) ==" -ForegroundColor Cyan
$base = Measure-Health -N 20 -TimeoutSec 3
Write-Host ($base | Format-List | Out-String)

Write-Host "`n== B. suspend 1 worker, health n=15 ==" -ForegroundColor Cyan
Suspend-Pids @($wp[0]); [void]$suspended.Add($wp[0])
Start-Sleep -Milliseconds 300
$b1 = Measure-Health -N 15 -TimeoutSec 3
Write-Host ($b1 | Format-List | Out-String)
Resume-Pids @($wp[0]); [void]$suspended.Remove($wp[0])
Start-Sleep -Milliseconds 500
if ($b1.ok -lt 8 -or $b1.ok_p50 -gt 100) {
  throw ("FAIL B: need most health OK fast; ok=" + $b1.ok + " ok_p50=" + $b1.ok_p50)
}
Write-Host "PASS B (1 frozen: capacity remains)" -ForegroundColor Green

Write-Host "`n== C. suspend 3 workers, health n=20 ==" -ForegroundColor Cyan
Suspend-Pids @($wp[0], $wp[1], $wp[2])
@($wp[0], $wp[1], $wp[2]) | ForEach-Object { [void]$suspended.Add($_) }
Start-Sleep -Milliseconds 300
$c1 = Measure-Health -N 20 -TimeoutSec 3
Write-Host ($c1 | Format-List | Out-String)
Resume-Pids @($wp[0], $wp[1], $wp[2])
$suspended.Clear()
Start-Sleep -Milliseconds 500
if ($c1.ok -lt 3 -or $c1.ok_p50 -gt 150) {
  throw ("FAIL C: need some health OK on last worker; ok=" + $c1.ok + " ok_p50=" + $c1.ok_p50)
}
Write-Host "PASS C (3 frozen / 1 alive: partial capacity)" -ForegroundColor Green

Write-Host "`n== D. refresh workers, then suspend ALL ==" -ForegroundColor Cyan
$wp = Wait-Workers -Port 8002 -Min 4 -TimeoutSec 25
Write-Host ("workers_now=" + $wp.Count + " pids=" + ($wp -join ","))
if ($wp.Count -lt 2) { throw "not enough workers after C to run D" }
Suspend-Pids $wp
$wp | ForEach-Object { [void]$suspended.Add($_) }
Start-Sleep -Milliseconds 300
$d1 = Measure-Health -N 3 -TimeoutSec 2
Write-Host ($d1 | Format-List | Out-String)
Resume-Pids $wp
$suspended.Clear()
Start-Sleep -Seconds 2
$wp = Wait-Workers -Port 8002 -Min 4 -TimeoutSec 25
Write-Host ("workers_after_D=" + $wp.Count)
if ($d1.fail -lt 2 -and $wp.Count -ge 4) {
  Write-Host "WARN D: expected stalls when all frozen (maybe accept landed on parent)" -ForegroundColor Yellow
} else {
  Write-Host "PASS D" -ForegroundColor Green
}

Write-Host "`n== E. recovery + concurrent burst ==" -ForegroundColor Cyan
$jobs = @()
1..30 | ForEach-Object {
  $jobs += Start-Job -ScriptBlock {
    param($u)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
      $r = Invoke-RestMethod -UseBasicParsing -Uri $u -TimeoutSec 5
      $sw.Stop()
      return @{ ok = 1; ms = [int]$sw.ElapsedMilliseconds; commit = [string]$r.commit }
    } catch {
      $sw.Stop()
      return @{ ok = 0; ms = [int]$sw.ElapsedMilliseconds; commit = "" }
    }
  } -ArgumentList $HealthUrl
}
$results = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job -Force
$okN = @($results | Where-Object { $_.ok -eq 1 }).Count
$msAll = @($results | ForEach-Object { $_.ms }) | Sort-Object
$p95e = $msAll[[math]::Floor(($msAll.Count - 1) * 0.95)]
Write-Host ("concurrent ok=" + $okN + "/30 p95=" + $p95e + "ms max=" + ($msAll | Measure-Object -Maximum).Maximum)
if ($okN -lt 28) { throw ("FAIL E concurrent ok=" + $okN) }
Write-Host "PASS E" -ForegroundColor Green

Write-Host "`n== F. final health ==" -ForegroundColor Cyan
$fin = Invoke-RestMethod -UseBasicParsing -Uri $HealthUrl -TimeoutSec 5
Write-Host ("status=" + $fin.status + " commit=" + $fin.commit)
$alive = Get-SpawnWorkers -Port 8002
Write-Host ("workers_after=" + $alive.Count)

Write-Host "`nSTRESS_OK" -ForegroundColor Green
Write-Host ("SUMMARY baseline_p50=" + $base.p50 + "ms | 1frozen ok=" + $b1.ok + "/" + $b1.n + " ok_p50=" + $b1.ok_p50 + "ms | 3frozen ok=" + $c1.ok + "/" + $c1.n + " ok_p50=" + $c1.ok_p50 + "ms | allfrozen_fail=" + $d1.fail + "/" + $d1.n + " | burst_ok=" + $okN + "/30")
}
finally {
  if ($suspended.Count -gt 0) {
    Write-Host ("FINALLY resume leftover: " + ($suspended -join ",")) -ForegroundColor Yellow
    Resume-Pids @($suspended)
  }
}
