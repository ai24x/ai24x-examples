// 简化的性能优化模块

// 性能指标
const performanceMetrics = {
    requests: { count: 0 },
    responseTimes: [],
    errors: { count: 0 },
    increment() {
        this.requests.count++;
    },
    addResponseTime(time) {
        this.responseTimes.push(time);
        // 只保留最近1000个响应时间
        if (this.responseTimes.length > 1000) {
            this.responseTimes.shift();
        }
    },
    incrementErrors() {
        this.errors.count++;
    }
};

// 性能监控中间件
function performanceMonitoringMiddleware(req, res, next) {
    const startTime = Date.now();
    
    // 记录请求开始
    performanceMetrics.increment();
    
    // 监听响应完成
    res.on('finish', () => {
        const responseTime = Date.now() - startTime;
        performanceMetrics.addResponseTime(responseTime);
        
        // 记录慢请求
        if (responseTime > 1000) {
            console.warn(`慢请求: ${req.method} ${req.url} - ${responseTime}ms`);
        }
    });
    
    next();
}

// API缓存中间件
function createApiCacheMiddleware() {
    return (req, res, next) => {
        // 为API响应添加缓存头
        if (req.path.startsWith('/api/')) {
            res.setHeader('Cache-Control', 'public, max-age=60');
        }
        next();
    };
}

// 获取性能报告
function getPerformanceReport() {
    const responseTimes = performanceMetrics.responseTimes;
    const avgResponseTime = responseTimes.length > 0 
        ? responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length 
        : 0;
    
    return {
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        requests: performanceMetrics.requests.count,
        errors: performanceMetrics.errors.count,
        responseTimes: {
            average: avgResponseTime.toFixed(2),
            min: responseTimes.length > 0 ? Math.min(...responseTimes) : 0,
            max: responseTimes.length > 0 ? Math.max(...responseTimes) : 0,
            p95: calculatePercentile(responseTimes, 95),
            p99: calculatePercentile(responseTimes, 99)
        },
        memory: process.memoryUsage()
    };
}

// 计算百分位数
function calculatePercentile(data, percentile) {
    if (data.length === 0) return 0;
    
    const sorted = [...data].sort((a, b) => a - b);
    const index = Math.ceil(percentile / 100 * sorted.length) - 1;
    return sorted[Math.max(0, index)];
}

module.exports = {
    performanceMetrics,
    performanceMonitoringMiddleware,
    createApiCacheMiddleware,
    getPerformanceReport
};