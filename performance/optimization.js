/**
 * AI24X性能优化模块 - 第二阶段
 * 包含高级缓存策略、CDN配置、数据库优化等
 */

const fs = require('fs');
const path = require('path');

// 性能监控数据
const performanceMetrics = {
    startTime: new Date(),
    totalRequests: 0,
    cacheHits: 0,
    cacheMisses: 0,
    dbQueries: 0,
    apiCalls: 0,
    errors: 0
};

// 高级缓存系统
class AdvancedCache {
    constructor(options = {}) {
        this.cache = new Map();
        this.maxSize = options.maxSize || 1000;
        this.ttl = options.ttl || 300000; // 5分钟默认TTL
        this.stats = {
            hits: 0,
            misses: 0,
            evictions: 0,
            size: 0
        };
    }

    // 获取缓存
    get(key) {
        const item = this.cache.get(key);
        
        if (!item) {
            this.stats.misses++;
            return null;
        }
        
        // 检查是否过期
        if (Date.now() > item.expiresAt) {
            this.cache.delete(key);
            this.stats.evictions++;
            this.stats.size--;
            this.stats.misses++;
            return null;
        }
        
        this.stats.hits++;
        return item.value;
    }

    // 设置缓存
    set(key, value, ttl = this.ttl) {
        // 如果缓存已满，删除最旧的项
        if (this.stats.size >= this.maxSize) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
            this.stats.evictions++;
            this.stats.size--;
        }
        
        const item = {
            value,
            expiresAt: Date.now() + ttl,
            createdAt: Date.now(),
            accessCount: 0
        };
        
        this.cache.set(key, item);
        this.stats.size++;
        
        return true;
    }

    // 删除缓存
    delete(key) {
        const deleted = this.cache.delete(key);
        if (deleted) {
            this.stats.size--;
        }
        return deleted;
    }

    // 清空缓存
    clear() {
        this.cache.clear();
        this.stats.size = 0;
        this.stats.evictions += this.stats.size;
    }

    // 获取统计信息
    getStats() {
        const hitRate = this.stats.hits + this.stats.misses > 0 
            ? (this.stats.hits / (this.stats.hits + this.stats.misses) * 100).toFixed(2)
            : 0;
        
        return {
            ...this.stats,
            hitRate: `${hitRate}%`,
            currentSize: this.stats.size,
            maxSize: this.maxSize,
            ttl: this.ttl
        };
    }
}

// 数据库查询优化
class DatabaseOptimizer {
    constructor() {
        this.queryCache = new AdvancedCache({ maxSize: 500, ttl: 60000 }); // 1分钟查询缓存
        this.indexes = new Map();
        this.queryStats = new Map();
    }

    // 优化查询
    optimizeQuery(query, params) {
        const queryKey = this.generateQueryKey(query, params);
        
        // 检查缓存
        const cachedResult = this.queryCache.get(queryKey);
        if (cachedResult) {
            performanceMetrics.cacheHits++;
            return cachedResult;
        }
        
        performanceMetrics.cacheMisses++;
        performanceMetrics.dbQueries++;
        
        // 记录查询统计
        this.recordQueryStat(query);
        
        // 这里应该执行实际的数据库查询
        // 返回null表示需要实际执行查询
        return null;
    }

    // 生成查询键
    generateQueryKey(query, params) {
        return `query:${Buffer.from(query).toString('base64')}:${JSON.stringify(params)}`;
    }

    // 记录查询统计
    recordQueryStat(query) {
        const normalizedQuery = this.normalizeQuery(query);
        const stat = this.queryStats.get(normalizedQuery) || { count: 0, lastExecuted: null };
        stat.count++;
        stat.lastExecuted = new Date();
        this.queryStats.set(normalizedQuery, stat);
    }

    // 规范化查询（移除空格和换行）
    normalizeQuery(query) {
        return query.replace(/\s+/g, ' ').trim();
    }

