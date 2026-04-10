/**
 * AI24X网站自动内存监控与重启系统
 * 功能：监控内存使用，超过阈值时自动重启服务
 * 重启策略：内存 > 80% 持续1分钟，则自动重启
 */

const { spawn, exec } = require('child_process');
const fs = require('fs');
const path = require('path');

// ===== 配置参数 =====
const CONFIG = {
    // 监控配置
    CHECK_INTERVAL: 60000,           // 检查间隔：60秒（减少频率）
    HIGH_MEMORY_THRESHOLD: 90,       // 高内存阈值：90%（提高阈值）
    HIGH_MEMORY_DURATION: 180000,    // 高内存持续时间：3分钟（延长触发时间）
    HIGH_MEMORY_COUNT_THRESHOLD: 3,  // 连续高内存次数阈值：3次
    
    // 服务器配置
    SERVER_PORT: 3000,
    SERVER_SCRIPT: 'server-stable.js', // 使用稳定版服务器脚本
    SERVER_PATH: __dirname,
    
    // 重启配置
    RESTART_DELAY: 10000,            // 重启延迟：10秒（给更多恢复时间）
    MAX_RESTARTS_PER_HOUR: 2,        // 每小时最大重启次数：2次（更保守）
    MAX_RESTARTS_PER_DAY: 5,         // 每天最大重启次数：5次（更保守）
    
    // 日志配置
    LOG_FILE: 'auto-restart.log',
    MAX_LOG_SIZE: 10 * 1024 * 1024,  // 最大日志大小：10MB
};

// ===== 状态变量 =====
let serverProcess = null;
let highMemoryStartTime = null;
let highMemoryCount = 0;  // 连续高内存次数
let restartCounts = {
    hour: { count: 0, resetTime: Date.now() + 3600000 },
    day: { count: 0, resetTime: Date.now() + 86400000 }
};
let isRestarting = false;

// ===== 日志系统 =====
function log(message, level = 'INFO') {
    const timestamp = new Date().toISOString().replace('T', ' ').substr(0, 19);
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    
    // 写入日志文件
    try {
        const logPath = path.join(CONFIG.SERVER_PATH, CONFIG.LOG_FILE);
        fs.appendFileSync(logPath, logMessage + '\n', 'utf8');
        
        // 检查日志文件大小，如果太大则清理
        const stats = fs.statSync(logPath);
        if (stats.size > CONFIG.MAX_LOG_SIZE) {
            const logs = fs.readFileSync(logPath, 'utf8').split('\n');
            const trimmedLogs = logs.slice(-1000); // 保留最后1000行
            fs.writeFileSync(logPath, trimmedLogs.join('\n'), 'utf8');
            log('日志文件已清理，保留最后1000行', 'INFO');
        }
    } catch (error) {
        console.error('写入日志失败:', error.message);
    }
}

// ===== 服务器管理 =====

// 启动服务器
function startServer() {
    if (isRestarting) {
        log('正在重启中，跳过重复启动', 'WARN');
        return;
    }
    
    log(`启动服务器: ${CONFIG.SERVER_SCRIPT}`);
    
    serverProcess = spawn('node', [CONFIG.SERVER_SCRIPT], {
        cwd: CONFIG.SERVER_PATH,
        stdio: ['pipe', 'pipe', 'pipe'],
        shell: true
    });
    
    // 处理服务器输出
    serverProcess.stdout.on('data', (data) => {
        const output = data.toString().trim();
        if (output) {
            log(`服务器输出: ${output}`, 'SERVER');
        }
    });
    
    serverProcess.stderr.on('data', (data) => {
        const error = data.toString().trim();
        if (error) {
            log(`服务器错误: ${error}`, 'ERROR');
        }
    });
    
    serverProcess.on('close', (code) => {
        log(`服务器进程退出，代码: ${code}`, code === 0 ? 'INFO' : 'ERROR');
        serverProcess = null;
        
        // 如果不是主动重启，且退出代码非0，则尝试重启
        if (!isRestarting && code !== 0) {
            log('服务器异常退出，将在5秒后重启', 'WARN');
            setTimeout(() => {
                isRestarting = false;
                startServer();
            }, CONFIG.RESTART_DELAY);
        }
    });
    
    serverProcess.on('error', (error) => {
        log(`服务器启动错误: ${error.message}`, 'ERROR');
        serverProcess = null;
    });
    
    log('服务器启动完成', 'SUCCESS');
}

