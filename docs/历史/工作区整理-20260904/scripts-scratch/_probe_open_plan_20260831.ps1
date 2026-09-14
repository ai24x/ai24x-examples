$ErrorActionPreference = "Continue"

Write-Host "== open process =="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'open|18080' } |
  ForEach-Object {
    $dt = $_.CreationDate.ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host ("PID=" + $_.ProcessId + " START=" + $dt)
  }

Write-Host "== wallet probe =="
$py = @'
import os, sys
from sqlalchemy import create_engine, text

EMAIL = "lei@itxin.com"

def load_url(path):
    for line in open(path, encoding="utf-8", errors="ignore"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    return None

def probe(tag, url):
    if not url:
        print(tag, "NO_URL")
        return
    e = create_engine(url)
    with e.connect() as c:
        users = c.execute(text("SELECT id, email, phone FROM auth_users WHERE email = :e OR phone = :e"), {"e": EMAIL}).fetchall()
        if not users:
            print(tag, "NO_USER")
            return
        for u in users:
            w = c.execute(text("SELECT plan, balance_tokens, balance_usd, vip_expires_at FROM token_wallets WHERE auth_user_id = :uid"), {"uid": u[0]}).fetchall()
            print(tag, "user", u[0], u[1], "wallets=", [(str(x[0]), x[1], x[2], str(x[3])) for x in w])

open_url = load_url(r"C:\ai24x01\p\open\api\.env")
core_url = load_url(r"C:\ai24x01\api\.env")
probe("OPEN", open_url)
probe("CORE", core_url)
print("PROBE_DONE")
'@
$py | python -
