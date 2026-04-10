const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 配置
const SOURCE_DIRS = [
    'C:\\AI24X\\OpenClaw\\web\\ai24x-website',
    'C:\\AI24X\\OpenClaw\\ai24x-platform',
    'C:\\AI24X\\OpenClaw\\web\\ai24x-projects\\ai-directory-web'
];

const BACKUP_DIR = 'C:\\AI24X\\OpenClaw\\web\\bak';
const BACKUP_TIMESTAMP = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0] + '_' + 
                         new Date().getHours() + new Date().getMinutes();

// 创建备份目录
const backupRoot = path.join(BACKUP_DIR, `backup_${BACKUP_TIMESTAMP}`);
const logsDir = path.join(backupRoot, 'logs');
const reportsDir = path.join(backupRoot, 'reports');

// 确保目录存在
[backupRoot, logsDir, reportsDir].forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

console.log(`备份目录: ${backupRoot}`);
console.log(`开始时间: ${new Date().toLocaleString()}`);

// 统计信息
const stats = {
    totalFiles: 0,
    totalSize: 0,
    skippedFiles: 0,
    backupFiles: 0,
    fileTypes: {},
    invalidFiles: []
};

// 无效文件模式（测试/临时文件）
const INVALID_PATTERNS = [
    /test/i,
    /temp/i,
    /tmp/i,
    /backup/i,
    /\.bak$/i,
    /\.old$/i,
    /\.tmp$/i,
    /\.log$/i,
    /debug/i,
    /debugging/i,
    /experiment/i,
    /experimental/i,
    /sample/i,
    /example/i,
    /dummy/i,
    /mock/i,
    /stub/i,
    /placeholder/i,
    /todo/i,
    /fixme/i,
    /hack/i,
    /wip/i,
    /scratch/i,
    /sandbox/i,
    /playground/i,
    /trash/i,
    /garbage/i,
    /junk/i,
    /useless/i,
    /obsolete/i,
    /deprecated/i,
    /legacy/i,
    /old_version/i,
    /outdated/i,
    /unused/i,
    /orphan/i,
    /dead_code/i,
    /zombie/i,
    /ghost/i,
    /phantom/i,
    /shadow/i,
    /duplicate/i,
    /copy/i,
    /clone/i,
    /replica/i,
    /mirror/i,
    /backup_copy/i,
    /test_backup/i,
    /experiment_backup/i
];

// 无效目录模式
const INVALID_DIRS = [
    'node_modules',
    '.git',
    '.vscode',
    '.idea',
    '__pycache__',
    'dist',
    'build',
    'coverage',
    '.next',
    '.nuxt',
    '.cache',
    'temp',
    'tmp',
    'logs',
    'backups',
    'old',
    'archive',
    'trash',
    'recycle',
    'waste',
    'garbage',
    'junk'
];

// 检查文件是否无效
function isInvalidFile(filePath, fileName) {
    // 检查文件名模式
    for (const pattern of INVALID_PATTERNS) {
        if (pattern.test(fileName)) {
            return true;
        }
    }
    
    // 检查文件扩展名
    const ext = path.extname(fileName).toLowerCase();
    const invalidExts = ['.log', '.tmp', '.bak', '.old', '.swp', '.swo', '.pid'];
    if (invalidExts.includes(ext)) {
        return true;
    }
    
    // 检查文件大小（过小的文件可能是测试文件）
    try {
        const stats = fs.statSync(filePath);
        if (stats.size < 10) { // 小于10字节的文件
            return true;
        }
    } catch (err) {
        // 忽略错误
    }
    
    return false;
}

// 检查目录是否无效
function isInvalidDir(dirName) {
    return INVALID_DIRS.includes(dirName.toLowerCase());
}

// 复制文件
function copyFile(source, target) {
    try {
        // 创建目标目录
        const targetDir = path.dirname(target);
        if (!fs.existsSync(targetDir)) {
            fs.mkdirSync(targetDir, { recursive: true });
        }
        
        // 复制文件
        fs.copyFileSync(source, target);
        return true;
    } catch (err) {
        console.error(`复制文件失败: ${source} -> ${target}`, err.message);
        return false;
    }
}

