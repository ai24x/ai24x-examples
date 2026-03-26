/**
 * AI24X网站服务 - 统一完美本地版
 * 版本: 4.0.0
 * 创建时间: 2026-03-19
 * 功能: 静态文件服务 + 自动统一头部 + 完美本地化
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;
const projectDir = __dirname;

// 读取统一头部配置
const unifiedHeaderPath = path.join(projectDir, 'header-unified-perfect.html');
let unifiedHeader = '';

try {
    unifiedHeader = fs.readFileSync(unifiedHeaderPath, 'utf8');
    console.log('✅ 统一头部配置文件加载成功');
} catch (err) {
    console.error('❌ 无法加载统一头部配置文件:', err.message);
    unifiedHeader = `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI24X</title>
        <link rel="stylesheet" href="/font-awesome-local.css">
        <link rel="stylesheet" href="/fonts-local.css">
    </head>
    <body>
        <main class="main-content">`;
}

// 提取统一头部的各个部分
function extractHeaderSections(headerContent) {
    const sections = {
        head: '',
        header: '',
        footer: '',
        scripts: ''
    };
    
    // 提取<head>部分
    const headMatch = headerContent.match(/<head>([\s\S]*?)<\/head>/i);
    if (headMatch) {
        sections.head = headMatch[1];
    }
    
    // 提取<header>部分
    const headerMatch = headerContent.match(/<header[\s\S]*?>([\s\S]*?)<\/header>/i);
    if (headerMatch) {
        sections.header = headerMatch[0];
    }
    
    // 提取<footer>部分
    const footerMatch = headerContent.match(/<footer[\s\S]*?>([\s\S]*?)<\/footer>/i);
    if (footerMatch) {
        sections.footer = footerMatch[0];
    }
    
    // 提取<script>部分（在header之后，main之前）
    const mainIndex = headerContent.indexOf('<main');
    if (mainIndex !== -1) {
        const beforeMain = headerContent.substring(0, mainIndex);
        const scriptMatch = beforeMain.match(/<script[\s\S]*?>([\s\S]*?)<\/script>/gi);
        if (scriptMatch) {
            sections.scripts = scriptMatch.join('\n');
        }
    }
    
    return sections;
}

// 统一头部处理函数
function applyUnifiedHeader(content, pageTitle = 'AI24X') {
    const sections = extractHeaderSections(unifiedHeader);
    
    // 1. 移除所有外部CDN链接
    content = content.replace(/<link[^>]*href=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    content = content.replace(/<script[^>]*src=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    
    // 2. 移除不存在的CSS文件引用
    content = content.replace(/<link[^>]*href=["']spacing-unified\.css["'][^>]*>/gi, '');
    
    // 3. 提取页面特定内容（在<body>标签内）
    let pageContent = '';
    const bodyMatch = content.match(/<body[\s\S]*?>([\s\S]*?)<\/body>/i);
    if (bodyMatch) {
        pageContent = bodyMatch[1];
        
        // 移除可能存在的header和footer
        pageContent = pageContent.replace(/<header[\s\S]*?>[\s\S]*?<\/header>/gi, '');
        pageContent = pageContent.replace(/<footer[\s\S]*?>[\s\S]*?<\/footer>/gi, '');
        
        // 提取main内容或整个内容
        const mainMatch = pageContent.match(/<main[\s\S]*?>([\s\S]*?)<\/main>/i);
        if (mainMatch) {
            pageContent = mainMatch[1];
        }
    }
    
    // 4. 构建统一页面
    const unifiedPage = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>${pageTitle}</title>
    
    <!-- 统一安全策略 -->
    <meta http-equiv="Content-Security-Policy" content="
        default-src 'self';
        style-src 'self' 'unsafe-inline';
        font-src 'self';
        img-src 'self' data:;
    ">
    
    <!-- 统一CSS文件 -->
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="header-unified.css">
    <link rel="stylesheet" href="spacing-unified.css">
    <link rel="stylesheet" href="mobile-fix.css">
    
    <!-- 100%本地图标 + 字体 -->
    <link rel="stylesheet" href="font-awesome-local.css">
    <link rel="stylesheet" href="fonts-local.css">
    
    <style>
        /* 统一系统字体 */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
        }
    </style>
