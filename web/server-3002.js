const express = require('express');
const path = require('path');
const fs = require('fs');
const morgan = require('morgan');
const cookieParser = require('cookie-parser');

// 性能优化模块（简化版）
const { 
    createApiCacheMiddleware, 
    performanceMonitoringMiddleware,
    getPerformanceReport,
    performanceMetrics 
} = require('./performance/optimization-simple');

// 性能监控（简化）
const performanceMonitor = {
    start: () => console.log('性能监控已启动'),
    stop: () => console.log('性能监控已停止')
};

// CDN配置（简化）
const cdnConfigurator = {
    enableCDN: () => console.log('CDN配置已启用（模拟）'),
    cdnMiddleware: () => (req, res, next) => next()
};

// 安全中间件
const securityMiddleware = require('./security/security-middleware');

const app = express();
const PORT = 3002; // 修改为3002端口

// 解析JSON请求体
app.use(express.json());
app.use(cookieParser());

// 性能监控中间件
app.use(performanceMonitoringMiddleware);

// 启用CDN（模拟生产环境）
cdnConfigurator.enableCDN('custom', {
    domains: ['static.ai24x.com', 'cdn.ai24x.com'],
    baseUrl: 'https://static.ai24x.com',
    compression: {
        enabled: true,
        gzip: true,
        brotli: true
    }
});

// 安全中间件 - 全面的安全防护
securityMiddleware.getMiddlewares().forEach(middleware => {
    app.use(middleware);
});

// CDN中间件 - 为静态资源添加CDN URL和缓存头
app.use(cdnConfigurator.cdnMiddleware());

// 日志中间件
app.use(morgan('combined'));

// API缓存中间件
app.use(createApiCacheMiddleware());

// 首页路由
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// 工具页面路由 - 直接重定向到tools-index（更好的用户体验）
app.get('/tools', (req, res) => {
    // 构建查询字符串
    const queryParams = new URLSearchParams();
    
    // 添加所有查询参数
    for (const [key, value] of Object.entries(req.query)) {
        if (value) {
            queryParams.append(key, value);
        }
    }
    
    // 构建重定向URL
    const queryString = queryParams.toString();
    const redirectUrl = queryString ? `/tools-index?${queryString}` : '/tools-index';
    
    res.redirect(redirectUrl);
});

// 工具索引页面路由
app.get('/tools-index', (req, res) => {
    res.sendFile(path.join(__dirname, 'tools-index.html'));
});

// 工具索引页面路由（带.html扩展名，重定向到规范化URL）
app.get('/tools-index.html', (req, res) => {
    // 构建查询字符串
    const queryParams = new URLSearchParams();
    
    // 添加所有查询参数
    for (const [key, value] of Object.entries(req.query)) {
        if (value) {
            queryParams.append(key, value);
        }
    }
    
    // 构建重定向URL
    const queryString = queryParams.toString();
    const redirectUrl = queryString ? `/tools-index?${queryString}` : '/tools-index';
    
    res.redirect(redirectUrl);
});

// 登录页面路由
app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'login.html'));
});

// 注册页面路由
app.get('/signup', (req, res) => {
    res.sendFile(path.join(__dirname, 'signup.html'));
});

// 分类页面路由
app.get('/categories', (req, res) => {
    res.sendFile(path.join(__dirname, 'categories.html'));
});

// 排行榜页面路由
app.get('/rankings', (req, res) => {
    res.sendFile(path.join(__dirname, 'rankings-index.html'));
});

// 教程页面路由
app.get('/tutorials', (req, res) => {
    res.sendFile(path.join(__dirname, 'tutorials', 'index.html'));
});

// 教程详情页面路由
app.get('/tutorials/openclaw-complete-guide', (req, res) => {
    res.sendFile(path.join(__dirname, 'tutorials', 'openclaw-complete-guide.html'));
});

