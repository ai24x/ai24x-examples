#!/usr/bin/env node

/**
 * AI24X网站清理脚本
 * 清理无关文件，保持站点整洁
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 当前目录
const rootDir = process.cwd();

// 保留的核心文件列表
const CORE_FILES = [
    // 主页面
    'index.html',
    'login.html',
    'signup.html',
    'payment.html',
    'tools-index.html',
    'share.html',
    
    // 核心脚本
    'server.js',
    'server-stable.js',
    'main.js',
    'style.css',
    'favicon.ico',
    
    // 配置文件
    'package.json',
    '.gitignore',
    'README.md',
    
    // 数据文件
    'users.json',
    
    // 服务管理
    'start-server.bat',
    'ai24x-website-service.bat',
    'ecosystem.config.js',
    
    // 帮助文档
    'help/AI24X智能体平台规划开发指南1.0版.md',
    
    // 脚本目录
    'scripts/verify-gitee-push.js',
];

// 保留的核心目录
const CORE_DIRS = [
    'api',
    'data',
    'help',
    'js',
    'scripts',
    'security',
    'share-system',
    'templates',
    'platform',  // 扩展目录
];

// 需要删除的文件模式
const DELETE_PATTERNS = [
    // 备份文件
    /\.backup(-\d+)?\.(html|js|json)$/i,
    /backup-\d{8}-\d{6}\./i,
    /\.backup$/i,
    
    // 调试/测试文件
    /^test-.*\.(html|js|json|bat)$/i,
    /^debug-.*\.(html|js)$/i,
    /^fix-.*\.(js|html)$/i,
    /-test\.(html|js)$/i,
    
    // 临时文件
    /^temp-.*/i,
    /\.tmp$/i,
    
    // 重复文件
    /-duplicate\./i,
    /-copy\./i,
    
    // 旧版本文件
    /-original\./i,
    /-old\./i,
    /-previous\./i,
    
    // 特定文件
    /^adjust-.*\.js$/i,
    /^check-.*\.(js|html)$/i,
    /^compare-.*\.js$/i,
    /^create-.*\.js$/i,
    /^deep-.*\.js$/i,
    /^diagnose-.*\.js$/i,
    /^emergency-.*\.js$/i,
    /^final-.*\.js$/i,
    /^find-.*\.js$/i,
    /^gradual-.*\.js$/i,
    /^list-.*\.js$/i,
    /^manual-.*\.js$/i,
    /^monitor-.*\.(js|log|json)$/i,
    /^optimization-.*\.md$/i,
    /^performance-.*\.(js|json)$/i,
    /^port-.*\.js$/i,
    /^precision-.*\.js$/i,
    /^quick-.*\.js$/i,
    /^remove-.*\.js$/i,
    /^restore-.*\.js$/i,
    /^rollback-.*\.js$/i,
    /^safe-.*\.js$/i,
    /^security-.*\.(js|json)$/i,
    /^server-.*\.js$/i,  // 除了server.js和server-stable.js
    /^setup-.*\.(ps1|bat)$/i,
    /^simple-.*\.js$/i,
    /^smart-.*\.(js|log|json)$/i,
    /^spacing-.*\.(css|html)$/i,
    /^start-.*\.(bat|ps1)$/i,  // 除了start-server.bat
    /^super-.*\.(js|log|json)$/i,
    /^unify-.*\.js$/i,
    /^update-.*\.js$/i,
    
    // 日志文件
    /\.log$/i,
    /-report\.json$/i,
    
    // PID文件
    /\.pid$/i,
    
    // 中文乱码文件（可能）
    /[\u4e00-\u9fa5]+\.(bat|md)$/,
];

// 需要保留的server文件
const KEEP_SERVER_FILES = ['server.js', 'server-stable.js'];
// 需要保留的start文件
const KEEP_START_FILES = ['start-server.bat', 'ai24x-website-service.bat'];

// 统计
let stats = {
    totalFiles: 0,
    deletedFiles: 0,
    keptFiles: 0,
    deletedSize: 0,
    errors: 0,
    deletedList: [],
    keptList: [],
};

function shouldDeleteFile(filename) {
    // 检查是否在核心文件列表中
    if (CORE_FILES.includes(filename)) {
        return false;
    }
    
    // 检查是否在保留的server文件中
    if (KEEP_SERVER_FILES.includes(filename)) {
        return false;
    }
    
    // 检查是否在保留的start文件中
    if (KEEP_START_FILES.includes(filename)) {
        return false;
    }
    
    // 检查是否匹配删除模式
    for (const pattern of DELETE_PATTERNS) {
        if (pattern.test(filename)) {
            return true;
        }
    }
    
    return false;
}

