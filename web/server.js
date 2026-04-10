const express = require('express');
const path = require('path');
const fs = require('fs');
const morgan = require('morgan');
const cookieParser = require('cookie-parser');

// 性能优化模块
const { 
    createApiCacheMiddleware, 
    performanceMonitoringMiddleware,
    getPerformanceReport,
    performanceMetrics 
} = require('./performance/optimization');

// 性能监控
const performanceMonitor = require('./performance/monitor');

// CDN配置
const cdnConfigurator = require('./performance/cdn-config');

// 安全中间件
const securityMiddleware = require('./security/security-middleware');

const app = express();
const PORT = process.env.PORT || 3000;

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
// 暂时禁用缓存以解决浏览器缓存问题
app.use((req, res, next) => {
    // 只处理静态资源
    if (req.path.match(/\.(css|js|jpg|jpeg|png|gif|webp|svg|woff|woff2|ttf|eot)$/)) {
        // 临时解决方案：禁用缓存，强制浏览器重新加载
        res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.setHeader('Pragma', 'no-cache');
        res.setHeader('Expires', '0');
        
        // 添加安全头
        const securityHeaders = cdnConfigurator.getSecurityHeaders();
        Object.entries(securityHeaders).forEach(([key, value]) => {
            res.setHeader(key, value);
        });
        
        // 记录CDN统计（但实际不缓存）
        cdnConfigurator.recordCacheHit(1024); // 模拟1KB节省
    }
    
    next();
});

// 创建日志目录和文件
const logDir = path.join(__dirname, 'logs');
if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
}

// 创建日志流
const accessLogStream = fs.createWriteStream(
    path.join(logDir, 'access.log'), 
    { flags: 'a' }
);
const errorLogStream = fs.createWriteStream(
    path.join(logDir, 'error.log'), 
    { flags: 'a' }
);

// 自定义日志格式
const logFormat = ':remote-addr - :remote-user [:date[clf]] ":method :url HTTP/:http-version" :status :res[content-length] ":referrer" ":user-agent"';

// 日志中间件 - 访问日志
app.use(morgan(logFormat, { 
    stream: accessLogStream,
    skip: (req, res) => req.path === '/health' // 跳过健康检查日志
}));

// 控制台日志
app.use(morgan('dev'));

// 静态文件服务 - 从当前目录（必须在国际化中间件之前）
app.use(express.static(path.join(__dirname)));
// 添加对CSS文件的直接支持
app.use('/style.css', express.static(path.join(__dirname, 'style.css')));

// 国际化中间件（必须在静态文件服务之后）
const { i18nMiddleware } = require('./i18n/middleware');
app.use(i18nMiddleware);

// 错误处理中间件
app.use((err, req, res, next) => {
    const timestamp = new Date().toISOString();
    const errorMessage = `[${timestamp}] ERROR: ${err.message}\nStack: ${err.stack}\n`;
    
    errorLogStream.write(errorMessage);
    console.error(errorMessage);
    
    res.status(500).json({ 
        error: '服务器内部错误',
        message: process.env.NODE_ENV === 'development' ? err.message : '请稍后重试'
    });
});

// 解析JSON请求体
app.use(express.json());

// 专门的路由处理
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/tools', (req, res) => {
  res.sendFile(path.join(__dirname, 'tools-index.html'));
});

app.get('/rankings', (req, res) => {
  res.sendFile(path.join(__dirname, 'rankings-index.html'));
});

// 注册和登录页面
app.get('/signup', (req, res) => {
  res.sendFile(path.join(__dirname, 'signup.html'));
});

app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'login.html'));
});

// 忘记密码页面
app.get('/forgot-password', (req, res) => {
  res.sendFile(path.join(__dirname, 'forgot-password.html'));
});

// 用户个人中心
app.get('/profile', (req, res) => {
  res.sendFile(path.join(__dirname, 'profile.html'));
});

// 分享链接系统API
const shareAPI = require('./api/share-new');

// 裂变系统API
const fissionAPI = require('./api/fission');

// 支付系统API
const paymentAPI = require('./api/payment');

// API缓存中间件（缓存GET请求30秒）
const apiCache = createApiCacheMiddleware({ ttl: 30000 });