app.get('/tutorials/openclaw-skill-development', (req, res) => {
    res.sendFile(path.join(__dirname, 'tutorials', 'openclaw-skill-development.html'));
});

app.get('/tutorials/openclaw-lan-deployment', (req, res) => {
    res.sendFile(path.join(__dirname, 'tutorials', 'openclaw-lan-deployment.html'));
});

app.get('/tutorials/ai-painting-midjourney', (req, res) => {
    res.sendFile(path.join(__dirname, 'tutorials', 'ai-painting-midjourney.html'));
});

app.get('/tutorials/chatgpt-advanced', (req, res) => {
    res.sendFile(path.join(__dirname, 'tutorials', 'chatgpt-advanced.html'));
});

app.get('/tutorials/ai-code-assistant', (req, res) => {
    res.sendFile(path.join(__dirname, 'tutorials', 'ai-code-assistant.html'));
});

// 定制页面路由
app.get('/custom', (req, res) => {
    res.sendFile(path.join(__dirname, 'custom.html'));
});

// 用户中心页面路由
app.get('/user-center', (req, res) => {
    res.sendFile(path.join(__dirname, 'user-center.html'));
});

// 支付页面路由
app.get('/payment', (req, res) => {
    res.sendFile(path.join(__dirname, 'payment.html'));
});

// 分享页面路由
app.get('/share', (req, res) => {
    res.sendFile(path.join(__dirname, 'share.html'));
});

// 健康检查端点
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        port: PORT
    });
});

// 性能报告端点
app.get('/performance-report', (req, res) => {
    const report = getPerformanceReport();
    res.json(report);
});

// 静态文件服务 - 放在路由之后，避免干扰
app.use(express.static(path.join(__dirname), {
    maxAge: '1y',
    setHeaders: (res, filePath) => {
        // 为静态文件设置缓存头
        if (filePath.match(/\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$/)) {
            res.setHeader('Cache-Control', 'public, max-age=31536000');
        }
    }
}));

// 404处理
app.use((req, res) => {
    res.status(404).sendFile(path.join(__dirname, '404.html'));
});

// 错误处理中间件
app.use((err, req, res, next) => {
    console.error('服务器错误:', err);
    performanceMetrics.errors.increment();
    
    res.status(500).json({
        error: '服务器内部错误',
        message: process.env.NODE_ENV === 'development' ? err.message : '请稍后重试',
        timestamp: new Date().toISOString()
    });
});

// 启动服务器
const server = app.listen(PORT, () => {
    console.log(`AI24X网站服务器运行在端口 ${PORT}`);
    console.log(`访问地址: http://localhost:${PORT}`);
    console.log(`健康检查: http://localhost:${PORT}/health`);
    console.log(`性能报告: http://localhost:${PORT}/performance-report`);
    
    // 启动性能监控
    performanceMonitor.start();
});

// 优雅关闭
process.on('SIGTERM', () => {
    console.log('收到SIGTERM信号，正在关闭服务器...');
    performanceMonitor.stop();
    server.close(() => {
        console.log('服务器已关闭');
        process.exit(0);
    });
});

process.on('SIGINT', () => {
    console.log('收到SIGINT信号，正在关闭服务器...');
    performanceMonitor.stop();
    server.close(() => {
        console.log('服务器已关闭');
        process.exit(0);
    });
});

// 未捕获异常处理
process.on('uncaughtException', (err) => {
    console.error('未捕获异常:', err);
    performanceMetrics.errors.increment();
    
    // 记录错误但不退出，保持服务可用
    fs.appendFileSync(
        path.join(__dirname, 'logs', 'uncaught-exceptions.log'),
        `${new Date().toISOString()} - ${err.stack}\n`
    );
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('未处理的Promise拒绝:', reason);
    performanceMetrics.errors.increment();
    
    fs.appendFileSync(
        path.join(__dirname, 'logs', 'unhandled-rejections.log'),
        `${new Date().toISOString()} - ${reason}\n`
    );
});

module.exports = app;