// 遍历目录
function walkDir(dir, relativePath = '') {
    try {
        const items = fs.readdirSync(dir);
        
        for (const item of items) {
            const fullPath = path.join(dir, item);
            const relPath = path.join(relativePath, item);
            
            try {
                const stat = fs.statSync(fullPath);
                
                if (stat.isDirectory()) {
                    // 检查是否无效目录
                    if (isInvalidDir(item)) {
                        console.log(`跳过无效目录: ${relPath}`);
                        continue;
                    }
                    
                    // 递归遍历子目录
                    walkDir(fullPath, relPath);
                } else {
                    // 统计文件
                    stats.totalFiles++;
                    stats.totalSize += stat.size;
                    
                    // 检查文件扩展名
                    const ext = path.extname(item).toLowerCase() || '无扩展名';
                    stats.fileTypes[ext] = (stats.fileTypes[ext] || 0) + 1;
                    
                    // 检查是否无效文件
                    if (isInvalidFile(fullPath, item)) {
                        stats.invalidFiles.push({
                            path: relPath,
                            size: stat.size,
                            reason: '匹配无效文件模式'
                        });
                        stats.skippedFiles++;
                        console.log(`跳过无效文件: ${relPath} (${stat.size} bytes)`);
                        continue;
                    }
                    
                    // 复制文件到备份目录
                    const targetPath = path.join(backupRoot, relPath);
                    if (copyFile(fullPath, targetPath)) {
                        stats.backupFiles++;
                        if (stats.backupFiles % 100 === 0) {
                            console.log(`已备份 ${stats.backupFiles} 个文件...`);
                        }
                    }
                }
            } catch (err) {
                console.error(`处理项目失败: ${fullPath}`, err.message);
            }
        }
    } catch (err) {
        console.error(`读取目录失败: ${dir}`, err.message);
    }
}

// 生成报告
function generateReport() {
    const report = {
        timestamp: new Date().toISOString(),
        backupInfo: {
            backupDir: backupRoot,
            sourceDirs: SOURCE_DIRS,
            totalFiles: stats.totalFiles,
            totalSize: formatBytes(stats.totalSize),
            backupFiles: stats.backupFiles,
            skippedFiles: stats.skippedFiles,
            backupRatio: stats.totalFiles > 0 ? (stats.backupFiles / stats.totalFiles * 100).toFixed(2) + '%' : '0%'
        },
        fileTypeDistribution: stats.fileTypes,
        invalidFiles: stats.invalidFiles.slice(0, 100), // 只显示前100个
        invalidFileSummary: {
            total: stats.invalidFiles.length,
            byReason: {
                patternMatch: stats.invalidFiles.filter(f => f.reason === '匹配无效文件模式').length,
                smallSize: stats.invalidFiles.filter(f => f.size < 10).length
            }
        },
        recommendations: []
    };
    
    // 添加建议
    if (stats.invalidFiles.length > 50) {
        report.recommendations.push(`发现 ${stats.invalidFiles.length} 个无效文件，建议清理`);
    }
    
    if (stats.skippedFiles > stats.totalFiles * 0.3) {
        report.recommendations.push(`跳过了 ${stats.skippedFiles} 个文件（占总文件 ${(stats.skippedFiles/stats.totalFiles*100).toFixed(2)}%），建议检查备份完整性`);
    }
    
    // 保存报告
    const reportFile = path.join(reportsDir, 'backup_report.json');
    fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
    
    // 保存无效文件清单
    const invalidFileList = path.join(reportsDir, 'invalid_files_list.txt');
    const invalidContent = stats.invalidFiles.map(f => 
        `${f.path} (${formatBytes(f.size)}) - ${f.reason}`
    ).join('\n');
    fs.writeFileSync(invalidFileList, `无效文件清单 (共${stats.invalidFiles.length}个):\n\n${invalidContent}`);
    
    // 保存摘要报告
    const summaryFile = path.join(reportsDir, 'backup_summary.txt');
    const summaryContent = `
AI24X网站系统完整备份报告
===========================

备份时间: ${new Date().toLocaleString()}
备份目录: ${backupRoot}

📊 备份统计
-----------
总文件数: ${stats.totalFiles} 个
总大小: ${formatBytes(stats.totalSize)}
备份文件: ${stats.backupFiles} 个
跳过文件: ${stats.skippedFiles} 个
备份比例: ${report.backupInfo.backupRatio}

📁 文件类型分布
---------------
${Object.entries(stats.fileTypes)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => `${type}: ${count} 个 (${(count/stats.totalFiles*100).toFixed(2)}%)`)
    .join('\n')}

🚫 无效文件统计
---------------
无效文件总数: ${stats.invalidFiles.length} 个
- 匹配无效模式: ${report.invalidFileSummary.byReason.patternMatch} 个
- 文件过小(<10B): ${report.invalidFileSummary.byReason.smallSize} 个

📋 无效文件示例 (前20个)
-----------------------
${stats.invalidFiles.slice(0, 20).map(f => `• ${f.path} (${formatBytes(f.size)})`).join('\n')}

💡 建议
-------
${report.recommendations.length > 0 ? report.recommendations.join('\n') : '备份完成，无特别建议'}

📁 备份内容
-----------
1. AI24X网站系统: ${SOURCE_DIRS[0]}
2. AI24X平台核心: ${SOURCE_DIRS[1]}
3. AI工具目录项目: ${SOURCE_DIRS[2]}

🔗 报告文件
----------
1. 详细报告: ${reportFile}
2. 无效文件清单: ${invalidFileList}
3. 本摘要: ${summaryFile}

备份完成时间: ${new Date().toLocaleString()}
    `.trim();
    
    fs.writeFileSync(summaryFile, summaryContent);
    
    return report;
}