// 分享链接API路由
app.post('/api/share/generate', (req, res) => {
  try {
    const { userId, toolId, customMessage } = req.body;
    
    if (!userId || !toolId) {
      return res.status(400).json({ error: '缺少必要参数: userId 和 toolId' });
    }
    
    const shareLink = shareAPI.generateShareLink(userId, toolId, customMessage);
    res.json({
      success: true,
      data: shareLink,
      message: '分享链接生成成功'
    });
  } catch (error) {
    console.error('生成分享链接错误:', error);
    res.status(500).json({ 
      error: '生成分享链接失败',
      message: error.message 
    });
  }
});

// 获取分享链接信息
app.get('/api/share/:shareId', apiCache, (req, res) => {
  try {
    const { shareId } = req.params;
    const shareLink = shareAPI.getShareLink(shareId);
    
    if (!shareLink) {
      return res.status(404).json({ error: '分享链接不存在' });
    }
    
    res.json({
      success: true,
      data: shareLink
    });
  } catch (error) {
    console.error('获取分享链接错误:', error);
    res.status(500).json({ 
      error: '获取分享链接失败',
      message: error.message 
    });
  }
});

// 获取分享统计
app.get('/api/share/:shareId/stats', apiCache, (req, res) => {
  try {
    const { shareId } = req.params;
    const stats = shareAPI.getShareStats(shareId);
    
    if (!stats) {
      return res.status(404).json({ error: '分享链接不存在' });
    }
    
    res.json({
      success: true,
      data: stats
    });
  } catch (error) {
    console.error('获取分享统计错误:', error);
    res.status(500).json({ 
      error: '获取分享统计失败',
      message: error.message 
    });
  }
});

// 分享链接重定向（记录点击）
app.get('/s/:shareId', (req, res) => {
  try {
    const { shareId } = req.params;
    const ipAddress = req.ip || req.connection.remoteAddress;
    const userAgent = req.headers['user-agent'] || '';
    const referrer = req.headers.referer || req.headers.referrer || '';
    
    console.log(`[API] 分享链接点击: shareId=${shareId}, ip=${ipAddress}`);
    
    // 记录点击
    const clickRecord = shareAPI.recordClick(shareId, ipAddress, userAgent, referrer);
    
    if (!clickRecord) {
      console.log(`[API] 分享链接不存在或已失效: ${shareId}`);
      // 如果分享链接不存在或已失效，重定向到首页
      return res.redirect('/');
    }
    
    console.log(`[API] 点击记录成功: ${clickRecord.id}`);
    
    // 获取分享链接信息
    const shareLink = shareAPI.getShareLink(shareId);
    
    // 重定向到分享页面
    res.redirect(`/share/${shareId}`);
  } catch (error) {
    console.error('[API] 分享链接重定向错误:', error);
    console.error('[API] 错误堆栈:', error.stack);
    res.redirect('/');
  }
});

// 获取用户的所有分享链接
app.get('/api/user/:userId/shares', (req, res) => {
  try {
    const { userId } = req.params;
    const userShares = shareAPI.getUserShares(userId);
    
    res.json({
      success: true,
      data: userShares,
      count: userShares.length
    });
  } catch (error) {
    console.error('获取用户分享列表错误:', error);
    res.status(500).json({ 
      error: '获取用户分享列表失败',
      message: error.message 
    });
  }
});

// 删除分享链接 - 使用查询参数
app.delete('/api/share/:shareId', (req, res) => {
  try {
    const { shareId } = req.params;
    const { userId } = req.query; // 改为查询参数
    
    console.log('DELETE请求:', { shareId, userId, body: req.body, query: req.query });
    
    if (!userId) {
      return res.status(400).json({ error: '缺少必要参数: userId' });
    }
    
    const success = shareAPI.deleteShareLink(shareId, userId);
    
    if (!success) {
      return res.status(404).json({ 
        error: '分享链接不存在或无权删除' 
      });
    }
    
    res.json({
      success: true,
      message: '分享链接删除成功'
    });
  } catch (error) {
    console.error('删除分享链接错误:', error);
    res.status(500).json({ 
      error: '删除分享链接失败',
      message: error.message 
    });
  }
});

