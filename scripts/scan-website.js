/**
 * AI24X网站全面扫描工具
 * 扫描所有页面和链接，生成问题报告
 */

const fs = require('fs');
const path = require('path');
const { safeWriter } = require('../safe-write');

// 扫描结果
const scanResults = {
    totalPages: 0,
    totalLinks: 0,
    brokenLinks: 0,
    emptyPages: 0,
    redirectPages: 0,
    styleIssues: 0,
    pages: [],
    issues: []
};

// 已知的页面路径
const knownPages = [
    '/',              // 首页
    '/en',            // 英文首页
    '/tools',         // AI工具库
    '/categories',    // 分类
    '/rankings',      // 热门排行
    '/recommendations', // 个性推荐
    '/tutorials',     // 教程
    '/about',         // 关于
    '/signup',        // 注册
    '/login',         // 登录
    '/share',         // 分享
    '/contact',       // 联系我们
    '/privacy',       // 隐私政策
    '/terms',         // 服务条款
    '/faq',           // 常见问题
    '/sitemap',       // 网站地图
    '/accessibility', // 无障碍访问
    '/status',        // 系统状态
    '/health',        // 健康检查
    '/self-contained' // 自包含版本
];

// 扫描所有HTML文件
async function scanHTMLFiles() {
    console.log('🔍 开始扫描HTML文件...');
    
    const htmlFiles = [];
    const directory = process.cwd();
    
    // 递归扫描目录
    function scanDir(dir) {
        const files = fs.readdirSync(dir);
        
        files.forEach(file => {
            const filePath = path.join(dir, file);
            const stat = fs.statSync(filePath);
            
            if (stat.isDirectory()) {
                // 跳过node_modules等目录
                if (!file.startsWith('.') && file !== 'node_modules') {
                    scanDir(filePath);
                }
            } else if (file.endsWith('.html')) {
                htmlFiles.push({
                    path: filePath,
                    relativePath: path.relative(directory, filePath),
                    name: file
                });
            }
        });
    }
    
    scanDir(directory);
    
    console.log(`📁 找到 ${htmlFiles.length} 个HTML文件`);
    return htmlFiles;
}

// 分析HTML文件
async function analyzeHTMLFile(fileInfo) {
    const result = {
        file: fileInfo.relativePath,
        exists: true,
        fileSize: 0,
        lines: 0,
        links: [],
        issues: [],
        hasMainStyle: false,
        hasHeader: false,
        hasFooter: false,
        contentLength: 0
    };
    
    try {
        const content = await safeWriter.readFile(fileInfo.path);
        result.fileSize = Buffer.byteLength(content, 'utf8');
        result.lines = content.split('\n').length;
        result.contentLength = content.length;
        
        // 检查是否引用主站样式
        result.hasMainStyle = content.includes('href="/style.css"') || 
                              content.includes('href="style.css"');
        
        // 检查是否有统一头部
        result.hasHeader = content.includes('class="header"') || 
                          content.includes('id="header"');
        
        // 检查是否有统一页脚
        result.hasFooter = content.includes('class="footer"') || 
                          content.includes('id="footer"');
        
        // 提取所有链接
        const links = extractLinks(content);
        result.links = links;
        
        // 检查链接有效性
        for (const link of links) {
            const linkResult = await checkLink(link, fileInfo.path);
            if (!linkResult.valid) {
                result.issues.push({
                    type: 'broken_link',
                    link: link.href,
                    text: link.text,
                    reason: linkResult.reason
                });
            }
        }
        
        // 检查页面内容
        if (content.length < 1000) {
            result.issues.push({
                type: 'empty_page',
                reason: `页面内容过短 (${content.length} 字符)`
            });
        }
        
        // 检查是否只是跳转页面
        if (content.includes('window.location.href') && content.length < 2000) {
            result.issues.push({
                type: 'redirect_page',
                reason: '页面只是简单跳转，缺少实际内容'
            });
        }
        
        // 检查样式问题
        if (!result.hasMainStyle) {
            result.issues.push({
                type: 'style_issue',
                reason: '未引用主站样式文件'
            });
        }
        
    } catch (error) {
        result.exists = false;
        result.issues.push({
            type: 'file_error',
            reason: error.message
        });
    }
    
    return result;
}

