/**
 * AI24X网站服务 - 高性能优化版
 * 版本: 6.0.0
 * 创建时间: 2026-03-19
 * 功能: 静态文件服务 + 缓存 + 压缩 + 性能优化
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const PORT = 3001; // 使用不同端口避免冲突
const projectDir = __dirname;

// 性能监控
const performance = {
    requests: 0,
    cacheHits: 0,
    startTime: Date.now(),
    getUptime: () => Math.floor((Date.now() - performance.startTime) / 1000)
};

// 文件缓存（内存缓存）
const fileCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5分钟缓存

// 压缩缓存
const compressCache = new Map();

// MIME类型映射
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.json': 'application/json',
    '.txt': 'text/plain',
    '.md': 'text/markdown'
};

// 简单的HTML修复函数（优化版）
function fixHTML(content) {
    // 1. 移除所有外部CDN链接
    content = content.replace(/<link[^>]*href=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    content = content.replace(/<script[^>]*src=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    
    // 2. 移除不存在的CSS文件引用
    content = content.replace(/<link[^>]*href=["']spacing-unified\.css["'][^>]*>/gi, '');
    
    // 3. 添加本地CSS链接（如果不存在）
    if (!content.includes('font-awesome-local.css')) {
        const localCSS = `
    <!-- 100% 本地图标 + 字体 -->
    <link rel="stylesheet" href="/font-awesome-local.css">
    <link rel="stylesheet" href="/fonts-local.css">`;
        
        // 插入到</head>之前
        const headEnd = content.indexOf('</head>');
        if (headEnd !== -1) {
            content = content.slice(0, headEnd) + localCSS + content.slice(headEnd);
        }
    }
    
    // 4. 添加CSP meta标签（如果不存在）
    if (!content.includes('Content-Security-Policy')) {
        const cspMeta = `
    <!-- 纯本地安全策略 -->
    <meta http-equiv="Content-Security-Policy" content="
        default-src 'self';
        script-src 'self' 'unsafe-inline';
        style-src 'self' 'unsafe-inline';
        font-src 'self';
        img-src 'self' data:;
    ">`;
        
        // 插入到<head>之后
        const headStart = content.indexOf('<head>');
        if (headStart !== -1) {
            const insertPos = headStart + '<head>'.length;
            content = content.slice(0, insertPos) + cspMeta + content.slice(insertPos);
        }
    }
    
    // 5. 修复图标类名
    content = content.replace(/class="fas fa-/g, 'class="fa fa-');
    content = content.replace(/class='fas fa-/g, "class='fa fa-");
    content = content.replace(/class="fab fa-/g, 'class="fa fa-');
    content = content.replace(/class='fab fa-/g, "class='fa fa-");
    
    return content;
}

// 读取文件（带缓存）
function readFileWithCache(filePath, callback) {
    const cached = fileCache.get(filePath);
    const now = Date.now();
    
    if (cached && (now - cached.timestamp) < CACHE_TTL) {
        performance.cacheHits++;
        return callback(null, cached.data);
    }
    
    fs.readFile(filePath, 'utf8', (err, data) => {
        if (err) {
            return callback(err);
        }
        
        // 缓存文件
        fileCache.set(filePath, {
            data: data,
            timestamp: now
        });
        
        callback(null, data);
    });
}

// 压缩响应
function compressResponse(data, acceptEncoding, callback) {
    const cacheKey = `${acceptEncoding}:${data.length}`;
    const cached = compressCache.get(cacheKey);
    
    if (cached) {
        return callback(null, cached.encoding, cached.data);
    }
    
    if (acceptEncoding.includes('gzip')) {
        zlib.gzip(data, (err, compressed) => {
            if (!err) {
                compressCache.set(cacheKey, {
                    encoding: 'gzip',
                    data: compressed
                });
                callback(null, 'gzip', compressed);
            } else {
                callback(null, null, data);
            }
        });
    } else if (acceptEncoding.includes('deflate')) {
        zlib.deflate(data, (err, compressed) => {
            if (!err) {
                compressCache.set(cacheKey, {
                    encoding: 'deflate',
                    data: compressed
                });
                callback(null, 'deflate', compressed);
            } else {
                callback(null, null, data);
            }
        });
    } else {
        callback(null, null, data);
    }
}

// 路由映射（预编译正则表达式）
const ROUTES = [
    { pattern: /^\/$|\/index\.html$/, file: 'index.html' },
    { pattern: /^\/tools$|\/tools\.html$|\/tools\/$/, file: 'tools-static.html' },
    { pattern: /^\/tutorials$|\/tutorials\.html$|\/tutorials\/$/, file: 'tutorials/index.html' },
    { pattern: /^\/custom$|\/custom\.html$/, file: 'custom.html' },
    { pattern: /^\/login$|\/login\.html$/, file: 'login.html' },
    { pattern: /^\/signup$|\/signup\.html$/, file: 'signup.html' },
    { pattern: /^\/font-awesome-local\.css$/, file: 'font-awesome-local.css' },
    { pattern: /^\/fonts-local\.css$/, file: 'fonts-local.css' }
];

// 创建HTTP服务器
const server = http.createServer((req, res) => {
    performance.requests++;
    
    // 记录请求（性能监控）
    const startTime = process.hrtime.bigint();
    
    // 移除查询参数
    const urlPath = req.url.split('?')[0];
    
    // 查找路由
    let filePath = '';
    let matched = false;
    
    for (const route of ROUTES) {
        if (route.pattern.test(urlPath)) {
            filePath = path.join(projectDir, route.file);
            matched = true;
            break;
        }
    }
    
    // 如果没有匹配到预定义路由，尝试作为静态文件处理
    if (!matched) {
        filePath = path.join(projectDir, urlPath.substring(1));
    }
    
    // 安全检查：防止目录遍历攻击
    const normalizedPath = path.normalize(filePath);
    if (!normalizedPath.startsWith(projectDir)) {
        res.statusCode = 403;
        res.end('403 - 禁止访问');
        return;
    }
    
    // 检查文件扩展名
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    
    // 读取文件
    readFileWithCache(filePath, (err, data) => {
        if (err) {
            // 文件不存在，返回404
            res.statusCode = 404;
            res.end('404 - 文件未找到');
            
            // 记录响应时间
            const endTime = process.hrtime.bigint();
            const duration = Number(endTime - startTime) / 1e6; // 毫秒
            console.log(`[${new Date().toISOString()}] ${req.method} ${req.url} - 404 (${duration.toFixed(2)}ms)`);
            return;
        }
        
        // 如果是HTML文件，进行修复
        if (ext === '.html') {
            data = fixHTML(data);
        }
        
        // 设置响应头
        res.setHeader('Content-Type', contentType);
        res.setHeader('Cache-Control', 'public, max-age=300'); // 5分钟缓存
        res.setHeader('X-Powered-By', 'AI24X-Optimized-Server');
        
        // 压缩响应
        const acceptEncoding = req.headers['accept-encoding'] || '';
        compressResponse(data, acceptEncoding, (err, encoding, compressedData) => {
            if (encoding) {
                res.setHeader('Content-Encoding', encoding);
            }
            
            // 发送响应
            res.end(compressedData);
            
            // 记录响应时间
            const endTime = process.hrtime.bigint();
            const duration = Number(endTime - startTime) / 1e6; // 毫秒
            const cacheStatus = fileCache.has(filePath) ? 'HIT' : 'MISS';
            
            console.log(`[${new Date().toISOString()}] ${req.method} ${req.url} - 200 (${duration.toFixed(2)}ms, Cache:${cacheStatus})`);
        });
    });
});

// 性能监控端点
server.on('request', (req, res) => {
    if (req.url === '/_status') {
        const uptime = performance.getUptime();
        const rps = (performance.requests / uptime).toFixed(2);
        const cacheHitRate = performance.requests > 0 
            ? ((performance.cacheHits / performance.requests) * 100).toFixed(2)
            : '0.00';
        
        const status = {
            status: 'running',
            uptime: `${uptime}s`,
            requests: performance.requests,
            cacheHits: performance.cacheHits,
            cacheHitRate: `${cacheHitRate}%`,
            requestsPerSecond: rps,
            memoryUsage: process.memoryUsage(),
            fileCacheSize: fileCache.size,
            compressCacheSize: compressCache.size,
            timestamp: new Date().toISOString()
        };
        
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify(status, null, 2));
        return;
    }
});

// 启动服务器（监听所有IP地址）
server.listen(PORT, '0.0.0.0', () => {
    console.log('🚀 AI24X高性能优化网站服务启动成功！');
    console.log(`📊 本地访问: http://localhost:${PORT}`);
    console.log(`🌐 网络访问: http://${getLocalIP()}:${PORT}`);
    console.log(`⏰ 启动时间: ${new Date().toLocaleString()}`);
    console.log(`📁 服务目录: ${projectDir}`);
    console.log('🎯 性能特性:');
    console.log('  🔄 内存缓存 (5分钟TTL)');
    console.log('  📦 GZIP/DEFLATE压缩');
    console.log('  ⚡ 预编译路由匹配');
    console.log('  📊 实时性能监控');
    console.log('  🔒 安全路径检查');
    console.log('  📈 缓存命中率统计');
    console.log('📡 监控端点: http://localhost:3001/_status');
    console.log('🔄 服务运行中...');
});

// 获取本地IP地址
function getLocalIP() {
    const interfaces = require('os').networkInterfaces();
    for (const name of Object.keys(interfaces)) {
        for (const iface of interfaces[name]) {
            if (iface.family === 'IPv4' && !iface.internal) {
                return iface.address;
            }
        }
    }
    return 'localhost';
}

// 定期清理过期缓存
setInterval(() => {
    const now = Date.now();
    let cleaned = 0;
    
    for (const [key, value] of fileCache.entries()) {
        if (now - value.timestamp > CACHE_TTL) {
            fileCache.delete(key);
            cleaned++;
        }
    }
    
    if (cleaned > 0) {
        console.log(`🧹 清理了 ${cleaned} 个过期缓存项`);
    }
}, 60000); // 每分钟清理一次

// 优雅关闭
process.on('SIGINT', () => {
    console.log('\n🛑 正在关闭优化服务器...');
    
    // 输出性能统计
    const uptime = performance.getUptime();
    const rps = (performance.requests / uptime).toFixed(2);
    const cacheHitRate = performance.requests > 0 
        ? ((performance.cacheHits / performance.requests) * 100).toFixed(2)
        : '0.00';
    
    console.log(`📊 性能统计:`);
    console.log(`  运行时间: ${uptime}s`);
    console.log(`  总请求数: ${performance.requests}`);
    console.log(`  缓存命中: ${performance.cacheHits} (${cacheHitRate}%)`);
    console.log(`  平均RPS: ${rps}`);
    console.log(`  文件缓存大小: ${fileCache.size}`);
    console.log(`  压缩缓存大小: ${compressCache.size}`);
    
    server.close(() => {
        console.log('✅ 优化服务器已关闭');
        process.exit(0);
    });
});

// 内存使用监控
setInterval(() => {
    const mem = process.memoryUsage();
    const heapUsedMB = Math.round(mem.heapUsed / 1024 / 1024);
    const heapTotalMB = Math.round(mem.heapTotal / 1024 / 1024);
    
    if (heapUsedMB > 100) { // 超过100MB时警告
        console.log(`⚠️  内存使用较高: ${heapUsedMB}MB / ${heapTotalMB}MB`);
    }
}, 30000); // 每30秒检查一次