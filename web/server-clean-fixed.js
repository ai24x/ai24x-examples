/**
 * AI24X网站服务 - 纯净版（不修改HTML）
 * 版本: 1.1.0
 * 创建时间: 2026-03-19
 * 功能: 静态文件服务，支持目录访问，完全不修改HTML内容
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

// 从命令行参数获取端口，默认3000
const PORT = process.argv[2] ? parseInt(process.argv[2]) : 3000;
const projectDir = __dirname;

// 创建HTTP服务器
const server = http.createServer((req, res) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
    
    // 路由处理
    let filePath = '';
    
    // 解析URL，移除查询参数
    const urlPath = req.url.split('?')[0];
    
    // 首页
    if (urlPath === '/' || urlPath === '/index.html') {
        filePath = path.join(projectDir, 'index.html');
    }
    // 工具库 - 支持带查询参数的URL
    else if (urlPath === '/tools' || urlPath === '/tools.html' || urlPath === '/tools-index.html' || urlPath === '/tools-fixed.html') {
        filePath = path.join(projectDir, 'tools-index.html');
    }
    // 动态工具库页面
    else if (urlPath === '/tools-dynamic' || urlPath === '/tools-dynamic.html') {
        filePath = path.join(projectDir, 'tools-dynamic.html');
    }
    // 教程页面
    else if (urlPath === '/tutorials' || urlPath === '/tutorials.html') {
        filePath = path.join(projectDir, 'tutorials', 'index.html');
    }
    // 自定义页面
    else if (urlPath === '/custom' || urlPath === '/custom.html') {
        filePath = path.join(projectDir, 'custom.html');
    }
    // 登录页面
    else if (urlPath === '/login' || urlPath === '/login.html') {
        filePath = path.join(projectDir, 'login.html');
    }
    // 注册页面
    else if (urlPath === '/signup' || urlPath === '/signup.html') {
        filePath = path.join(projectDir, 'signup.html');
    }
    // 实时排行页面
    else if (urlPath === '/rankings' || urlPath === '/rankings.html') {
        filePath = path.join(projectDir, 'rankings-index.html');
    }
    // 分类页面
    else if (urlPath === '/categories' || urlPath === '/categories.html') {
        filePath = path.join(projectDir, 'categories.html');
    }
    // 用户中心页面
    else if (urlPath === '/user-center' || urlPath === '/user-center.html') {
        filePath = path.join(projectDir, 'user-center.html');
    }
    // 用户中心测试页面
    else if (urlPath === '/test-user-center' || urlPath === '/test-user-center.html') {
        filePath = path.join(projectDir, 'test-user-center.html');
    }
    // 测试页面
    else if (urlPath === '/test' || urlPath === '/test-simple.html') {
        filePath = path.join(projectDir, 'test-simple.html');
    }
    // 动态工具测试页面
    else if (urlPath === '/test-dynamic' || urlPath === '/test-dynamic.html') {
        filePath = path.join(projectDir, 'test-dynamic.html');
    }
    // 静态文件
    else {
        filePath = path.join(projectDir, urlPath);
    }
    
    // 处理文件请求
    serveFile(filePath, req, res);
});

// 文件服务函数
function serveFile(filePath, req, res) {
    // 安全检查：确保文件在项目目录内
    const normalizedPath = path.normalize(filePath);
    if (!normalizedPath.startsWith(projectDir)) {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('403 Forbidden');
        return;
    }
    
    // 检查文件是否存在
    fs.stat(filePath, (err, stats) => {
        if (err || !stats.isFile()) {
            // 如果是目录，尝试查找index.html
            if (stats && stats.isDirectory()) {
                const indexFile = path.join(filePath, 'index.html');
                fs.stat(indexFile, (err2, stats2) => {
                    if (err2 || !stats2.isFile()) {
                        res.writeHead(404, { 'Content-Type': 'text/plain' });
                        res.end('404 Not Found');
                    } else {
                        serveStaticFile(indexFile, res);
                    }
                });
            } else {
                res.writeHead(404, { 'Content-Type': 'text/plain' });
                res.end('404 Not Found');
            }
            return;
        }
        
        // 提供静态文件
        serveStaticFile(filePath, res);
    });
}

// 提供静态文件
function serveStaticFile(filePath, res) {
    const ext = path.extname(filePath).toLowerCase();
    const contentType = getContentType(ext);
    
    fs.readFile(filePath, (err, data) => {
        if (err) {
            res.writeHead(500, { 'Content-Type': 'text/plain' });
            res.end('500 Internal Server Error');
            return;
        }
        
        res.writeHead(200, {
            'Content-Type': contentType,
            'Cache-Control': 'public, max-age=0'
        });
        res.end(data);
    });
}

// 获取内容类型
function getContentType(ext) {
    const types = {
        '.html': 'text/html; charset=UTF-8',
        '.htm': 'text/html; charset=UTF-8',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.txt': 'text/plain',
        '.pdf': 'application/pdf',
        '.zip': 'application/zip'
    };
    
    return types[ext] || 'application/octet-stream';
}

// 启动服务器 - 监听所有网络接口
server.listen(PORT, '0.0.0.0', () => {
    console.log(`========================================`);
    console.log(`AI24X网站服务 - 纯净修复版`);
    console.log(`版本: 1.1.0`);
    console.log(`启动时间: ${new Date().toLocaleString()}`);
    console.log(`监听端口: ${PORT}`);
    console.log(`监听地址: 0.0.0.0 (所有网络接口)`);
    console.log(`项目目录: ${projectDir}`);
    console.log(`访问地址: http://localhost:${PORT}`);
    console.log(`外部访问: http://123.207.199.238:${PORT}`);
    console.log(`域名访问: http://www.ai24x.com:${PORT}`);
    console.log(`========================================`);
    console.log(`重要说明:`);
    console.log(`1. 此服务器不修改任何HTML内容`);
    console.log(`2. 支持目录访问（自动查找index.html）`);
    console.log(`3. 所有文件按原样提供`);
    console.log(`4. 已修复缺失文件问题`);
    console.log(`========================================`);
});

// 优雅关闭
process.on('SIGINT', () => {
    console.log('\n服务器正在关闭...');
    server.close(() => {
        console.log('服务器已关闭');
        process.exit(0);
    });
});