// 格式化字节大小
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 主函数
async function main() {
    console.log('开始备份AI24X网站系统...');
    console.log('='.repeat(50));
    
    // 备份每个目录
    for (const sourceDir of SOURCE_DIRS) {
        if (fs.existsSync(sourceDir)) {
            console.log(`\n备份目录: ${sourceDir}`);
            walkDir(sourceDir, path.basename(sourceDir));
        } else {
            console.log(`目录不存在: ${sourceDir}`);
        }
    }
    
    console.log('\n' + '='.repeat(50));
    console.log('备份完成，生成报告...');
    
    // 生成报告
    const report = generateReport();
    
    console.log('\n📊 备份完成摘要:');
    console.log(`备份目录: ${backupRoot}`);
    console.log(`总文件数: ${stats.totalFiles}`);
    console.log(`备份文件: ${stats.backupFiles}`);
    console.log(`跳过文件: ${stats.skippedFiles}`);
    console.log(`总大小: ${formatBytes(stats.totalSize)}`);
    console.log(`无效文件: ${stats.invalidFiles.length} 个`);
    
    // 显示文件类型分布
    console.log('\n📁 文件类型分布:');
    const sortedTypes = Object.entries(stats.fileTypes)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    
    sortedTypes.forEach(([type, count]) => {
        const percentage = (count / stats.totalFiles * 100).toFixed(2);
        console.log(`  ${type}: ${count} 个 (${percentage}%)`);
    });
    
    // 显示无效文件示例
    if (stats.invalidFiles.length > 0) {
        console.log('\n🚫 无效文件示例 (前10个):');
        stats.invalidFiles.slice(0, 10).forEach((file, index) => {
            console.log(`  ${index + 1}. ${file.path} (${formatBytes(file.size)})`);
        });
    }
    
    console.log('\n✅ 备份完成！');
    console.log(`报告文件保存在: ${path.join(backupRoot, 'reports')}`);
    
    return {
        backupDir: backupRoot,
        stats: stats,
        reportPath: path.join(backupRoot, 'reports')
    };
}

// 执行备份
main().catch(err => {
    console.error('备份过程中出错:', err);
    process.exit(1);
});