// 停止服务器
function stopServer() {
    return new Promise((resolve) => {
        if (!serverProcess) {
            log('没有运行的服务器进程', 'INFO');
            resolve();
            return;
        }
        
        log('正在停止服务器...', 'INFO');
        
        // 先尝试优雅关闭
        serverProcess.kill('SIGTERM');
        
        // 设置超时，5秒后强制关闭
        const forceKillTimeout = setTimeout(() => {
            if (serverProcess) {
                log('服务器未响应，强制关闭', 'WARN');
                serverProcess.kill('SIGKILL');
            }
        }, 5000);
        
        serverProcess.on('close', () => {
            clearTimeout(forceKillTimeout);
            serverProcess = null;
            log('服务器已停止', 'SUCCESS');
            resolve();
        });
    });
}

// 重启服务器
async function restartServer(reason) {
    if (isRestarting) {
        log('已经在重启过程中，跳过', 'WARN');
        return;
    }
    
    // 检查重启频率限制
    if (!canRestart()) {
        log('达到重启频率限制，跳过重启', 'WARN');
        return;
    }
    
    isRestarting = true;
    log(`开始重启服务器，原因: ${reason}`, 'INFO');
    
    // 记录重启次数
    restartCounts.hour.count++;
    restartCounts.day.count++;
    
    await stopServer();
    
    log(`等待 ${CONFIG.RESTART_DELAY / 1000} 秒后启动...`, 'INFO');
    setTimeout(() => {
        isRestarting = false;
        startServer();
        log('服务器重启完成', 'SUCCESS');
    }, CONFIG.RESTART_DELAY);
}

// 检查是否可以重启（频率限制）
function canRestart() {
    const now = Date.now();
    
    // 重置小时计数
    if (now > restartCounts.hour.resetTime) {
        restartCounts.hour = { count: 0, resetTime: now + 3600000 };
    }
    
    // 重置天计数
    if (now > restartCounts.day.resetTime) {
        restartCounts.day = { count: 0, resetTime: now + 86400000 };
    }
    
    // 检查限制
    if (restartCounts.hour.count >= CONFIG.MAX_RESTARTS_PER_HOUR) {
        log(`每小时重启次数已达上限: ${CONFIG.MAX_RESTARTS_PER_HOUR}`, 'WARN');
        return false;
    }
    
    if (restartCounts.day.count >= CONFIG.MAX_RESTARTS_PER_DAY) {
        log(`每天重启次数已达上限: ${CONFIG.MAX_RESTARTS_PER_DAY}`, 'WARN');
        return false;
    }
    
    return true;
}

// ===== 内存监控 =====

// 获取内存使用率
function getMemoryUsage() {
    const memory = process.memoryUsage();
    const usedMB = Math.round(memory.heapUsed / 1024 / 1024 * 100) / 100;
    const totalMB = Math.round(memory.heapTotal / 1024 / 1024 * 100) / 100;
    const usagePercent = Math.round((usedMB / totalMB) * 100);
    
    return {
        usedMB,
        totalMB,
        usagePercent,
        timestamp: Date.now()
    };
}

// 检查服务器健康状态
function checkServerHealth() {
    return new Promise((resolve) => {
        const http = require('http');
        
        const options = {
            hostname: 'localhost',
            port: CONFIG.SERVER_PORT,
            path: '/health',
            method: 'GET',
            timeout: 5000
        };
        
        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const health = JSON.parse(data);
                    resolve({
                        healthy: res.statusCode === 200,
                        statusCode: res.statusCode,
                        data: health
                    });
                } catch (error) {
                    resolve({
                        healthy: false,
                        statusCode: res.statusCode,
                        error: '解析响应失败'
                    });
                }
            });
        });
        
        req.on('error', (error) => {
            resolve({
                healthy: false,
                error: error.code || error.message
            });
        });
        
        req.on('timeout', () => {
            req.destroy();
            resolve({
                healthy: false,
                error: '请求超时'
            });
        });
        
        req.end();
    });
}

