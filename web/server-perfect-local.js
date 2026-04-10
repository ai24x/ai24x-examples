/**
 * AI24X网站服务 - 完美本地版（美观+纯本地）
 * 版本: 3.0.0
 * 创建时间: 2026-03-19
 * 功能: 静态文件服务 + 自动本地化 + 美观图标
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;
const projectDir = __dirname;

// 完美本地化处理函数
function perfectLocalizeHTML(content) {
    // 1. 移除所有外部CDN链接
    content = content.replace(/<link[^>]*href=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    content = content.replace(/<script[^>]*src=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    
    // 2. 移除不存在的CSS文件引用
    content = content.replace(/<link[^>]*href=["']spacing-unified\.css["'][^>]*>/gi, '');
    
    // 3. 替换为本地CSS链接
    const localCSS = `
    <!-- 100% 本地图标 + 字体 -->
    <link rel="stylesheet" href="/font-awesome-local.css">
    <link rel="stylesheet" href="/fonts-local.css">
    `;
    
    // 4. 添加宽松的CSP meta标签（如果不存在）
    if (!content.includes('Content-Security-Policy')) {
        const cspMeta = `
    <!-- 纯本地安全策略（完美不报错） -->
    <meta http-equiv="Content-Security-Policy" content="
        default-src 'self';
        style-src 'self' 'unsafe-inline';
        font-src 'self';
        img-src 'self' data:;
    ">`;
        
        // 插入到head标签内
        content = content.replace(/<head>/i, `<head>${cspMeta}`);
    }
    
    // 5. 确保本地CSS被正确引用
    // 找到</head>标签，在它前面插入本地CSS
    const headEnd = content.indexOf('</head>');
    if (headEnd !== -1) {
        // 检查是否已经有本地CSS
        if (!content.includes('font-awesome-local.css')) {
            content = content.slice(0, headEnd) + localCSS + content.slice(headEnd);
        }
    }
    
    // 6. 修复图标类名（fas → fa）
    content = content.replace(/class="fas fa-/g, 'class="fa fa-');
    content = content.replace(/class='fas fa-/g, "class='fa fa-");
    content = content.replace(/class="fab fa-/g, 'class="fa fa-');
    content = content.replace(/class='fab fa-/g, "class='fa fa-");
    
    return content;
}

// 创建HTTP服务器
const server = http.createServer((req, res) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
    
    // 路由处理
    let filePath = '';
    
    // 首页
    if (req.url === '/' || req.url === '/index.html') {
        filePath = path.join(projectDir, 'index.html');
    }
    // 工具库 - 支持多种路径
    else if (req.url === '/tools' || req.url === '/tools.html' || req.url === '/tools-index.html') {
        filePath = path.join(projectDir, 'tools-index.html');
    }
    // 教程 - 支持目录和文件
    else if (req.url === '/tutorials' || req.url === '/tutorials.html' || req.url === '/tutorials/index.html') {
        filePath = path.join(projectDir, 'tutorials', 'index.html');
    }
    // 定制页面
    else if (req.url === '/custom' || req.url === '/custom.html') {
        filePath = path.join(projectDir, 'custom.html');
    }
    // 登录页面
    else if (req.url === '/login' || req.url === '/login.html') {
        filePath = path.join(projectDir, 'login.html');
    }
    // 注册页面
    else if (req.url === '/signup' || req.url === '/signup.html') {
        filePath = path.join(projectDir, 'signup.html');
    }
    // 本地CSS文件
    else if (req.url === '/font-awesome-local.css') {
        filePath = path.join(projectDir, 'font-awesome-local.css');
    }
    else if (req.url === '/fonts-local.css') {
        filePath = path.join(projectDir, 'fonts-local.css');
    }
    // 工具详情页面 - 支持 /tools/xxx.html
    else if (req.url.startsWith('/tools/') && req.url.endsWith('.html')) {
        const toolFile = req.url.substring('/tools/'.length);
        filePath = path.join(projectDir, 'tools', toolFile);
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
        
        // 如果是HTML文件，进行完美本地化处理
        if (ext === '.html') {
            data = perfectLocalizeHTML(data);
        }
        
        // 发送响应
        res.end(data);
    });
});

// 启动服务器
server.listen(PORT, () => {
    console.log('🚀 AI24X完美本地网站服务启动成功！');
    console.log(`📊 访问地址: http://localhost:${PORT}`);
    console.log(`⏰ 启动时间: ${new Date().toLocaleString()}`);
    console.log(`📁 服务目录: ${projectDir}`);
    console.log('🎨 特性: 美观图标 + 纯本地 + 零外部依赖');
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