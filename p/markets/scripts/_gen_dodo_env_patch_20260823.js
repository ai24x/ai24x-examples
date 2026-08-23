// 生成 04 生产 DODO 环境变量补丁脚本（密钥不进 git；输出到安全凭据目录）
const fs = require("fs");

function env(f) {
  const o = {};
  for (const l of fs.readFileSync(f, "utf8").split(/\r?\n/)) {
    const m = l.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m) o[m[1]] = m[2].trim();
  }
  return o;
}

const core = env("api/.env");
const open = env("p/open/api/.env");

const esc = (v) =>
  String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\$/g, "`$");

const coreKeys = [
  "DODO_API_KEY",
  "DODO_MODE",
  "DODO_WEBHOOK_SECRET",
  "DODO_PRODUCT_MARKETS_WEEKLY",
  "DODO_PRODUCT_MARKETS_MONTHLY",
  "DODO_PRODUCT_MARKETS_YEARLY",
  "DODO_API_KEY_LIVE",
];
const openKeys = [
  "DODO_API_KEY",
  "DODO_MODE",
  "DODO_WEBHOOK_SECRET",
  "DODO_RETURN_URL",
  "DODO_PRODUCT_BYOK_MONTH",
  "DODO_PRODUCT_BYOK_YEAR",
  "DODO_API_KEY_LIVE",
];

const lines = [];
lines.push("function Set-DodoVars {");
lines.push("  param([string]$EnvFile,[string[]]$Keys)");
lines.push('  if (-not (Test-Path $EnvFile)) { Write-Host "!! missing $EnvFile" -ForegroundColor Red; return 1 }');
lines.push("  $stamp = Get-Date -Format yyyyMMdd-HHmmss");
lines.push('  Copy-Item -LiteralPath $EnvFile -Destination ($EnvFile + ".bak-dodo-" + $stamp) -Force');
lines.push("  $lines = Get-Content -LiteralPath $EnvFile -Encoding UTF8");
lines.push("  $added = 0; $updated = 0");
lines.push("  foreach ($k in $Keys) {");
lines.push('    $val = [System.Environment]::GetEnvironmentVariable("__DVAL_$k")');
lines.push('    if ([string]::IsNullOrEmpty($val)) { Write-Host "  !! no value for $k" -ForegroundColor Red; continue }');
lines.push("    $idx = -1");
lines.push('    for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match "^$k=") { $idx = $i; break } }');
lines.push('    $newLine = "$k=$val"');
lines.push('    if ($idx -ge 0) { $lines[$idx] = $newLine; $updated++ } else { $lines += $newLine; $added++ }');
lines.push('    Write-Host ("  " + $k + " = " + $val.Substring(0, [Math]::Min(6, $val.Length)) + "...") -ForegroundColor Green');
lines.push("  }");
lines.push("  [System.IO.File]::WriteAllLines($EnvFile, $lines, (New-Object System.Text.UTF8Encoding($false)))");
lines.push('  Write-Host "  done: added=$added updated=$updated (backup .bak-dodo-$stamp)" -ForegroundColor Green');
lines.push("}");
lines.push("");
const setVal = (k, v) => lines.push('$env:__DVAL_' + k + ' = "' + esc(v) + '"');
coreKeys.forEach((k) => setVal(k, core[k]));
lines.push("Set-DodoVars -EnvFile 'C:\\ai24x01\\api\\.env' -Keys @(" + coreKeys.map((k) => '"' + k + '"').join(",") + ")");
lines.push("");
["DODO_RETURN_URL", "DODO_PRODUCT_BYOK_MONTH", "DODO_PRODUCT_BYOK_YEAR"].forEach((k) => setVal(k, open[k]));
lines.push("Set-DodoVars -EnvFile 'C:\\ai24x01\\p\\open\\api\\.env' -Keys @(" + openKeys.map((k) => '"' + k + '"').join(",") + ")");
lines.push("");
lines.push('Write-Host "DODO env patch complete" -ForegroundColor Cyan');

const out = lines.join("\r\n") + "\r\n";
const dir = "E:/AI24X/安全凭据/ops-patches";
fs.mkdirSync(dir, { recursive: true });
const p = dir + "/dodo_env_20260823.ps1";
fs.writeFileSync(p, "\uFEFF" + out, "utf8");
console.log("written", p, out.length, "bytes");
