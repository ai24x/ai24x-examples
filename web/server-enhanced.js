/**
 * AI24X网站服务器 - 增强稳定版（集成支付系统）
 * 版本: 2.0.0
 * 创建时间: 2026-03-18
 * 特性: 极简、稳定、低内存占用 + 支付系统API
 * 负责人: 副脑01（首席开发工程师）
 */

const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ===== 1. 导入支付系统API =====
const paymentAPI = require('./api/payment');

// ===== 2. 极简配置 =====

// 禁用不必要的中间件和功能
app.disable('x-powered-by');

// 基础安全头
app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'; script-src-attr 'none'; upgrade-insecure-requests");
    res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
    res.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
    res.setHeader('Origin-Agent-Cluster', '?1');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    res.setHeader('X-Permitted-Cross-Domain-Policies', 'none');
    next();
});

// 解析JSON请求体
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ===== 3. 静态文件服务（极简版） =====

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
                    server: 'enhanced-2.0',
                    memory: {
                        rss: Math.round(memory.rss / 1024 / 1024 * 100) / 100,
                        heapUsed: Math.round(memory.heapUsed / 1024 / 1024 * 100) / 100,
                        heapTotal: Math.round(memory.heapTotal / 1024 / 1024 * 100) / 100
                    },
                    uptime: Math.round(process.uptime()),
                    pid: process.pid,
                    features: ['payment-system', 'api-endpoints', 'security-headers']
                });
                return;
            }
            
            if (req.path === '/status') {
                res.json({
                    server: 'AI24X Enhanced Server',
                    version: '2.0.0',
                    memory: process.memoryUsage(),
                    uptime: process.uptime(),
                    pid: process.pid,
                    features: ['payment-system', 'api-endpoints', 'security-headers']
                });
                return;
            }
            
            // 检查API路由
            if (req.path.startsWith('/api/')) {
                next(); // 交给API路由处理
                return;
            }
            
            // 检查已知路由
            const knownRoutes = {
                '/tools': 'tools-index.html',
                '/tutorials': 'tutorials/index.html',
                '/custom': 'custom.html',
                '/login': 'login.html',
                '/signup': 'signup.html',
                '/register': 'signup.html',
                '/payment': 'payment.html',
                '/profile': 'profile.html',
                '/forgot-password': 'forgot-password.html'
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
        
        // 设置缓存头（静态资源）
        if (ext.match(/\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$/)) {
            res.setHeader('Cache-Control', 'public, max-age=86400'); // 24小时缓存
        }
        
        res.sendFile(filePath);
    });
});

// ===== 4. 支付系统API集成 =====
paymentAPI(app);

// ===== 5. 基础API路由 =====

// 用户注册API（简化版）
app.post('/api/register', (req, res) => {
    try {
        const { username, email, password } = req.body;
        
        if (!username || !email || !password) {
            return res.status(400).json({
                success: false,
                error: '缺少必要字段'
            });
        }
        
        // 简化处理 - 实际应该保存到数据库
        res.json({
            success: true,
            message: '注册成功（模拟）',
            data: {
                user_id: `user_${Date.now()}`,
                username: username,
                email: email,
                created_at: new Date().toISOString()
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// 用户登录API（简化版）
app.post('/api/login', (req, res) => {
    try {
        const { email, password } = req.body;
        
        if (!email || !password) {
            return res.status(400).json({
                success: false,
                error: '缺少邮箱或密码'
            });
        }
        
        // 简化处理 - 实际应该验证数据库
        res.json({
            success: true,
            message: '登录成功（模拟）',
            data: {
                user_id: `user_${Date.now()}`,
                email: email,
                token: `token_${Date.now()}_${Math.random().toString(36).substr(2)}`,
                expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// 获取用户信息API
app.get('/api/user/:userId', (req, res) => {
    try {
        const { userId } = req.params;
        
        res.json({
            success: true,
            data: {
                user_id: userId,
                username: '测试用户',
                email: 'test@example.com',
                created_at: new Date().toISOString(),
                subscription: {
                    has_subscription: false,
                    plan: 'free',
                    expires_at: null
                }
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// ===== 6. 工具函数 =====

function send404(res) {
    const notFoundPath = path.join(__dirname, '404.html');
    fs.stat(notFoundPath, (err, stats) => {
        if (!err && stats.isFile()) {
            res.status(404).sendFile(notFoundPath);
        } else {
            res.status(404).json({
                error: '页面未找到',
                path: req?.path || 'unknown',
                timestamp: new Date().toISOString()
            });
        }
    });
}

function getContentType(ext) {
    const contentTypes = {
        '.html': 'text/html; charset=utf-8',
        '.htm': 'text/html; charset=utf-8',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.eot': 'application/vnd.ms-fontobject',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.xml': 'application/xml'
    };
    
    return contentTypes[ext] || 'application/octet-stream';
}

// ===== 7. 启动服务器 =====

app.listen(PORT, () => {
    const memory = process.memoryUsage();
    const usedMB = Math.round(memory.heapUsed / 1024 / 1024 * 100) / 100;
    
    console.log(`
🚀 === AI24X增强稳定版服务器已启动 ===
📱 端口: ${PORT}, PID: ${process.pid}
💾 内存: ${usedMB}MB (目标: <50MB)
🎯 特性: 极简、稳定、低内存占用 + 支付系统
🌐 访问地址:
   本地: http://localhost:${PORT}
   公网: http://42.192.1.93:${PORT}
📊 监控端点:
   健康检查: http://localhost:${PORT}/health
   系统状态: http://localhost:${PORT}/status
💰 支付API:
   套餐列表: http://localhost:${PORT}/api/payment/plans
   订阅状态: http://localhost:${PORT}/api/payment/subscription?user_id=test

🔧 开始时间: ${new Date().toLocaleString()}
    `);
});

// ===== 8. 优雅关闭和错误处理 =====

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
    console.error('⚠️ 未捕获异常(继续运行):', err.message);
});

process.on('unhandledRejection', (reason) => {
    console.error('⚠️ 未处理的Promise拒绝 (继续运行):', reason);
});

// ===== 9. 内存优化 =====

// 定期执行垃圾回收（如果启用）
if (global.gc) {
    setInterval(() => {
        global.gc();
        console.log('🧹 执行垃圾回收');
    }, 300000); // 5分钟一次
}

// 内存使用监控
setInterval(() => {
    const used = process.memoryUsage();
    const rssMB = Math.round(used.rss / 1024 / 1024 * 100) / 100;
    const heapMB = Math.round(used.heapUsed / 1024 / 1024 * 100) / 100;
    
    if (rssMB > 50) {
        console.warn(`⚠️ 内存使用偏高: RSS ${rssMB}MB, Heap ${heapMB}MB`);
    }
}, 60000); // 每分钟记录一次