// 提取HTML中的链接
function extractLinks(htmlContent) {
    const links = [];
    
    // 匹配<a>标签
    const linkRegex = /<a\s+(?:[^>]*?\s+)?href=(["'])(.*?)\1[^>]*>(.*?)<\/a>/gi;
    let match;
    
    while ((match = linkRegex.exec(htmlContent)) !== null) {
        const href = match[2];
        const text = match[3].replace(/<[^>]*>/g, '').trim();
        
        // 过滤外部链接和特殊链接
        if (!href.startsWith('http') && 
            !href.startsWith('#') && 
            !href.startsWith('mailto:') && 
            !href.startsWith('tel:')) {
            
            links.push({
                href: href,
                text: text || '[无文本]',
                fullMatch: match[0]
            });
        }
    }
    
    return links;
}

// 检查链接有效性
async function checkLink(link, sourceFile) {
    const result = {
        valid: true,
        reason: 'OK'
    };
    
    // 检查链接是否指向已知页面
    const isKnownPage = knownPages.some(page => link.href === page || link.href.startsWith(page + '/'));
    
    if (!isKnownPage) {
        // 检查文件是否存在
        const targetPath = path.join(path.dirname(sourceFile), link.href);
        
        try {
            if (fs.existsSync(targetPath)) {
                const stat = fs.statSync(targetPath);
                if (stat.isFile()) {
                    const content = await safeWriter.readFile(targetPath);
                    if (content.length < 500) {
                        result.valid = false;
                        result.reason = '目标文件内容过少';
                    }
                }
            } else {
                // 检查是否是路由页面（由服务器处理）
                if (!link.href.includes('.') && !link.href.endsWith('/')) {
                    // 可能是路由，暂时标记为有效
                    result.valid = true;
                    result.reason = '路由链接（由服务器处理）';
                } else {
                    result.valid = false;
                    result.reason = '目标文件不存在';
                }
            }
        } catch (error) {
            result.valid = false;
            result.reason = `检查文件时出错: ${error.message}`;
        }
    }
    
    return result;
}

// 生成扫描报告
function generateReport(results) {
    const report = {
        scanTime: new Date().toISOString(),
        summary: {
            totalPages: results.length,
            pagesWithIssues: results.filter(r => r.issues.length > 0).length,
            totalIssues: results.reduce((sum, r) => sum + r.issues.length, 0),
            issueBreakdown: {
                broken_links: 0,
                empty_pages: 0,
                redirect_pages: 0,
                style_issues: 0,
                file_errors: 0
            }
        },
        detailedResults: results
    };
    
    // 统计问题类型
    results.forEach(page => {
        page.issues.forEach(issue => {
            if (report.summary.issueBreakdown[issue.type]) {
                report.summary.issueBreakdown[issue.type]++;
            }
        });
    });
    
    return report;
}

// 保存报告
async function saveReport(report) {
    const reportDir = path.join(process.cwd(), 'reports');
    if (!fs.existsSync(reportDir)) {
        fs.mkdirSync(reportDir, { recursive: true });
    }
    
    const reportFile = path.join(reportDir, `scan-report-${Date.now()}.json`);
    await safeWriter.writeFile(reportFile, JSON.stringify(report, null, 2));
    
    console.log(`📊 扫描报告已保存: ${reportFile}`);
    
    // 同时生成简明的Markdown报告
    const markdownReport = generateMarkdownReport(report);
    const markdownFile = path.join(reportDir, `scan-report-${Date.now()}.md`);
    await safeWriter.writeFile(markdownFile, markdownReport);
    
    console.log(`📝 Markdown报告已保存: ${markdownFile}`);
    
    return { jsonFile: reportFile, mdFile: markdownFile };
}

// 生成Markdown格式的报告
function generateMarkdownReport(report) {
    let md = `# AI24X网站扫描报告\n\n`;
    md += `**扫描时间**: ${new Date(report.scanTime).toLocaleString('zh-CN')}\n\n`;
    
    // 摘要
    md += `## 📊 扫描摘要\n\n`;
    md += `| 指标 | 数量 |\n`;
    md += `|------|------|\n`;
    md += `| 扫描页面总数 | ${report.summary.totalPages} |\n`;
    md += `| 存在问题页面 | ${report.summary.pagesWithIssues} |\n`;
    md += `| 问题总数 | ${report.summary.totalIssues} |\n\n`;
    
    // 问题分类
    md += `## 🚨 问题分类\n\n`;
    md += `| 问题类型 | 数量 | 说明 |\n`;
    md += `|----------|------|------|\n`;
    md += `| 损坏链接 | ${report.summary.issueBreakdown.broken_links || 0} | 链接指向不存在的文件 |\n`;
    md += `| 空页面 | ${report.summary.issueBreakdown.empty_pages || 0} | 页面内容过少 |\n`;
    md += `| 跳转页面 | ${report.summary.issueBreakdown.redirect_pages || 0} | 只是简单跳转，缺少内容 |\n`;
    md += `| 样式问题 | ${report.summary.issueBreakdown.style_issues || 0} | 未使用统一样式 |\n`;
    md += `| 文件错误 | ${report.summary.issueBreakdown.file_errors || 0} | 文件读取错误 |\n\n`;
    
    // 详细结果
    md += `## 📋 详细结果\n\n`;
    
    const pagesWithIssues = report.detailedResults.filter(page => page.issues.length > 0);
    
    if (pagesWithIssues.length === 0) {
        md += `✅ 所有页面都没有发现问题！\n`;
    } else {
        pagesWithIssues.forEach((page, index) => {
            md += `### ${index + 1}. ${page.file}\n\n`;
            md += `- **文件大小**: ${(page.fileSize / 1024).toFixed(2)} KB\n`;
            md += `- **行数**: ${page.lines}\n`;
            md += `- **引用主样式**: ${page.hasMainStyle ? '✅' : '❌'}\n`;
            md += `- **统一头部**: ${page.hasHeader ? '✅' : '❌'}\n`;
            md += `- **统一页脚**: ${page.hasFooter ? '✅' : '❌'}\n`;
            md += `- **链接数量**: ${page.links.length}\n`;
            md += `- **问题数量**: ${page.issues.length}\n\n`;
            
            if (page.issues.length > 0) {
                md += `#### 发现的问题:\n\n`;
                page.issues.forEach((issue, issueIndex) => {
                    md += `${issueIndex + 1}. **${issue.type}**: ${issue.reason}\n`;
                    if (issue.link) {
                        md += `   - 链接: ${issue.link}\n`;
                    }
                    if (issue.text) {
                        md += `   - 链接文本: ${issue.text}\n`;
                    }
                });
                md += '\n';
            }
        });
    }
    
    // 修复建议
    md += `## 🛠️ 修复建议\n\n`;
    md += `### 优先级排序\n\n`;
    md += `1. **P0 - 紧急修复** (今晚完成)\n`;
    md += `   - 损坏的导航链接\n`;
    md += `   - 核心功能页面不存在\n`;
    md += `   - 严重影响用户体验的问题\n\n`;
    
    md += `2. **P1 - 重要修复** (明晚完成)\n`;
    md += `   - 空页面和跳转页面\n`;
    md += `   - 样式不统一问题\n`;
    md += `   - 功能不完整页面\n\n`;
    
    md += `3. **P2 - 优化改进** (后续完成)\n`;
    md += `   - 性能优化\n`;
    md += `   - 用户体验改进\n`;
    md += `   - SEO优化\n\n`;
    
    md += `### 具体行动项\n\n`;
    md += `1. **立即检查以下页面**:\n`;
    
    const urgentPages = pagesWithIssues.filter(page => 
        page.issues.some(issue => 
            issue.type === 'broken_link' || 
            issue.type === 'file_error'
        )
    );
    
    if (urgentPages.length > 0) {
        urgentPages.forEach(page => {
            md += `   - ${page.file}\n`;
        });
    } else {
        md += `   ✅ 没有需要立即修复的紧急问题\n`;
    }
    
    md += `\n2. **今晚修复重点**:\n`;
    md += `   - /tools 页面 (AI工具库)\n`;
    md += `   - 核心导航页面\n`;
    md += `   - 用户功能页面\n\n`;
    
    md += `3. **明晚修复重点**:\n`;
    md += `   - 所有空页面和跳转页面\n`;
    md += `   - 样式统一问题\n`;
    md += `   - 生成帮助文档\n\n`;
    
    md += `---\n\n`;
    md += `*报告生成时间: ${new Date().toLocaleString('zh-CN')}*\n`;
    md += `*扫描工具: AI24X网站扫描器 v1.0*\n`;
    
    return md;
}

// 主函数
async function main() {
    console.log('🚀 AI24X网站全面扫描开始');
    console.log('========================\n');
    
    try {
        // 1. 扫描所有HTML文件
        const htmlFiles = await scanHTMLFiles();
        
        // 2. 分析每个HTML文件
        console.log('🔬 分析HTML文件...');
        const results = [];
        
        for (const file of htmlFiles) {
            console.log(`  分析: ${file.relativePath}`);
            const result = await analyzeHTMLFile(file);
            results.push(result);
            
            // 显示问题数量
            if (result.issues.length > 0) {
                console.log(`    ⚠️ 发现 ${result.issues.length} 个问题`);
            }
        }
        
        // 3. 生成报告
        console.log('\n📊 生成扫描报告...');
        const report = generateReport(results);
        
        // 4. 保存报告
        const reportFiles = await saveReport(report);
        
        // 5. 显示摘要
        console.log('\n🎉 扫描完成！');
        console.log('=============\n');
        
        console.log('📈 扫描摘要:');
        console.log(`   扫描页面: ${report.summary.totalPages}`);
        console.log(`   存在问题页面: ${report.summary.pagesWithIssues}`);
        console.log(`   问题总数: ${report.summary.totalIssues}\n`);
        
        if (report.summary.issueBreakdown.broken_links > 0) {
            console.log(`🚨 紧急问题: ${report.summary.issueBreakdown.broken_links} 个损坏链接需要立即修复！`);
        }
        
        console.log('\n📁 报告文件:');
        console.log(`   JSON报告: ${reportFiles.jsonFile}`);
        console.log(`   Markdown报告: ${reportFiles.mdFile}`);
        
        console.log('\n🛠️ 下一步:');
        console.log('   1. 查看详细报告了解具体问题');
        console.log('   2. 按照优先级开始修复');
        console.log('   3. 首先修复/tools页面和核心导航');
        
    } catch (error) {
        console.error('❌ 扫描过程中出错:', error.message);
        process.exit(1);
    }
}

// 执行
if (require.main === module) {
    main();
}

module.exports = {
    scanHTMLFiles,
    analyzeHTMLFile,
    extractLinks,
    checkLink,
    generateReport,
    saveReport,
    generateMarkdownReport
};