    // 获取查询优化建议
    getOptimizationSuggestions() {
        const suggestions = [];
        const statsArray = Array.from(this.queryStats.entries());
        
        // 按执行次数排序
        statsArray.sort((a, b) => b[1].count - a[1].count);
        
        // 分析最频繁的查询
        for (const [query, stat] of statsArray.slice(0, 10)) {
            if (stat.count > 100) {
                suggestions.push({
                    query,
                    executionCount: stat.count,
                    suggestion: '考虑添加数据库索引或查询缓存',
                    priority: 'high'
                });
            } else if (stat.count > 50) {
                suggestions.push({
                    query,
                    executionCount: stat.count,
                    suggestion: '考虑优化查询逻辑',
                    priority: 'medium'
                });
            }
        }
        
        return suggestions;
    }

    // 缓存查询结果
    cacheQueryResult(query, params, result, ttl = 60000) {
        const queryKey = this.generateQueryKey(query, params);
        this.queryCache.set(queryKey, result, ttl);
    }

    // 获取性能统计
    getPerformanceStats() {
        return {
            queryCacheStats: this.queryCache.getStats(),
            queryStats: Array.from(this.queryStats.entries()).map(([query, stat]) => ({
                query: query.length > 100 ? query.substring(0, 100) + '...' : query,
                ...stat
            })),
            optimizationSuggestions: this.getOptimizationSuggestions()
        };
    }
}

// API响应缓存中间件
function createApiCacheMiddleware(options = {}) {
    const cache = new AdvancedCache({
        maxSize: options.maxSize || 100,
        ttl: options.ttl || 30000 // 30秒默认TTL
    });

    return function apiCacheMiddleware(req, res, next) {
        // 只缓存GET请求
        if (req.method !== 'GET') {
            return next();
        }

        // 检查是否应该跳过缓存
        if (req.query.nocache === 'true') {
            return next();
        }

        const cacheKey = `${req.method}:${req.originalUrl}`;
        const cachedResponse = cache.get(cacheKey);

        if (cachedResponse) {
            // 设置缓存命中头
            res.setHeader('X-Cache', 'HIT');
            res.setHeader('X-Cache-Key', cacheKey);
            
            // 返回缓存的响应
            res.status(cachedResponse.status).json(cachedResponse.data);
            return;
        }

        // 缓存未命中，继续处理
        res.setHeader('X-Cache', 'MISS');
        
        // 保存原始send方法
        const originalSend = res.send;
        const originalJson = res.json;
        
        // 重写send方法以捕获响应
        res.send = function(body) {
            // 只缓存成功的响应
            if (res.statusCode >= 200 && res.statusCode < 300) {
                const responseToCache = {
                    status: res.statusCode,
                    data: body,
                    headers: res.getHeaders()
                };
                
                cache.set(cacheKey, responseToCache);
            }
            
            originalSend.call(this, body);
        };
        
        // 重写json方法
        res.json = function(body) {
            // 只缓存成功的响应
            if (res.statusCode >= 200 && res.statusCode < 300) {
                const responseToCache = {
                    status: res.statusCode,
                    data: body,
                    headers: res.getHeaders()
                };
                
                cache.set(cacheKey, responseToCache);
            }
            
            originalJson.call(this, body);
        };
        
        next();
    };
}

// 静态资源优化
class StaticResourceOptimizer {
    constructor() {
        this.compressedFiles = new Map();
        this.cdnConfig = {
            enabled: false,
            baseUrl: '',
            domains: []
        };
    }

    // 压缩CSS
    compressCss(css) {
        // 简单的CSS压缩：移除空格、注释、换行
        return css
            .replace(/\/\*[\s\S]*?\*\//g, '') // 移除注释
            .replace(/\s+/g, ' ') // 合并多个空格
            .replace(/\s*([{}:;,])\s*/g, '$1') // 移除选择器和属性周围的空格
            .replace(/;}/g, '}') // 移除最后一个分号
            .trim();
    }

