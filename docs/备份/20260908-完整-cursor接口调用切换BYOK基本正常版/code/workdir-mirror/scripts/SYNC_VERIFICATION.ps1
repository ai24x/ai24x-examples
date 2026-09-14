# OpenClaw同步验证脚本
# 检查文件差异，提供同步建议

Write-Host "=== OpenClaw同步验证 ==="
Write-Host "Time: $(Get-Date)"
Write-Host "Mode: Difference detection"

# 1. Check file differences
Write-Host "`n1. Checking file differences..."

$sourceDir = "C:\AI24X\OpenClaw\openclaw"
$targetDir = "C:\claw\openclaw"

# Check source directory
$sourceFiles = Get-ChildItem $sourceDir -Recurse -File
Write-Host "Source files: $($sourceFiles.Count)"

# Check target directory
$targetFiles = Get-ChildItem $targetDir -Recurse -File
Write-Host "Target files: $($targetFiles.Count)"

# 2. File comparison
Write-Host "`n2. File comparison..."

$differences = @()
foreach ($sourceFile in $sourceFiles) {
    $relativePath = $sourceFile.FullName.Substring($sourceDir.Length)
    $targetPath = Join-Path $targetDir $relativePath
    
    if (Test-Path $targetPath) {
        # Check if files are identical
        $sourceHash = Get-FileHash $sourceFile.FullName -Algorithm MD5
        $targetHash = Get-FileHash $targetPath -Algorithm MD5
        
        if ($sourceHash.Hash -ne $targetHash.Hash) {
            $differences += [PSCustomObject]@{
                File = $relativePath
                SourceSize = $sourceFile.Length
                TargetSize = (Get-Item $targetPath).Length
                SourceTime = $sourceFile.LastWriteTime
                TargetTime = (Get-Item $targetPath).LastWriteTime
                Status = "Content different"
            }
        }
    } else {
        $differences += [PSCustomObject]@{
            File = $relativePath
            SourceSize = $sourceFile.Length
            TargetSize = "Missing"
            SourceTime = $sourceFile.LastWriteTime
            TargetTime = "Missing"
            Status = "Missing file"
        }
    }
}

# 3. Display report
Write-Host "`n3. Difference report:"
if ($differences.Count -eq 0) {
    Write-Host "✅ All files are identical, no sync needed!"
} else {
    Write-Host "Found $($differences.Count) differences:"
    $differences | Format-Table File, Status, SourceSize, TargetSize, SourceTime, TargetTime
    
    Write-Host "`nRecommendation:"
    if ($differences.Count -eq 0) {
        Write-Host "✅ No synchronization needed - files are already identical"
    } else {
        Write-Host "📋 Files need synchronization"
    }
}

# 4. Final verification
Write-Host "`n4. Final verification..."
$finalSourceCount = (Get-ChildItem $sourceDir -Recurse -File).Count
$finalTargetCount = (Get-ChildItem $targetDir -Recurse -File).Count

Write-Host "Source: $finalSourceCount files"
Write-Host "Target: $finalTargetCount files"

if ($finalSourceCount -eq $finalTargetCount) {
    Write-Host "✅ File count matches"
} else {
    Write-Host "⚠️ File count mismatch"
}

Write-Host "`n=== Script completed ==="