/**
 * AI24X简单负载均衡器（无依赖版）
 * 版本: 1.0.0
 * 创建时间: 2026-03-19
 * 功能: 简单轮询负载均衡
 */

const http = require('http');

// 后端服务器列表
const servers = [
    { host: 'localhost', port: 3000, healthy: true, name: '标准服务器' },
    { host: 'localhost', port: 3001, healthy: true, name: '优化服务器' }
];

// 当前服务器索引（用于轮询）
let currentServerIndex = 0;

// 请求计数器
let requestCount = 0;

// 健康检查函数
function healthCheck(server) {
    return new Promise((resolve) => {
        const options = {
            hostname: server.host,
            port: server.port,
            path: '/',
            method: 'HEAD',
            timeout: 3000
        };
        
        const req = http.request(options, (res) => {
            server.healthy = (res.statusCode >= 200 && res.statusCode < 500);
            resolve(server.healthy);
        });
        
        req.on('error', () => {
            server.healthy = false;
            resolve(false);
        });
        
        req.on('timeout', () => {
            server.healthy = false;
            req.destroy();
            resolve(false);
        });
        
        req.end();
    });
}

// 选择服务器（简单轮询）
function selectServer() {
    // 只选择健康的服务器
    const healthyServers = servers.filter(server => server.healthy);
    if (healthyServers.length === 0) {
        return null;
    }
    
    // 简单轮询
    const selected = healthyServers[currentServerIndex % healthyServers.length];
    currentServerIndex++;
    return selected;
}

// 转发请求
function forwardRequest(req, res, targetServer) {
    const options = {
        hostname: targetServer.host,
        port: targetServer.port,
        path: req.url,
        method: req.method,
        headers: req.headers
    };
    
    // 添加转发头
    options.headers['x-forwarded-for'] = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
    options.headers['x-forwarded-host'] = req.headers.host;
    options.headers['x-forwarded-proto'] = 'http';
    options.headers['x-forwarded-by'] = 'AI24X-LoadBalancer';
    
    const proxyReq = http.request(options, (proxyRes) => {
        // 复制响应头
        Object.keys(proxyRes.headers).forEach(key => {
            res.setHeader(key, proxyRes.headers[key]);
        });
        
        // 添加负载均衡器头
        res.setHeader('x-lb-server', targetServer.name);
        res.setHeader('x-lb-port', targetServer.port);
        
        // 设置状态码
        res.statusCode = proxyRes.statusCode;
        
        // 转发响应体
        proxyRes.pipe(res);
    });
    
    proxyReq.on('error', (err) => {
        console.error(`转发错误到 ${targetServer.name}:`, err.message);
        if (!res.headersSent) {
            res.statusCode = 502;
            res.setHeader('Content-Type', 'text/plain');
            res.end(`502 - 后端服务器 ${targetServer.name} 错误`);
        }
    });
    
    // 转发请求体
    req.pipe(proxyReq);
}

// 创建负载均衡服务器
const PORT = 8080;
const server = http.createServer((req, res) => {
    requestCount++;
    
    // 记录请求
    const requestId = requestCount;
    console.log(`[${new Date().toISOString()}] #${requestId} ${req.method} ${req.url}`);
    
    // 状态检查端点
    if (req.url === '/_lb_status') {
        const status = {
            status: 'running',
            timestamp: new Date().toISOString(),
            requestCount: requestCount,
            servers: servers.map(server => ({
                name: server.name,
                host: server.host,
                port: server.port,
                healthy: server.healthy,
                url: `http://${server.host}:${server.port}`
            })),
            stats: {
                totalServers: servers.length,
                healthyServers: servers.filter(s => s.healthy).length,
                unhealthyServers: servers.filter(s => !s.healthy).length
            }
        };
        
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify(status, null, 2));
        return;
    }
    
    // 选择服务器
    const targetServer = selectServer();
    
    if (!targetServer) {
        res.statusCode = 503;
        res.setHeader('Content-Type', 'text/plain');
        res.end('503 - 所有后端服务器都不可用');
        console.log(`#${requestId} ❌ 所有后端服务器都不可用`);
        return;
    }
    
    console.log(`#${requestId} ➡️  转发到 ${targetServer.name} (${targetServer.host}:${targetServer.port})`);
    
    // 转发请求
    forwardRequest(req, res, targetServer);
});

// 启动负载均衡器
server.listen(PORT, '0.0.0.0', () => {
    console.log('🚀 AI24X简单负载均衡器启动成功！');
    console.log(`📊 监听端口: ${PORT}`);
    console.log(`⏰ 启动时间: ${new Date().toLocaleString()}`);
    console.log('🎯 后端服务器:');
    servers.forEach((server, index) => {
        console.log(`  ${index + 1}. ${server.name} - ${server.host}:${server.port}`);
    });
    console.log('🔍 健康检查: 每30秒一次');
    console.log('🔄 负载均衡算法: 简单轮询');
    console.log('📈 监控端点: http://localhost:8080/_lb_status');
    console.log('🔄 服务运行中...');
});

// 定期健康检查
setInterval(async () => {
    console.log('🔍 执行健康检查...');
    
    for (const server of servers) {
        const wasHealthy = server.healthy;
        const isHealthy = await healthCheck(server);
        
        if (wasHealthy && !isHealthy) {
            console.log(`⚠️  ${server.name} 变为不健康`);
        } else if (!wasHealthy && isHealthy) {
            console.log(`✅  ${server.name} 恢复健康`);
        }
    }
    
    // 输出状态摘要
    const healthyCount = servers.filter(s => s.healthy).length;
    console.log(`📊 健康状态: ${healthyCount}/${servers.length} 个服务器健康`);
}, 30000); // 每30秒检查一次

// 启动时立即执行一次健康检查
console.log('🔍 执行初始健康检查...');
Promise.all(servers.map(server => healthCheck(server))).then(() => {
    const healthyCount = servers.filter(s => s.healthy).length;
    console.log(`📊 初始健康检查完成: ${healthyCount}/${servers.length} 个服务器健康`);
});

// 优雅关闭
process.on('SIGINT', () => {
    console.log('\n🛑 正在关闭负载均衡器...');
    
    // 输出统计
    console.log('📊 运行统计:');
    console.log(`  总请求数: ${requestCount}`);
    console.log('  服务器状态:');
    servers.forEach((server, index) => {
        const status = server.healthy ? '✅ 健康' : '❌ 不健康';
        console.log(`    ${index + 1}. ${server.name} - ${status}`);
    });
    
    server.close(() => {
        console.log('✅ 负载均衡器已关闭');
        process.exit(0);
    });
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