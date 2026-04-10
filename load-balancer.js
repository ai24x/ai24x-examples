/**
 * AI24X简单负载均衡器
 * 版本: 1.0.0
 * 创建时间: 2026-03-19
 * 功能: 轮询负载均衡 + 健康检查
 */

const http = require('http');
const httpProxy = require('http-proxy');

// 后端服务器列表
const servers = [
    { host: 'localhost', port: 3000, weight: 1, healthy: true },
    { host: 'localhost', port: 3001, weight: 2, healthy: true } // 优化服务器权重更高
];

// 创建代理
const proxy = httpProxy.createProxyServer({});

// 当前服务器索引（用于轮询）
let currentServerIndex = 0;

// 健康检查间隔（秒）
const HEALTH_CHECK_INTERVAL = 30;

// 选择服务器（加权轮询）
function selectServer() {
    // 只选择健康的服务器
    const healthyServers = servers.filter(server => server.healthy);
    if (healthyServers.length === 0) {
        return null;
    }
    
    // 计算总权重
    const totalWeight = healthyServers.reduce((sum, server) => sum + server.weight, 0);
    
    // 生成随机数
    let random = Math.random() * totalWeight;
    
    // 根据权重选择服务器
    for (const server of healthyServers) {
        random -= server.weight;
        if (random <= 0) {
            return server;
        }
    }
    
    // 如果算法失败，返回第一个健康的服务器
    return healthyServers[0];
}

// 健康检查函数
function healthCheck(server) {
    const options = {
        hostname: server.host,
        port: server.port,
        path: '/',
        method: 'HEAD',
        timeout: 5000
    };
    
    const req = http.request(options, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 500) {
            if (!server.healthy) {
                console.log(`✅ 服务器 ${server.host}:${server.port} 恢复健康`);
                server.healthy = true;
            }
        } else {
            if (server.healthy) {
                console.log(`⚠️  服务器 ${server.host}:${server.port} 不健康 (状态码: ${res.statusCode})`);
                server.healthy = false;
            }
        }
    });
    
    req.on('error', (err) => {
        if (server.healthy) {
            console.log(`❌ 服务器 ${server.host}:${server.port} 不可达: ${err.message}`);
            server.healthy = false;
        }
    });
    
    req.on('timeout', () => {
        if (server.healthy) {
            console.log(`⏰ 服务器 ${server.host}:${server.port} 响应超时`);
            server.healthy = false;
        }
        req.destroy();
    });
    
    req.end();
}

// 创建负载均衡服务器
const lbServer = http.createServer((req, res) => {
    // 记录请求
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
    
    // 选择服务器
    const target = selectServer();
    
    if (!target) {
        res.statusCode = 503;
        res.setHeader('Content-Type', 'text/plain');
        res.end('503 - 所有后端服务器都不可用');
        console.log('❌ 所有后端服务器都不可用');
        return;
    }
    
    // 设置代理目标
    const targetUrl = {
        host: target.host,
        port: target.port
    };
    
    // 添加X-Forwarded-For头
    req.headers['x-forwarded-for'] = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
    req.headers['x-forwarded-host'] = req.headers.host;
    req.headers['x-forwarded-proto'] = 'http';
    
    // 代理请求
    proxy.web(req, res, { target: targetUrl }, (err) => {
        console.error(`代理错误: ${err.message}`);
        res.statusCode = 502;
        res.setHeader('Content-Type', 'text/plain');
        res.end('502 - 代理错误');
    });
});

// 代理错误处理
proxy.on('error', (err, req, res) => {
    console.error('代理服务器错误:', err);
    if (!res.headersSent) {
        res.statusCode = 500;
        res.setHeader('Content-Type', 'text/plain');
        res.end('500 - 内部服务器错误');
    }
});

// 启动负载均衡器
const PORT = 8080;
lbServer.listen(PORT, '0.0.0.0', () => {
    console.log('🚀 AI24X负载均衡器启动成功！');
    console.log(`📊 监听端口: ${PORT}`);
    console.log(`⏰ 启动时间: ${new Date().toLocaleString()}`);
    console.log('🎯 后端服务器:');
    servers.forEach((server, index) => {
        console.log(`  ${index + 1}. ${server.host}:${server.port} (权重: ${server.weight})`);
    });
    console.log('🔍 健康检查: 每30秒一次');
    console.log('🔄 负载均衡算法: 加权轮询');
    console.log('📈 监控端点: http://localhost:8080/_lb_status');
    console.log('🔄 服务运行中...');
});

// 状态监控端点
lbServer.on('request', (req, res) => {
    if (req.url === '/_lb_status') {
        const status = {
            status: 'running',
            timestamp: new Date().toISOString(),
            servers: servers.map(server => ({
                host: server.host,
                port: server.port,
                weight: server.weight,
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
});

// 定期健康检查
setInterval(() => {
    console.log('🔍 执行健康检查...');
    servers.forEach(server => {
        healthCheck(server);
    });
}, HEALTH_CHECK_INTERVAL * 1000);

// 启动时立即执行一次健康检查
console.log('🔍 执行初始健康检查...');
servers.forEach(server => {
    healthCheck(server);
});

// 优雅关闭
process.on('SIGINT', () => {
    console.log('\n🛑 正在关闭负载均衡器...');
    
    // 输出服务器状态
    console.log('📊 服务器状态:');
    servers.forEach((server, index) => {
        const status = server.healthy ? '✅ 健康' : '❌ 不健康';
        console.log(`  ${index + 1}. ${server.host}:${server.port} - ${status}`);
    });
    
    lbServer.close(() => {
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