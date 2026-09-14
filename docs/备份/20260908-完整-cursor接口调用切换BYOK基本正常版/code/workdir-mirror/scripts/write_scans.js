const fs = require('fs');
const bom = '\uFEFF';
const instr = [
  "$dir = 'E:\\AI24X\\ai24x-website\\ai24x01\\docs\\营销\\收发\\指令\\'",
  "Get-ChildItem -Path $dir -File -Filter *.txt | Where-Object { -not $_.Name.StartsWith('_') } | Select-Object -ExpandProperty FullName",
  ""
].join('\n');
const reply = [
  "$dir = 'E:\\AI24X\\ai24x-website\\ai24x01\\docs\\营销\\收发\\回复\\'",
  "Get-ChildItem -Path $dir -File -Filter *.txt | Where-Object { -not $_.Name.StartsWith('_') } | Select-Object -ExpandProperty FullName",
  ""
].join('\n');
fs.writeFileSync('E:\\AI24X\\ai24x-website\\ai24x01\\scripts\\scan_instr.ps1', bom + instr, 'utf8');
fs.writeFileSync('E:\\AI24X\\ai24x-website\\ai24x01\\scripts\\scan_reply.ps1', bom + reply, 'utf8');
console.log('written');
