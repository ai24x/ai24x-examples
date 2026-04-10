/**
 * AI24X网站服务 - 纯净版（不修改HTML）
 * 版本: 1.0.0
 * 创建时间: 2026-03-19
 * 功能: 静态文件服务，完全不修改HTML内容
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;
const projectDir = __dirname;

// 创建HTTP服务器
const server = http.createServer((req, res) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
    
    // 路由处理
    let filePath = '';
    
    // 首页
    if (req.url === '/' || req.url === '/index.html') {
        filePath = path.join(projectDir, 'index.html');
    }
    // 工具库
    else if (req.url === '/tools' || req.url === '/tools.html' || req.url === '/tools-index.html' || req.url === '/tools-fixed.html') {
        filePath = path.join(projectDir, 'tools-fixed.html');
    }
    // 教程
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
    // 测试页面
    else if (req.url === '/test' || req.url === '/test-simple.html') {
        filePath = path.join(projectDir, 'test-simple.html');
    }
    // 静态文件
    else {
        filePath = path.join(projectDir, req.url);
    }
    
    // 检查文件扩展名
    const ext = path.extname(filePath).toLowerCase();
    
    // 检查是否是目录
    fs.stat(filePath, (err, stats) => {
        if (err) {
            console.error(`文件访问错误: ${filePath}`, err);
            res.statusCode = 404;
            res.end('404 - 文件未找到');
            return;
        }
        
        // 如果是目录，尝试读取index.html
        if (stats.isDirectory()) {
            const indexPath = path.join(filePath, 'index.html');
            fs.readFile(indexPath, 'utf8', (err, data) => {
                if (err) {
                    console.error(`目录索引文件读取错误: ${indexPath}`, err);
                    res.statusCode = 404;
                    res.end('404 - 目录索引未找到');
                    return;
                }
                
                // 设置Content-Type并发送
                res.setHeader('Content-Type', 'text/html; charset=utf-8');
                res.end(data);
            });
            return;
        }
        
        // 如果是文件，正常读取
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
        
        // 不修改任何内容，直接发送
        res.end(data);
    });
});

// 启动服务器
server.listen(PORT, () => {
    console.log(`========================================`);
    console.log(`AI24X网站服务 - 纯净版`);
    console.log(`版本: 1.0.0`);
    console.log(`启动时间: ${new Date().toLocaleString()}`);
    console.log(`监听端口: ${PORT}`);
    console.log(`项目目录: ${projectDir}`);
    console.log(`访问地址: http://localhost:${PORT}`);
    console.log(`========================================`);
    console.log(`重要说明:`);
    console.log(`1. 此服务器不修改任何HTML内容`);
    console.log(`2. 所有文件按原样提供`);
    console.log(`3. 确保HTML文件已正确修复`);
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