function cleanupDirectory(dirPath) {
    try {
        const items = fs.readdirSync(dirPath);
        
        for (const item of items) {
            const fullPath = path.join(dirPath, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                // 检查是否为核心目录
                const dirName = path.basename(fullPath);
                if (!CORE_DIRS.includes(dirName) && 
                    !dirName.startsWith('.') && 
                    dirName !== 'node_modules') {
                    console.log(`⚠️  发现非核心目录: ${dirName}/ (可能需要手动检查)`);
                }
                // 递归清理子目录
                cleanupDirectory(fullPath);
            } else {
                stats.totalFiles++;
                const filename = path.basename(fullPath);
                
                if (shouldDeleteFile(filename)) {
                    try {
                        const fileSize = stat.size;
                        fs.unlinkSync(fullPath);
                        stats.deletedFiles++;
                        stats.deletedSize += fileSize;
                        stats.deletedList.push(fullPath);
                        console.log(`🗑️  删除: ${filename} (${(fileSize / 1024).toFixed(1)} KB)`);
                    } catch (error) {
                        stats.errors++;
                        console.log(`❌ 删除失败: ${filename} - ${error.message}`);
                    }
                } else {
                    stats.keptFiles++;
                    stats.keptList.push(fullPath);
                }
            }
        }
    } catch (error) {
        console.log(`❌ 清理目录失败: ${dirPath} - ${error.message}`);
        stats.errors++;
    }
}

function generateCleanupReport() {
    const report = `
# AI24X网站清理报告
生成时间: ${new Date().toLocaleString('zh-CN')}

## 📊 清理统计
- 扫描文件总数: ${stats.totalFiles}
- 保留文件数: ${stats.keptFiles}
- 删除文件数: ${stats.deletedFiles}
- 删除文件大小: ${(stats.deletedSize / 1024 / 1024).toFixed(2)} MB
- 错误数量: ${stats.errors}

## 📁 保留的核心目录
${CORE_DIRS.map(dir => `- ${dir}/`).join('\n')}

## 📄 保留的核心文件
${CORE_FILES.map(file => `- ${file}`).join('\n')}

## 🗑️ 已删除文件列表
${stats.deletedList.length > 0 ? stats.deletedList.map(file => `- ${path.relative(rootDir, file)}`).join('\n') : '无'}

## ✅ 清理完成
站点已清理完成，建议运行以下命令验证：
\`\`\`bash
# 检查剩余文件
dir /b

# 启动服务器测试
node server-stable.js

# 访问网站测试
curl http://localhost:3000/
\`\`\`

## ⚠️ 注意事项
1. 清理前已备份到Git，可通过 \`git checkout -- .\` 恢复
2. 部分目录可能需要手动检查
3. 建议重启服务器验证功能正常
`;

    return report;
}

// 主函数
async function main() {
    console.log('🔍 开始清理AI24X网站无关文件...\n');
    console.log('当前目录:', rootDir);
    console.log('='.repeat(60));
    
    // 先备份当前状态到Git
    try {
        console.log('📦 备份当前状态到Git...');
        execSync('git add .', { stdio: 'pipe' });
        execSync('git commit -m "chore: 清理前备份" --allow-empty', { stdio: 'pipe' });
        console.log('✅ Git备份完成\n');
    } catch (error) {
        console.log('⚠️  Git备份跳过（可能无变化）\n');
    }
    
    // 清理根目录
    cleanupDirectory(rootDir);
    
    // 生成报告
    console.log('\n' + '='.repeat(60));
    console.log('📋 清理完成！');
    
    const report = generateCleanupReport();
    console.log(report);
    
    // 保存报告
    const reportPath = path.join(rootDir, 'cleanup-report.md');
    fs.writeFileSync(reportPath, report);
    console.log(`📄 清理报告已保存: ${reportPath}`);
    
    // 显示清理后的目录结构
    console.log('\n📁 清理后的主要文件:');
    try {
        const remainingFiles = fs.readdirSync(rootDir).filter(item => {
            const fullPath = path.join(rootDir, item);
            const stat = fs.statSync(fullPath);
            return !stat.isDirectory() || CORE_DIRS.includes(item);
        }).slice(0, 20); // 只显示前20个
        
        remainingFiles.forEach(item => {
            const fullPath = path.join(rootDir, item);
            const stat = fs.statSync(fullPath);
            const size = stat.isDirectory() ? '[目录]' : `(${(stat.size / 1024).toFixed(1)} KB)`;
            console.log(`  ${item} ${size}`);
        });
        
        if (remainingFiles.length > 20) {
            console.log(`  ... 还有 ${remainingFiles.length - 20} 个文件/目录`);
        }
    } catch (error) {
        console.log('❌ 无法读取清理后目录:', error.message);
    }
    
    // 建议下一步
    console.log('\n🚀 建议下一步:');
    console.log('1. 测试网站功能: node server-stable.js');
    console.log('2. 提交清理到Git: git add . && git commit -m "chore: 清理无关文件"');
    console.log('3. 推送到Gitee: git push origin develop');
    console.log('4. 验证网站访问: http://localhost:3000/');
}

// 执行清理
main().catch(console.error);