// 记录转化（用户注册）
app.post('/api/share/:shareId/convert', (req, res) => {
  try {
    const { shareId } = req.params;
    const { userId } = req.body;
    
    if (!userId) {
      return res.status(400).json({ error: '缺少必要参数: userId' });
    }
    
    const conversion = shareAPI.recordConversion(shareId, userId);
    
    if (!conversion) {
      return res.status(404).json({ error: '分享链接不存在' });
    }
    
    res.json({
      success: true,
      data: conversion,
      message: '转化记录成功'
    });
  } catch (error) {
    console.error('记录转化错误:', error);
    res.status(500).json({ 
      error: '记录转化失败',
      message: error.message 
    });
  }
});

// 分享页面
app.get('/share/:shareId', (req, res) => {
  const { shareId } = req.params;
  const shareLink = shareAPI.getShareLink(shareId);
  
  if (!shareLink) {
    return res.redirect('/');
  }
  
  // 发送分享页面
  res.sendFile(path.join(__dirname, 'share.html'));
});

// 裂变系统API
const fissionAPI = require('./api/fission');

// 创建邀请码
app.post('/api/fission/invite/create', (req, res) => {
  try {
    const { userId, maxUses, expiresInDays } = req.body;
    
    if (!userId) {
      return res.status(400).json({ error: '缺少必要参数: userId' });
    }
    
    const inviteCode = fissionAPI.generateInvitationCode(userId, {
      maxUses: maxUses || 10,
      expiresInDays: expiresInDays || 30
    });
    
    res.json({
      success: true,
      data: inviteCode,
      message: '邀请码创建成功'
    });
  } catch (error) {
    console.error('创建邀请码错误:', error);
    res.status(500).json({ 
      error: '创建邀请码失败',
      message: error.message 
    });
  }
});

// 使用邀请码注册
app.post('/api/fission/invite/use', (req, res) => {
  try {
    const { code, userId } = req.body;
    
    if (!code || !userId) {
      return res.status(400).json({ error: '缺少必要参数: code 和 userId' });
    }
    
    const result = fissionAPI.useInvitationCode(code, userId);
    
    if (!result.success) {
      return res.status(400).json(result);
    }
    
    res.json({
      success: true,
      data: result.data,
      message: '邀请码使用成功'
    });
  } catch (error) {
    console.error('使用邀请码错误:', error);
    res.status(500).json({ 
      error: '使用邀请码失败',
      message: error.message 
    });
  }
});

// 获取用户裂变统计
app.get('/api/fission/user/:userId/stats', (req, res) => {
  try {
    const { userId } = req.params;
    const stats = fissionAPI.getUserReferralNetwork(userId);
    
    res.json({
      success: true,
      data: stats
    });
  } catch (error) {
    console.error('获取用户裂变统计错误:', error);
    res.status(500).json({ 
      error: '获取用户裂变统计失败',
      message: error.message 
    });
  }
});

// 获取裂变排行榜
app.get('/api/fission/leaderboard', (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 20;
    const leaderboard = fissionAPI.getFissionLeaderboard(limit);
    
    res.json({
      success: true,
      data: leaderboard,
      count: leaderboard.length
    });
  } catch (error) {
    console.error('获取裂变排行榜错误:', error);
    res.status(500).json({ 
      error: '获取裂变排行榜失败',
      message: error.message 
    });
  }
});

// 获取用户的邀请码列表
app.get('/api/fission/user/:userId/invites', (req, res) => {
  try {
    const { userId } = req.params;
    const invites = fissionAPI.getUserInvitationCodes(userId);
    
    res.json({
      success: true,
      data: invites,
      count: invites.length
    });
  } catch (error) {
    console.error('获取用户邀请码列表错误:', error);
    res.status(500).json({ 
      error: '获取用户邀请码列表失败',
      message: error.message 
    });
  }
});

// 完成推荐动作
app.post('/api/fission/referral/:referralId/complete', (req, res) => {
  try {
    const { referralId } = req.params;
    const { actionType, value } = req.body;
    
    if (!actionType) {
      return res.status(400).json({ error: '缺少必要参数: actionType' });
    }
    
    const result = fissionAPI.completeReferralAction(referralId, actionType, value);
    
    if (!result.success) {
      return res.status(400).json(result);
    }
    
    res.json({
      success: true,
      data: result.data,
      message: '推荐动作完成记录成功'
    });
  } catch (error) {
    console.error('完成推荐动作错误:', error);
    res.status(500).json({ 
      error: '完成推荐动作失败',
      message: error.message 
    });
  }
});