</head>
<body>
    ${sections.header}
    
    ${sections.scripts}
    
    <main class="main-content">
        ${pageContent}
    </main>
    
    ${sections.footer}
</body>
</html>`;
    
    // 5. 修复图标类名（fas → fa）
    let finalContent = unifiedPage.replace(/class="fas fa-/g, 'class="fa fa-');
    finalContent = finalContent.replace(/class='fas fa-/g, "class='fa fa-");
    finalContent = finalContent.replace(/class="fab fa-/g, 'class="fa fa-');
    finalContent = finalContent.replace(/class='fab fa-/g, "class='fa fa-");
    
    return finalContent;
}

// 创建HTTP服务器
const server = http.createServer((req, res) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
    
    // 路由处理
    let filePath = '';
    let pageTitle = 'AI24X';
    
    // 首页
    if (req.url === '/' || req.url === '/index.html') {
        filePath = path.join(projectDir, 'index.html');
        pageTitle = 'AI24X - 发现AI未来，就在AI24X';
    }
    // 工具库
    else if (req.url === '/tools' || req.url === '/tools.html' || req.url === '/tools-index.html') {
        filePath = path.join(projectDir, 'tools-index-fixed.html');
        pageTitle = 'AI工具库 - AI24X';
    }
    // 教程
    else if (req.url === '/tutorials' || req.url === '/tutorials.html' || req.url === '/tutorials/index.html') {
        filePath = path.join(projectDir, 'tutorials', 'index.html');
        pageTitle = '热门教程 - AI24X';
    }
    // 定制页面
    else if (req.url === '/custom' || req.url === '/custom.html') {
        filePath = path.join(projectDir, 'custom.html');
        pageTitle = '定制开发 - AI24X';
    }
    // 登录页面
    else if (req.url === '/login' || req.url === '/login.html') {
        filePath = path.join(projectDir, 'login.html');
        pageTitle = '登录 - AI24X';
    }
    // 注册页面
    else if (req.url === '/signup' || req.url === '/signup.html') {
        filePath = path.join(projectDir, 'signup.html');
        pageTitle = '注册 - AI24X';
    }
    // 本地CSS文件
    else if (req.url === '/font-awesome-local.css') {
        filePath = path.join(projectDir, 'font-awesome-local.css');
    }
    else if (req.url === '/fonts-local.css') {
        filePath = path.join(projectDir, 'fonts-local.css');
    }
    // 其他CSS文件
    else if (req.url.endsWith('.css')) {
        filePath = path.join(projectDir, req.url.substring(1));
    }
    // 静态文件
    else {
        filePath = path.join(projectDir, req.url);
    }
    
    // 检查文件扩展名
    const ext = path.extname(filePath).toLowerCase();
    
    // 读取文件
    fs.readFile(filePath, 'utf8', (err, data) => {
        if (err) {
            console.error(`文件读取错误: ${filePath}`, err);
            res.statusCode = 404;
            res.end('404 - 文件未找到');
            return;
        }
        
        // 设置Content-Type
        const contentType = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.json': 'application/json'
        }[ext] || 'text/plain';
        
        res.setHeader('Content-Type', contentType);
        
        // 如果是HTML文件，应用统一头部
        if (ext === '.html') {
            data = applyUnifiedHeader(data, pageTitle);
        }
        
        // 发送响应
        res.end(data);
    });
});

// 启动服务器
server.listen(PORT, () => {
    console.log('🚀 AI24X统一完美本地网站服务启动成功！');
    console.log(`📊 访问地址: http://localhost:${PORT}`);
    console.log(`⏰ 启动时间: ${new Date().toLocaleString()}`);
    console.log(`📁 服务目录: ${projectDir}`);
    console.log('🎨 特性: 统一头部 + 美观图标 + 纯本地');
    console.log('🔧 图标: 本地Font Awesome样式');
    console.log('🔤 字体: 本地系统字体');
    console.log('🔄 服务运行中...');
});

// 优雅关闭
process.on('SIGINT', () => {
    console.log('\n🛑 正在关闭服务器...');
    server.close(() => {
        console.log('✅ 服务器已关闭');
        process.exit(0);
    });
});