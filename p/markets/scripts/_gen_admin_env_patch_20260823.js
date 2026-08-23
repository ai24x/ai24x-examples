// 生成 04 生产 ADMIN_API_KEY 补丁脚本（密钥不进 git；输出到安全凭据目录）
const fs = require("fs");

const secretFile = "E:/AI24X/安全凭据/ops-patches/admin_api_key_prod_20260823.txt";
const content = fs.readFileSync(secretFile, "utf8");
const m = content.match(/^ADMIN_API_KEY=(.+)$/m);
if (!m) throw new Error("ADMIN_API_KEY not found in secret file");
const key = m[1].trim();

const esc = (v) =>
  String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\$/g, "`$");

const L = [];
L.push("function Set-AdminVars {");
L.push("  param([string]$EnvFile,[string[]]$Keys)");
L.push('  if (-not (Test-Path $EnvFile)) { Write-Host "!! missing $EnvFile" -ForegroundColor Red; return 1 }');
L.push("  $stamp = Get-Date -Format yyyyMMdd-HHmmss");
L.push('  Copy-Item -LiteralPath $EnvFile -Destination ($EnvFile + ".bak-admin-" + $stamp) -Force');
L.push("  $lines = Get-Content -LiteralPath $EnvFile -Encoding UTF8");
L.push("  $added = 0; $updated = 0");
L.push("  foreach ($k in $Keys) {");
L.push('    $val = [System.Environment]::GetEnvironmentVariable("__AVAL_$k")');
L.push('    if ([string]::IsNullOrEmpty($val)) { Write-Host "  !! no value for $k" -ForegroundColor Red; continue }');
L.push("    $idx = -1");
L.push('    for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match "^$k=") { $idx = $i; break } }');
L.push('    $newLine = "$k=$val"');
L.push('    if ($idx -ge 0) { $lines[$idx] = $newLine; $updated++ } else { $lines += $newLine; $added++ }');
L.push('    Write-Host ("  " + $k + " = " + $val.Substring(0, [Math]::Min(6, $val.Length)) + "...") -ForegroundColor Green');
L.push("  }");
L.push("  [System.IO.File]::WriteAllLines($EnvFile, $lines, (New-Object System.Text.UTF8Encoding($false)))");
L.push('  Write-Host "  done: added=$added updated=$updated (backup .bak-admin-$stamp)" -ForegroundColor Green');
L.push("}");
L.push("");
L.push('$env:__AVAL_ADMIN_API_KEY = "' + esc(key) + '"');
L.push('$env:__AVAL_ADMIN_REQUIRE_SMS = "true"');
L.push('$env:__AVAL_ADMIN_PHONE = "18958992226"');
L.push("Set-AdminVars -EnvFile 'C:\\ai24x01\\api\\.env' -Keys @(\"ADMIN_API_KEY\",\"ADMIN_REQUIRE_SMS\",\"ADMIN_PHONE\")");
L.push("");
L.push("Set-AdminVars -EnvFile 'C:\\ai24x01\\p\\open\\api\\.env' -Keys @(\"ADMIN_API_KEY\")");
L.push("");
L.push("Restart-Service AI24X-core -Force");
L.push("Restart-Service AI24X-open-api -Force");
L.push("");
L.push('$ok = $false');
L.push('for ($i = 0; $i -lt 24; $i++) { Start-Sleep -Seconds 5; try { $m = Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/admin/auth/mode" -TimeoutSec 10 -UseBasicParsing; $ok = $true; break } catch {} }');
L.push('if (-not $ok) { Write-Host "!! core auth/mode not ready" -ForegroundColor Red; exit 1 }');
L.push('"core require_sms=" + $m.require_sms + " sms_enabled=" + $m.sms_enabled + " sms_key_configured=" + $m.sms_key_configured');
L.push('if (-not $m.require_sms -or -not $m.sms_enabled) { Write-Host "!! ADMIN 2FA 未生效" -ForegroundColor Red; exit 1 }');
L.push("");
L.push('$ok2 = $false');
L.push('for ($i = 0; $i -lt 24; $i++) { Start-Sleep -Seconds 5; try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:18080/health" -TimeoutSec 10 -UseBasicParsing; $ok2 = $true; break } catch {} }');
L.push('if (-not $ok2) { Write-Host "!! open not ready" -ForegroundColor Red; exit 1 }');
L.push('"open health=" + $h.status + " commit=" + $h.commit');
L.push("");
L.push('try {');
L.push('  $r = Invoke-WebRequest -Uri "http://127.0.0.1:18080/v1/admin/byok/plans" -Headers @{"X-Admin-Key"="' + esc(key) + '"} -TimeoutSec 15 -UseBasicParsing');
L.push('  "open admin key accept status=" + $r.StatusCode');
L.push('  if ($r.StatusCode -ne 200) { Write-Host "!! open 不接受 ADMIN_API_KEY" -ForegroundColor Red; exit 1 }');
L.push('} catch { Write-Host ("!! open admin probe failed: " + $_.Exception.Message) -ForegroundColor Red; exit 1 }');
L.push("");
L.push('Write-Host "ADMIN env patch + verify complete" -ForegroundColor Cyan');

const out = L.join("\r\n") + "\r\n";
const dir = "E:/AI24X/安全凭据/ops-patches";
fs.mkdirSync(dir, { recursive: true });
const p = dir + "/admin_env_20260823.ps1";
fs.writeFileSync(p, "\uFEFF" + out, "utf8");
console.log("written", p, out.length, "bytes");