    // 压缩JavaScript
    compressJs(js) {
        // 简单的JS压缩：移除注释和多余空格
        return js
            .replace(/\/\/.*$/gm, '') // 移除单行注释
            .replace(/\/\*[\s\S]*?\*\//g, '') // 移除多行注释
            .replace(/\s+/g, ' ') // 合并多个空格
            .replace(/\s*([=+\-*/%&|^~!?:;,{}()[\]])\s*/g, '$1') // 移除操作符周围的空格
            .trim();
    }

    // 配置CDN
    configureCDN(config) {
        this.cdnConfig = {
            ...this.cdnConfig,
            ...config,
            enabled: true
        };
        
        console.log('[Performance] CDN配置已更新:', this.cdnConfig);
    }

    // 获取CDN URL
    getCdnUrl(relativePath) {
        if (!this.cdnConfig.enabled || !this.cdnConfig.baseUrl) {
            return relativePath;
        }
        
        // 简单的CDN域名轮询
        if (this.cdnConfig.domains && this.cdnConfig.domains.length > 0) {
            const domainIndex = Math.floor(Math.random() * this.cdnConfig.domains.length);
            const domain = this.cdnConfig.domains[domainIndex];
            return `https://${domain}${relativePath}`;
        }
        
        return `${this.cdnConfig.baseUrl}${relativePath}`;
    }

    // 获取优化统计
    getOptimizationStats() {
        return {
            cdnConfig: this.cdnConfig,
            compressedFiles: this.compressedFiles.size,
            compressionRatios: Array.from(this.compressedFiles.entries()).map(([file, data]) => ({
                file,
                originalSize: data.originalSize,
                compressedSize: data.compressedSize,
                ratio: ((data.originalSize - data.compressedSize) / data.originalSize * 100).toFixed(2) + '%'
            }))
        };
    }
}

// 性能监控中间件
function performanceMonitoringMiddleware(req, res, next) {
    const startTime = Date.now();
    
    // 记录请求开始
    performanceMetrics.totalRequests++;
    
    // 监听响应完成
    res.on('finish', () => {
        const duration = Date.now() - startTime;
        const requestInfo = {
            method: req.method,
            path: req.path,
            statusCode: res.statusCode,
            duration: `${duration}ms`,
            timestamp: new Date().toISOString(),
            userAgent: req.headers['user-agent'] || 'unknown',
            ip: req.ip || req.connection.remoteAddress
        };
        
        // 记录错误
        if (res.statusCode >= 400) {
            performanceMetrics.errors++;
        }
        
        // 记录API调用
        if (req.path.startsWith('/api/')) {
            performanceMetrics.apiCalls++;
        }
        
        // 慢请求警告
        if (duration > 1000) {
            console.warn(`[Performance] 慢请求检测: ${req.method} ${req.path} - ${duration}ms`);
        }
    });
    
    next();
}

// 获取性能报告
function getPerformanceReport() {
    const uptime = Date.now() - performanceMetrics.startTime;
    const uptimeHours = (uptime / (1000 * 60 * 60)).toFixed(2);
    
    const cacheHitRate = performanceMetrics.cacheHits + performanceMetrics.cacheMisses > 0
        ? (performanceMetrics.cacheHits / (performanceMetrics.cacheHits + performanceMetrics.cacheMisses) * 100).toFixed(2)
        : 0;
    
    const errorRate = performanceMetrics.totalRequests > 0
        ? (performanceMetrics.errors / performanceMetrics.totalRequests * 100).toFixed(4)
        : 0;
    
    return {
        system: {
            uptime: `${uptimeHours}小时`,
            totalRequests: performanceMetrics.totalRequests,
            apiCalls: performanceMetrics.apiCalls,
            dbQueries: performanceMetrics.dbQueries,
            errors: performanceMetrics.errors,
            errorRate: `${errorRate}%`
        },
        cache: {
            hits: performanceMetrics.cacheHits,
            misses: performanceMetrics.cacheMisses,
            hitRate: `${cacheHitRate}%`
        },
        recommendations: [
            cacheHitRate < 70 ? '建议增加缓存TTL或缓存更多数据' : '缓存命中率良好',
            errorRate > 1 ? '错误率较高，建议检查系统稳定性' : '错误率正常',
            performanceMetrics.dbQueries > performanceMetrics.apiCalls * 10 
                ? '数据库查询过多，建议优化查询逻辑' 
                : '数据库查询量正常'
        ]
    };
}

// 导出模块
module.exports = {
    AdvancedCache,
    DatabaseOptimizer,
    createApiCacheMiddleware,
    StaticResourceOptimizer,
    performanceMonitoringMiddleware,
    getPerformanceReport,
    performanceMetrics
};