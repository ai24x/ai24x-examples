/**
 * AI24X网站服务器 - 极简稳定版
 * 版本: 1.0.0
 * 创建时间: 2026-03-15
 * 特性: 极简、稳定、低内存占用
 */

const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ===== 1. 极简配置 =====

// 禁用不必要的中间件和功能
app.disable('x-powered-by');

// 基础安全头
app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    next();
});

// ===== 2. 静态文件服务（极简版） =====

app.use((req, res, next) => {
    const urlPath = req.path === '/' ? '/index.html' : req.path;
    const filePath = path.join(__dirname, urlPath);
    
    // 检查文件是否存在
    fs.stat(filePath, (err, stats) => {
        if (err || !stats.isFile()) {
            // 文件不存在，检查特殊路由
            if (req.path === '/health') {
                const memory = process.memoryUsage();
                res.json({
                    status: 'healthy',
                    server: 'stable-1.0',
                    memory: {
                        rss: Math.round(memory.rss / 1024 / 1024 * 100) / 100,
                        heapUsed: Math.round(memory.heapUsed / 1024 / 1024 * 100) / 100,
                        heapTotal: Math.round(memory.heapTotal / 1024 / 1024 * 100) / 100
                    },
                    uptime: Math.round(process.uptime()),
                    pid: process.pid
                });
                return;
            }
            
            if (req.path === '/status') {
                res.json({
                    server: 'AI24X Stable Server',
                    version: '1.0.0',
                    memory: process.memoryUsage(),
                    uptime: process.uptime(),
                    pid: process.pid
                });
                return;
            }
            
            // 检查已知路由
            const knownRoutes = {
                '/tools': 'tools-index.html',
                '/tutorials': 'tutorials/index.html',
                '/custom': 'custom.html',
                '/login': 'login.html',
                '/signup': 'signup.html',
                '/register': 'signup.html'
            };
            
            // 处理带斜杠和不带斜杠的路径
            let routePath = req.path;
            if (routePath.endsWith('/') && routePath.length > 1) {
                routePath = routePath.slice(0, -1);
            }
            
            if (knownRoutes[routePath]) {
                const redirectPath = path.join(__dirname, knownRoutes[routePath]);
                fs.stat(redirectPath, (err2, stats2) => {
                    if (!err2 && stats2.isFile()) {
                        res.sendFile(redirectPath);
                    } else {
                        send404(res);
                    }
                });
                return;
            }
            
            send404(res);
            return;
        }
        
        // 发送文件
        const ext = path.extname(filePath).toLowerCase();
        const contentType = getContentType(ext);
        
        res.setHeader('Content-Type', contentType);
        
        // 极简缓存策略
        if (['.html', '.css', '.js'].includes(ext)) {
            res.setHeader('Cache-Control', 'public, max-age=60'); // 1分钟
        } else if (['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico'].includes(ext)) {
            res.setHeader('Cache-Control', 'public, max-age=3600'); // 1小时
        }
        
        const stream = fs.createReadStream(filePath);
        stream.pipe(res);
        
        stream.on('error', () => {
            send404(res);
        });
    });
});

function getContentType(ext) {
    const types = {
        '.html': 'text/html; charset=utf-8',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon'
    };
    return types[ext] || 'text/plain';
}

function send404(res) {
    const notFoundPath = path.join(__dirname, '404.html');
    fs.stat(notFoundPath, (err) => {
        if (!err) {
            res.status(404).sendFile(notFoundPath);
        } else {
            res.status(404).send('404 - Page Not Found');
        }
    });
}

// ===== 3. 内存监控（极简版） =====

let startupTime = Date.now();

setInterval(() => {
    const memory = process.memoryUsage();
    const usedMB = Math.round(memory.heapUsed / 1024 / 1024 * 100) / 100;
    const totalMB = Math.round(memory.heapTotal / 1024 / 1024 * 100) / 100;
    const uptime = Math.round((Date.now() - startupTime) / 1000);
    
    // 每10分钟记录一次状态
    if (uptime % 600 === 0) {
        console.log(`📊 稳定版服务器状态 - 运行 ${Math.floor(uptime/60)} 分钟`);
        console.log(`   💾 内存: ${usedMB}MB / ${totalMB}MB (${Math.round(usedMB/totalMB*100)}%)`);
        console.log(`   🕒 PID: ${process.pid}`);
    }
    
    // 内存使用超过100MB时记录警告
    if (usedMB > 100) {
        console.log(`⚠️ 内存使用较高: ${usedMB}MB`);
    }
}, 60000); // 每分钟检查一次

// ===== 4. 启动服务器 =====

app.listen(PORT, () => {
    const memory = process.memoryUsage();
    const usedMB = Math.round(memory.heapUsed / 1024 / 1024 * 100) / 100;
    
    console.log(`
🚀 === AI24X极简稳定版服务器已启动 ===
📱 端口: ${PORT}, PID: ${process.pid}
💾 内存: ${usedMB}MB (目标: <50MB)
🎯 特性: 极简、稳定、低内存占用
🌐 访问地址:
   本地: http://localhost:${PORT}
   公网: http://42.192.1.93:${PORT}
📊 监控端点:
   健康检查: http://localhost:${PORT}/health
   系统状态: http://localhost:${PORT}/status

🔧 开始时间: ${new Date().toLocaleString()}
    `);
});

// ===== 5. 优雅关闭和错误处理 =====

process.on('SIGTERM', () => {
    console.log('🔄 收到SIGTERM信号，优雅关闭服务器...');
    process.exit(0);
});

process.on('SIGINT', () => {
    console.log('🔄 收到SIGINT信号，优雅关闭服务器...');
    process.exit(0);
});

// 未捕获异常处理 - 记录但不退出
process.on('uncaughtException', (err) => {
    console.error('❌ 未捕获异常 (继续运行):', err.message);
});

process.on('unhandledRejection', (reason) => {
    console.error('❌ 未处理的Promise拒绝 (继续运行):', reason);
});

// ===== 6. 内存优化 =====

// 定期执行垃圾回收（如果启用）
if (global.gc) {
    setInterval(() => {
        global.gc();
        console.log('🧹 执行垃圾回收');
    }, 300000); // 每5分钟一次
}