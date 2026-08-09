const fs = require('fs');
const bom = '\uFEFF';
const script = [
  "$root='E:\\AI24X\\ai24x-website\\ai24x01\\docs\\营销\\收发\\回复\\'",
  "$sent=$root+'_sent\\'",
  "Get-ChildItem -Path $root -File -Filter *.txt | ForEach-Object {",
  "  $s=$sent+$_.Name",
  "  if(Test-Path $s){",
  "    $h1=(Get-FileHash $_.FullName -Algorithm MD5).Hash",
  "    $h2=(Get-FileHash $s -Algorithm MD5).Hash",
  "    Write-Output ($_.Name+' | root='+$_.Length+' | sent='+(Get-Item $s).Length+' | SAME='+($h1 -eq $h2))",
  "  } else { Write-Output ($_.Name+' | NO_SENT_COPY') }",
  "}",
  ""
].join('\n');
fs.writeFileSync('E:\\AI24X\\ai24x-website\\ai24x01\\scripts\\cmp_replies.ps1', bom + script, 'utf8');
console.log('written');
