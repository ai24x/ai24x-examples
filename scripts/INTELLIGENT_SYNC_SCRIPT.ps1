# OpenClaw智能同步脚本
# 自动检测差异，安全同步，保护数据库

Write-Host "=== OpenClaw智能同步脚本 ==="
Write-Host "时间: $(Get-Date)"
Write-Host "模式: 差异检测 + 安全同步"

# 1. 检查文件差异
Write-Host "`n1. 检查文件差异..."

$sourceDir = "C:\AI24X\OpenClaw\openclaw"
$targetDir = "C:\claw\openclaw"

# 检查源目录文件
$sourceFiles = Get-ChildItem $sourceDir -Recurse -File
Write-Host "源目录文件数: $($sourceFiles.Count)"

# 检查目标目录文件
$targetFiles = Get-ChildItem $targetDir -Recurse -File
Write-Host "目标目录文件数: $($targetFiles.Count)"

# 2. 文件对比
Write-Host "`n2. 文件对比分析..."

$differences = @()
foreach ($sourceFile in $sourceFiles) {
    $relativePath = $sourceFile.FullName.Substring($sourceDir.Length)
    $targetPath = Join-Path $targetDir $relativePath
    
    if (Test-Path $targetPath) {
        # 检查文件内容是否相同
        $sourceHash = Get-FileHash $sourceFile.FullName -Algorithm MD5
        $targetHash = Get-FileHash $targetPath -Algorithm MD5
        
        if ($sourceHash.Hash -ne $targetHash.Hash) {
            $differences += @{
                File = $relativePath
                SourceSize = $sourceFile.Length
                TargetSize = (Get-Item $targetPath).Length
                SourceTime = $sourceFile.LastWriteTime
                TargetTime = (Get-Item $targetPath).LastWriteTime
                Status = "内容不同"
            }
        }
    } else {
        $differences += @{
            File = $relativePath
            SourceSize = $sourceFile.Length
            TargetSize = "不存在"
            SourceTime = $sourceFile.LastWriteTime
            TargetTime = "不存在"
            Status = "缺失文件"
        }
    }
}

# 3. 显示差异报告
Write-Host "`n3. 差异报告:"
if ($differences.Count -eq 0) {
    Write-Host "✅ 所有文件完全相同，无需同步！"
} else {
    Write-Host "发现 $($differences.Count) 个差异:"
    $differences | Format-Table File, Status, SourceSize, TargetSize, SourceTime, TargetTime
    
    # 4. 询问是否同步
    Write-Host "`n4. 同步选项:"
    Write-Host "   A) 同步所有差异文件"
    Write-Host "   B) 仅同步缺失文件"
    Write-Host "   C) 跳过同步"
    
    $choice = Read-Host "`n请选择 (A/B/C)"
    
    switch ($choice.ToUpper()) {
        "A" {
            # 同步所有差异
            Write-Host "`n开始同步所有差异文件..."
            foreach ($diff in $differences) {
                $sourceFile = Join-Path $sourceDir $diff.File
                $targetFile = Join-Path $targetDir $diff.File
                
                # 确保目标目录存在
                $targetDirPath = Split-Path $targetFile -Parent
                if (!(Test-Path $targetDirPath)) {
                    New-Item -ItemType Directory -Path $targetDirPath -Force
                }
                
                Copy-Item $sourceFile $targetFile -Force
                Write-Host "✅ 同步: $($diff.File)"
            }
            Write-Host "`n✅ 同步完成！"
        }
        "B" {
            # 仅同步缺失文件
            Write-Host "`n开始同步缺失文件..."
            $missingFiles = $differences | Where-Object { $_.Status -eq "缺失文件" }
            foreach ($diff in $missingFiles) {
                $sourceFile = Join-Path $sourceDir $diff.File
                $targetFile = Join-Path $targetDir $diff.File
                
                # 确保目标目录存在
                $targetDirPath = Split-Path $targetFile -Parent
                if (!(Test-Path $targetDirPath)) {
                    New-Item -ItemType Directory -Path $targetDirPath -Force
                }
                
                Copy-Item $sourceFile $targetFile -Force
                Write-Host "✅ 同步缺失文件: $($diff.File)"
            }
            Write-Host "`n✅ 缺失文件同步完成！"
        }
        "C" {
            Write-Host "`n跳过同步操作。"
        }
    }
}

# 5. 最终验证
Write-Host "`n5. 最终验证..."
$finalSourceFiles = Get-ChildItem $sourceDir -Recurse -File
$finalTargetFiles = Get-ChildItem $targetDir -Recurse -File

Write-Host "源目录: $($finalSourceFiles.Count) 个文件"
Write-Host "目标目录: $($finalTargetFiles.Count) 个文件"

if ($finalSourceFiles.Count -eq $finalTargetFiles.Count) {
    Write-Host "✅ 文件数量一致"
} else {
    Write-Host "⚠️ 文件数量不一致"
}

Write-Host "`n=== 脚本执行完成 ==="