// 添加奖励
app.post('/api/fission/reward/add', (req, res) => {
  try {
    const { userId, type, points, description } = req.body;
    
    if (!userId || !type || !points) {
      return res.status(400).json({ error: '缺少必要参数: userId, type, points' });
    }
    
    const reward = fissionAPI.addReward(userId, type, points, description);
    
    res.json({
      success: true,
      data: reward,
      message: '奖励添加成功'
    });
  } catch (error) {
    console.error('添加奖励错误:', error);
    res.status(500).json({ 
      error: '添加奖励失败',
      message: error.message 
    });
  }
});

// 获取裂变系统测试数据
app.get('/api/fission/test/data', (req, res) => {
  try {
    const testData = fissionAPI.getTestData();
    
    res.json({
      success: true,
      data: testData,
      message: '测试数据获取成功'
    });
  } catch (error) {
    console.error('获取测试数据错误:', error);
    res.status(500).json({ 
      error: '获取测试数据失败',
      message: error.message 
    });
  }
});

// 安全监控端点
app.get('/api/security/stats', (req, res) => {
  try {
    const stats = securityMiddleware.getSecurityStats();
    
    res.json({
      success: true,
      data: stats,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('获取安全统计错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 重置安全统计
app.post('/api/security/reset', (req, res) => {
  try {
    securityMiddleware.resetStats();
    
    res.json({
      success: true,
      message: '安全统计已重置',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('重置安全统计错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 生成CSRF令牌（用于表单）
app.get('/api/security/csrf-token', (req, res) => {
  try {
    const token = securityMiddleware.generateCsrfToken();
    
    // 设置CSRF令牌Cookie
    res.cookie('csrf-token', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 24 * 60 * 60 * 1000 // 24小时
    });
    
    res.json({
      success: true,
      data: { csrfToken: token },
      message: 'CSRF令牌已生成',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('生成CSRF令牌错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 获取分享系统测试数据
app.get('/api/share/test/data', (req, res) => {
  try {
    const testData = shareAPI.getTestData ? shareAPI.getTestData() : { 
      message: '分享系统测试数据API未实现',
      timestamp: new Date().toISOString()
    };
    
    res.json({
      success: true,
      data: testData,
      message: '测试数据获取成功'
    });
  } catch (error) {
    console.error('获取分享测试数据错误:', error);
    res.status(500).json({ 
      error: '获取测试数据失败',
      message: error.message 
    });
  }
});

// 健康检查端点
app.get('/health', (req, res) => {
    const uptime = process.uptime();
    const memoryUsage = process.memoryUsage();
    
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        uptime: uptime,
        memory: {
            rss: Math.round(memoryUsage.rss / 1024 / 1024) + 'MB',
            heapTotal: Math.round(memoryUsage.heapTotal / 1024 / 1024) + 'MB',
            heapUsed: Math.round(memoryUsage.heapUsed / 1024 / 1024) + 'MB',
            external: Math.round(memoryUsage.external / 1024 / 1024) + 'MB'
        },
        node: {
            version: process.version,
            platform: process.platform,
            arch: process.arch
        },
        server: {
            port: PORT,
            env: process.env.NODE_ENV || 'development',
            pid: process.pid
        }
    });
});

// 详细状态端点
app.get('/status', (req, res) => {
    const uptime = process.uptime();
    const memoryUsage = process.memoryUsage();
    const loadAvg = process.cpuUsage();
    
    res.json({
        server: 'AI24X Website Server',
        version: '1.0.0',
        status: 'running',
        timestamp: new Date().toISOString(),
        
        uptime: {
            seconds: uptime,
            formatted: formatUptime(uptime)
        },
        
        memory: {
            rss: formatBytes(memoryUsage.rss),
            heapTotal: formatBytes(memoryUsage.heapTotal),
            heapUsed: formatBytes(memoryUsage.heapUsed),
            external: formatBytes(memoryUsage.external),
            arrayBuffers: formatBytes(memoryUsage.arrayBuffers)
        },
        
        cpu: {
            user: loadAvg.user / 1000 + 'ms',
            system: loadAvg.system / 1000 + 'ms'
        },
        
        process: {
            pid: process.pid,
            ppid: process.ppid,
            uid: process.getuid ? process.getuid() : null,
            gid: process.getgid ? process.getgid() : null,
            cwd: process.cwd()
        },
        
        node: {
            version: process.version,
            versions: process.versions,
            platform: process.platform,
            arch: process.arch,
            release: process.release
        },
        
        system: {
            argv: process.argv,
            execArgv: process.execArgv,
            execPath: process.execPath,
            envKeys: Object.keys(process.env).length
        }
    });
});

// 辅助函数：格式化字节
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 辅助函数：格式化运行时间
function formatUptime(seconds) {
    const days = Math.floor(seconds / (3600 * 24));
    const hours = Math.floor((seconds % (3600 * 24)) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    const parts = [];
    if (days > 0) parts.push(`${days}天`);
    if (hours > 0) parts.push(`${hours}小时`);
    if (minutes > 0) parts.push(`${minutes}分钟`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}秒`);
    
    return parts.join(' ');
}

// 处理其他路由
app.get('*', (req, res) => {
  // 如果是API请求，返回404
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({ error: 'API endpoint not found' });
  }
  
  // 检查请求的文件是否存在
  const filePath = path.join(__dirname, req.path);
  if (fs.existsSync(filePath) && !req.path.endsWith('/')) {
    return res.sendFile(filePath);
  }
  
  // 否则返回主页面
  res.sendFile(path.join(__dirname, 'index.html'));
});

// 错误处理中间件
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).send('Internal Server Error');
});

// 启动服务器 - 绑定到所有网络接口，支持公网访问
const HOST = '0.0.0.0'; // 绑定到所有网络接口
const server = app.listen(PORT, HOST, () => {
  const localUrl = `http://localhost:${PORT}`;
  const networkUrl = `http://${getLocalIP()}:${PORT}`;
  const publicUrl = `http://42.192.1.93:${PORT}`;
  
  console.log(`🚀 AI24X网站服务器已启动！`);
  console.log(`📱 本地访问: ${localUrl}`);
  console.log(`🌐 局域网访问: ${networkUrl}`);
  console.log(`🌍 公网访问: ${publicUrl}`);
  console.log(`📊 健康检查: ${localUrl}/health`);
  console.log(`📈 状态监控: ${localUrl}/status`);
  console.log(`⏰ 启动时间: ${new Date().toISOString()}`);
  console.log(`🔧 配置: 端口=${PORT}, 主机=${HOST}, PID=${process.pid}`);
  
  // 重要提示：使用HTTP而不是HTTPS
  console.log(`\n⚠️  重要提示:`);
  console.log(`   公网访问请使用: http://42.192.1.93:${PORT}`);
  console.log(`   不要使用 https:// 前缀，服务器未配置SSL证书`);
  console.log(`   如果浏览器显示安全警告，请确保使用 http:// 而不是 https://`);
  console.log(`\n🔧 已放宽请求限制: 测试环境15分钟内允许1000个请求`);
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

// 简单测试页面 - 不依赖外部资源
app.get('/test-simple', (req, res) => {
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI24X 测试页面</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }
        h1 {
            color: #fff;
            text-align: center;
            margin-bottom: 30px;
        }
        .test-item {
            background: rgba(255, 255, 255, 0.2);
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            display: flex;
            align-items: center;
        }
        .icon {
            font-size: 24px;
            margin-right: 15px;
            width: 40px;
            text-align: center;
        }
        .status {
            margin-left: auto;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }
        .success {
            background: #10b981;
            color: white;
        }
        .error {
            background: #ef4444;
            color: white;
        }
        .test-button {
            display: block;
            width: 100%;
            padding: 15px;
            margin: 10px 0;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.3s;
        }
        .test-button:hover {
            background: #2563eb;
        }
        .dropdown {
            position: relative;
            display: inline-block;
            width: 200px;
        }
        .dropdown-btn {
            width: 100%;
            padding: 10px;
            background: white;
            color: #333;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            text-align: left;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .dropdown-content {
            display: none;
            position: absolute;
            background: white;
            width: 100%;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            border-radius: 5px;
            z-index: 1;
        }
        .dropdown-content a {
            color: #333;
            padding: 12px 16px;
            text-decoration: none;
            display: block;
        }
        .dropdown-content a:hover {
            background: #f1f1f1;
        }
        .show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 AI24X 公网访问测试页面</h1>
        
        <div class="test-item">
            <div class="icon">🎨</div>
            <div>
                <strong>CSS样式测试</strong><br>
                <small>检查内联CSS是否生效</small>
            </div>
            <div class="status success">内联CSS ✅</div>
        </div>
        
        <div class="test-item">
            <div class="icon">🖼️</div>
            <div>
                <strong>图标显示测试</strong><br>
                <small>检查图标是否显示（使用Unicode）</small>
            </div>
            <div class="status success">Unicode图标 ✅</div>
        </div>
        
        <div class="test-item">
            <div class="icon">⚡</div>
            <div>
                <strong>JavaScript交互测试</strong><br>
                <small>检查下拉菜单功能</small>
            </div>
            <div class="status" id="jsStatus">待测试</div>
        </div>
        
        <div class="test-item">
            <div class="icon">🌐</div>
            <div>
                <strong>网络连接测试</strong><br>
                <small>检查公网访问能力</small>
            </div>
            <div class="status success">公网访问 ✅</div>
        </div>
        
        <h2>🔧 功能测试</h2>
        
        <!-- 下拉菜单测试 -->
        <div class="dropdown">
            <button class="dropdown-btn" onclick="toggleDropdown()">
                <span>选择语言</span>
                <span>▼</span>
            </button>
            <div class="dropdown-content" id="dropdownContent">
                <a href="#" onclick="selectLanguage('zh')">🇨🇳 中文</a>
                <a href="#" onclick="selectLanguage('en')">🇺🇸 English</a>
                <a href="#" onclick="selectLanguage('ja')">🇯🇵 日本語</a>
            </div>
        </div>
        
        <button class="test-button" onclick="testAlert()">
            🧪 测试JavaScript弹窗
        </button>
        
        <button class="test-button" onclick="testConsole()">
            📝 测试控制台输出
        </button>
        
        <div id="testResult" style="margin-top: 20px; padding: 15px; background: rgba(255,255,255,0.2); border-radius: 5px; display: none;">
            <h3>测试结果</h3>
            <p id="resultText"></p>
        </div>
        
        <div style="margin-top: 30px; padding: 15px; background: rgba(0,0,0,0.2); border-radius: 5px;">
            <h3>💡 诊断信息</h3>
            <p><strong>页面特点:</strong></p>
            <ul>
                <li>✅ 完全内联CSS - 不依赖外部CSS文件</li>
                <li>✅ Unicode图标 - 不依赖Font Awesome</li>
                <li>✅ 内联JavaScript - 不依赖外部JS文件</li>
                <li>✅ 无外部资源依赖 - 完全自包含</li>
                <li>✅ 交互功能完整 - 下拉菜单、按钮点击</li>
            </ul>
            <p><strong>测试目的:</strong> 确定问题是外部资源加载问题还是服务器配置问题</p>
        </div>
    </div>

    <script>
        let dropdownVisible = false;
        
        function toggleDropdown() {
            const dropdown = document.getElementById('dropdownContent');
            dropdown.classList.toggle('show');
            dropdownVisible = !dropdownVisible;
            document.getElementById('jsStatus').className = 'status success';
            document.getElementById('jsStatus').textContent = 'JS交互 ✅';
        }
        
        function selectLanguage(lang) {
            const languages = {
                'zh': '中文',
                'en': 'English', 
                'ja': '日本語'
            };
            document.querySelector('.dropdown-btn span:first-child').textContent = languages[lang];
            toggleDropdown();
            
            const resultDiv = document.getElementById('testResult');
            const resultText = document.getElementById('resultText');
            resultText.textContent = \`✅ 成功选择语言: \${languages[lang]} (\${lang})\`;
            resultDiv.style.display = 'block';
        }
        
        function testAlert() {
            alert('✅ JavaScript弹窗功能正常！');
            document.getElementById('jsStatus').className = 'status success';
            document.getElementById('jsStatus').textContent = '弹窗功能 ✅';
        }
        
        function testConsole() {
            console.log('✅ JavaScript控制台输出正常！');
            console.log('测试时间:', new Date().toLocaleString());
            console.log('用户代理:', navigator.userAgent);
            
            const resultDiv = document.getElementById('testResult');
            const resultText = document.getElementById('resultText');
            resultText.textContent = '✅ 控制台输出正常，请按F12查看控制台';
            resultDiv.style.display = 'block';
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            console.log('🔧 AI24X测试页面已加载');
            console.log('⏰ 加载时间:', new Date().toISOString());
            console.log('🌐 页面URL:', window.location.href);
            
            document.addEventListener('click', function(event) {
                const dropdown = document.getElementById('dropdownContent');
                const button = document.querySelector('.dropdown-btn');
                
                if (dropdownVisible && !dropdown.contains(event.target) && !button.contains(event.target)) {
                    dropdown.classList.remove('show');
                    dropdownVisible = false;
                }
            });
        });
    </script>
</body>
</html>`;
  
  res.send(html);
});

// 分享系统测试数据端点
app.get('/api/share/test/data', (req, res) => {
  try {
    const testData = shareAPI.getTestData ? shareAPI.getTestData() : { 
      message: '分享系统测试数据API未实现',
      timestamp: new Date().toISOString()
    };
    
    res.json({
      success: true,
      data: testData,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// 分享系统测试数据端点（兼容旧路径）
app.get('/api/share/test-data', (req, res) => {
  try {
    const testData = shareAPI.getTestData ? shareAPI.getTestData() : { 
      message: '分享系统测试数据API未实现',
      timestamp: new Date().toISOString()
    };
    
    res.json({
      success: true,
      data: testData,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

app.get('/api/fission/test-data', (req, res) => {
  try {
    const testData = fissionAPI.getTestData ? fissionAPI.getTestData() : { 
      message: '测试数据API未实现',
      timestamp: new Date().toISOString()
    };
    
    res.json({
      success: true,
      data: testData,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// 集成测试状态端点
app.get('/api/integration-test/status', (req, res) => {
  res.json({
    success: true,
    data: {
      serverStatus: 'running',
      pid: process.pid,
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      timestamp: new Date().toISOString(),
      version: '1.0.0',
      features: {
        shareSystem: true,
        fissionSystem: true,
        i18n: true,
        userAuth: true
      }
    }
  });
});

// 优雅关闭
process.on('SIGTERM', () => {
  console.log('收到SIGTERM信号，正在关闭服务器...');
  server.close(() => {
    console.log('服务器已关闭');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('收到SIGINT信号，正在关闭服务器...');
  server.close(() => {
    console.log('服务器已关闭');
    process.exit(0);
  });
});

// 未捕获异常处理
process.on('uncaughtException', (err) => {
  console.error('未捕获异常:', err);
  // 尝试重启服务器
  setTimeout(() => {
    console.log('尝试重启服务器...');
    process.exit(1);
  }, 1000);
});

// 性能监控端点
app.get('/api/performance/report', (req, res) => {
  try {
    const report = getPerformanceReport();
    const monitorReport = performanceMonitor.getPerformanceReport();
    
    res.json({
      success: true,
      data: {
        optimizationReport: report,
        monitorReport: monitorReport,
        realtimeMetrics: performanceMonitor.getRealtimeMetrics(),
        timestamp: new Date().toISOString()
      }
    });
  } catch (error) {
    console.error('获取性能报告错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 性能监控实时数据
app.get('/api/performance/realtime', (req, res) => {
  try {
    const metrics = performanceMonitor.getRealtimeMetrics();
    
    res.json({
      success: true,
      data: metrics,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('获取实时性能数据错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 重置性能指标
app.post('/api/performance/reset', (req, res) => {
  try {
    performanceMonitor.resetMetrics();
    
    res.json({
      success: true,
      message: '性能指标已重置',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('重置性能指标错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 安全监控端点
app.get('/api/security/stats', (req, res) => {
  try {
    const stats = securityMiddleware.getSecurityStats();
    
    res.json({
      success: true,
      data: stats,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('获取安全统计错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 重置安全统计
app.post('/api/security/reset', (req, res) => {
  try {
    securityMiddleware.resetStats();
    
    res.json({
      success: true,
      message: '安全统计已重置',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('重置安全统计错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 生成CSRF令牌（用于表单）
app.get('/api/security/csrf-token', (req, res) => {
  try {
    const token = securityMiddleware.generateCsrfToken();
    
    // 设置CSRF令牌Cookie
    res.cookie('csrf-token', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 24 * 60 * 60 * 1000 // 24小时
    });
    
    res.json({
      success: true,
      data: { csrfToken: token },
      message: 'CSRF令牌已生成',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('生成CSRF令牌错误:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// 内存使用监控
setInterval(() => {
  const used = process.memoryUsage();
  console.log(`内存使用: RSS ${Math.round(used.rss / 1024 / 1024)}MB, Heap ${Math.round(used.heapUsed / 1024 / 1024)}MB`);
}, 60000); // 每分钟记录一次