/**
 * HTTPS配置和公网访问修复
 * 解决 ERR_SSL_PROTOCOL_ERROR 问题
 */

const fs = require('fs');
const https = require('https');
const http = require('http');

class HTTPSManager {
    constructor() {
        this.config = {
            httpPort: 3000,
            httpsPort: 3443, // 使用非标准HTTPS端口，避免权限问题
            enableHTTPS: false, // 默认禁用，需要证书
            redirectHTTPtoHTTPS: false,
            sslCertPath: null,
            sslKeyPath: null
        };
    }
    
    // 检查SSL证书
    checkSSLCertificates() {
        const certPaths = [
            'ssl/cert.pem',
            'ssl/key.pem',
            'cert.pem',
            'key.pem',
            '../ssl/cert.pem',
            '../ssl/key.pem'
        ];
        
        for (const certPath of certPaths) {
            if (fs.existsSync(certPath)) {
                const keyPath = certPath.replace('cert', 'key');
                if (fs.existsSync(keyPath)) {
                    this.config.sslCertPath = certPath;
                    this.config.sslKeyPath = keyPath;
                    this.config.enableHTTPS = true;
                    console.log(`✅ 找到SSL证书: ${certPath}, ${keyPath}`);
                    return true;
                }
            }
        }
        
        console.log('⚠️  未找到SSL证书，HTTPS将不可用');
        console.log('💡 解决方案:');
        console.log('  1. 使用HTTP访问: http://42.192.1.93:3000');
        console.log('  2. 生成自签名证书: openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes');
        console.log('  3. 将cert.pem和key.pem放在项目根目录');
        return false;
    }
    
    // 创建HTTPS服务器
    createHTTPServer(app) {
        const httpServer = http.createServer(app);
        
        httpServer.listen(this.config.httpPort, '0.0.0.0', () => {
            console.log(`🌐 HTTP服务器运行在: http://localhost:${this.config.httpPort}`);
            console.log(`🌐 局域网访问: http://${this.getLocalIP()}:${this.config.httpPort}`);
            console.log(`🌐 公网访问: http://42.192.1.93:${this.config.httpPort}`);
        });
        
        return httpServer;
    }
    
    // 创建HTTPS服务器（如果有证书）
    createHTTPSServer(app) {
        if (!this.config.enableHTTPS) {
            console.log('⚠️  HTTPS未启用，跳过HTTPS服务器创建');
            return null;
        }
        
        try {
            const options = {
                cert: fs.readFileSync(this.config.sslCertPath),
                key: fs.readFileSync(this.config.sslKeyPath)
            };
            
            const httpsServer = https.createServer(options, app);
            
            httpsServer.listen(this.config.httpsPort, '0.0.0.0', () => {
                console.log(`🔒 HTTPS服务器运行在: https://localhost:${this.config.httpsPort}`);
                console.log(`🔒 公网HTTPS: https://42.192.1.93:${this.config.httpsPort}`);
                console.log('⚠️  注意: 自签名证书会显示安全警告，点击"高级"->"继续访问"即可');
            });
            
            return httpsServer;
        } catch (error) {
            console.error(`❌ 创建HTTPS服务器失败: ${error.message}`);
            return null;
        }
    }
    
    // 添加HTTP到HTTPS重定向
    addHTTPRedirect(app) {
        if (this.config.redirectHTTPtoHTTPS && this.config.enableHTTPS) {
            app.use((req, res, next) => {
                if (!req.secure && req.get('X-Forwarded-Proto') !== 'https') {
                    return res.redirect(`https://${req.headers.host.replace(/:\d+/, '')}:${this.config.httpsPort}${req.url}`);
                }
                next();
            });
        }
    }
    
    // 获取本地IP地址
    getLocalIP() {
        const interfaces = require('os').networkInterfaces();
        for (const name of Object.keys(interfaces)) {
            for (const iface of interfaces[name]) {
                if (iface.family === 'IPv4' && !iface.internal) {
                    return iface.address;
                }
            }
        }
        return '127.0.0.1';
    }
    
    // 打印访问指南
    printAccessGuide() {
        console.log('\n📋 访问指南:');
        console.log('========================================');
        
        if (this.config.enableHTTPS) {
            console.log('🔒 HTTPS访问 (推荐):');
            console.log(`  https://42.192.1.93:${this.config.httpsPort}`);
            console.log(`  https://localhost:${this.config.httpsPort}`);
            console.log('\n⚠️  注意: 自签名证书会显示安全警告');
            console.log('     点击"高级"->"继续访问"即可');
        }
        
        console.log('\n🌐 HTTP访问:');
        console.log(`  http://42.192.1.93:${this.config.httpPort}`);
        console.log(`  http://localhost:${this.config.httpPort}`);
        
        console.log('\n📱 移动端访问:');
        console.log(`  确保设备与服务器在同一网络`);
        console.log(`  使用: http://${this.getLocalIP()}:${this.config.httpPort}`);
        
        console.log('\n🔧 故障排除:');
        console.log('  1. 防火墙: 确保端口3000和3443已开放');
        console.log('  2. 路由器: 可能需要端口转发');
        console.log('  3. 浏览器: 清除缓存，尝试无痕模式');
        console.log('  4. 网络: 确保公网IP正确: 42.192.1.93');
        console.log('========================================\n');
    }
}

module.exports = HTTPSManager;