// 简化的安全中间件
const helmet = require('helmet');
const hpp = require('hpp');
const xss = require('xss-clean');
const rateLimit = require('express-rate-limit');

// 创建限流器
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15分钟
    max: 100, // 每个IP限制100个请求
    standardHeaders: true,
    legacyHeaders: false,
    message: '请求过于频繁，请稍后再试'
});

// API限流器（更严格）
const apiLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 50,
    standardHeaders: true,
    legacyHeaders: false,
    message: 'API请求过于频繁，请稍后再试'
});

// 获取所有安全中间件
function getMiddlewares() {
    return [
        // 基本安全头
        helmet({
            contentSecurityPolicy: {
                directives: {
                    defaultSrc: ["'self'"],
                    styleSrc: ["'self'", "'unsafe-inline'"],
                    scriptSrc: ["'self'", "'unsafe-inline'"],
                    imgSrc: ["'self'", "data:", "https:"],
                    fontSrc: ["'self'", "data:"],
                    connectSrc: ["'self'"]
                }
            },
            crossOriginEmbedderPolicy: false,
            crossOriginResourcePolicy: { policy: "cross-origin" }
        }),
        
        // 防止参数污染
        hpp(),
        
        // 防止XSS攻击
        xss(),
        
        // 全局限流
        limiter
    ];
}

// API路由的限流中间件
function getApiLimiter() {
    return apiLimiter;
}

module.exports = {
    getMiddlewares,
    getApiLimiter
};