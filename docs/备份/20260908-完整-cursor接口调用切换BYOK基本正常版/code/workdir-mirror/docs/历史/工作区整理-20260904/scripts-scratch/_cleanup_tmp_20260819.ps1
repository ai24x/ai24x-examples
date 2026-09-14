$ErrorActionPreference = "Continue"
$dest = "C:\ai24x01\scripts\_tmp_deploy_20260819"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$files = Get-ChildItem "C:\ai24x01\scripts" -File |
  Where-Object {
    $_.Name -like "_*open*" -or $_.Name -like "_probe*" -or
    $_.Name -like "_check_open*" -or $_.Name -like "_smoke_open*" -or
    $_.Name -like "_cleanup_open*" -or $_.Name -like "_find_feishu*" -or
    $_.Name -like "_send_group*" -or $_.Name -like "_receipt_366f818*" -or
    $_.Name -like "_make_nginx_open*" -or $_.Name -like "_deploy_open*" -or
    $_.Name -like "_verify_open*"
  }
$files | Move-Item -Destination $dest -Force
Write-Output "moved $($files.Count) files to $dest"