// ===== 主监控循环 =====
async function monitorLoop() {
    try {
        // 1. 检查内存使用
        const memory = getMemoryUsage();
        log(`内存使用: ${memory.usagePercent}% (${memory.usedMB}MB/${memory.totalMB}MB)`, 'MONITOR');
        
        // 2. 检查服务器健康状态
        const health = await checkServerHealth();
        
        // 3. 判断是否需要重启
        let restartReason = null;
        
        // 情况A: 内存使用率过高（使用连续计数机制）
        if (memory.usagePercent > CONFIG.HIGH_MEMORY_THRESHOLD) {
            highMemoryCount++;
            log(`检测到高内存使用率: ${memory.usagePercent}% (连续第${highMemoryCount}次)`, 'WARN');
            
            // 检查是否达到连续次数阈值
            if (highMemoryCount >= CONFIG.HIGH_MEMORY_COUNT_THRESHOLD) {
                restartReason = `内存使用率连续过高: ${memory.usagePercent}% (连续${highMemoryCount}次)`;
                highMemoryCount = 0; // 重置计数
            }
        } else {
            // 内存恢复正常，重置计数
            if (highMemoryCount > 0) {
                log(`内存使用率恢复正常: ${memory.usagePercent}%，重置连续计数`, 'INFO');
                highMemoryCount = 0;
            }
        }
        
        // 情况B: 服务器不健康
        if (!health.healthy) {
            restartReason = `服务器不健康: ${health.error || '状态码 ' + health.statusCode}`;
        }
        
        // 4. 执行重启（如果需要）
        if (restartReason) {
            log(`触发重启条件: ${restartReason}`, 'WARN');
            await restartServer(restartReason);
        }
        
        // 5. 记录重启统计
        log(`重启统计 - 本小时: ${restartCounts.hour.count}/${CONFIG.MAX_RESTARTS_PER_HOUR}, 本日: ${restartCounts.day.count}/${CONFIG.MAX_RESTARTS_PER_DAY}`, 'STATS');
        
    } catch (error) {
        log(`监控循环错误: ${error.message}`, 'ERROR');
    }
}

// ===== 系统启动 =====
function startSystem() {
    log('='.repeat(60), 'INFO');
    log('AI24X自动内存监控与重启系统启动', 'INFO');
    log(`配置: 检查间隔${CONFIG.CHECK_INTERVAL/1000}秒, 内存阈值${CONFIG.HIGH_MEMORY_THRESHOLD}%, 持续${CONFIG.HIGH_MEMORY_DURATION/1000}秒触发重启`, 'INFO');
    log('='.repeat(60), 'INFO');
    
    // 启动服务器
    startServer();
    
    // 启动监控循环
    setInterval(monitorLoop, CONFIG.CHECK_INTERVAL);
    
    // 首次检查
    setTimeout(monitorLoop, 10000);
    
    log('监控系统已启动，开始监控服务器状态', 'SUCCESS');
}

// ===== 优雅关闭 =====
process.on('SIGTERM', () => {
    log('收到SIGTERM信号，正在关闭系统...', 'INFO');
    shutdown();
});

process.on('SIGINT', () => {
    log('收到SIGINT信号，正在关闭系统...', 'INFO');
    shutdown();
});

async function shutdown() {
    log('开始关闭系统...', 'INFO');
    
    // 停止服务器
    if (serverProcess) {
        await stopServer();
    }
    
    log('系统已关闭', 'INFO');
    process.exit(0);
}

// ===== 启动系统 =====
startSystem();

// ===== 导出函数（用于测试） =====
module.exports = {
    startServer,
    stopServer,
    restartServer,
    getMemoryUsage,
    checkServerHealth,
    CONFIG
};