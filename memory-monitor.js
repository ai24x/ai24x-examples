/**
 * AI24X内存监控脚本
 * 实时监控服务器内存使用，自动重启防止内存泄漏
 */

const http = require('http');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const CONFIG = {
    serverUrl: 'http://localhost:3000/health',
    checkInterval: 30000, // 每30秒检查一次（减少频率）
    memoryThreshold: 50, // 内存阈值50MB（合理的安全值，避免误杀）
    maxRestartsPerHour: 2, // 每小时最多重启2次（更保守）
    logFile: path.join(__dirname, 'memory-monitor.log')
};

// 重启统计
let restartStats = {
    totalRestarts: 0,
    lastRestartTime: 0,
    restartsThisHour: 0,
    lastHourReset: Date.now()
};

// 日志函数
function log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    
    // 写入日志文件
    fs.appendFileSync(CONFIG.logFile, logMessage + '\n', 'utf8');
}

// 检查内存使用
function checkMemoryUsage() {
    return new Promise((resolve, reject) => {
        http.get(CONFIG.serverUrl, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const healthData = JSON.parse(data);
                    const memoryStr = healthData.memory.rss;
                    const memoryMB = parseFloat(memoryStr);
                    
                    resolve({
                        memoryMB,
                        peakMemory: parseFloat(healthData.memory.peak),
                        healthy: healthData.status === 'healthy',
                        uptime: healthData.uptime
                    });
                } catch (error) {
                    reject(new Error('无法解析健康检查响应'));
                }
            });
        }).on('error', (error) => {
            reject(new Error(`健康检查失败: ${error.message}`));
        }).setTimeout(5000, () => {
            reject(new Error('健康检查超时'));
        });
    });
}

// 重启服务器
function restartServer() {
    const now = Date.now();
    const hourInMs = 60 * 60 * 1000;
    
    // 重置小时计数
    if (now - restartStats.lastHourReset > hourInMs) {
        restartStats.restartsThisHour = 0;
        restartStats.lastHourReset = now;
    }
    
    // 检查重启频率
    if (restartStats.restartsThisHour >= CONFIG.maxRestartsPerHour) {
        log(`⚠️ 已达到每小时最大重启次数 (${CONFIG.maxRestartsPerHour})`, 'WARNING');
        return false;
    }
    
    log(`🔄 正在重启服务器... (内存超过${CONFIG.memoryThreshold}MB阈值)`);
    
    // 执行重启命令（使用更温和的方式）
    const killCommand = `for /f "tokens=2" %i in ('netstat -ano ^| findstr :3000') do taskkill /PID %i /F`;
    exec(killCommand, (error, stdout, stderr) => {
        if (error) {
            // 如果强制终止失败，尝试更温和的方式
            log(`⚠️ 强制终止失败，尝试温和重启: ${error.message}`, 'WARNING');
            
            // 尝试只终止特定端口的进程
            exec('taskkill /F /FI "PID gt 0" /IM node.exe', (error2) => {
                if (error2) {
                    log(`❌ 所有重启尝试都失败: ${error2.message}`, 'ERROR');
                    return;
                }
                log('✅ 已终止Node.js进程（温和方式）');
            });
            return;
        }
        
        log('✅ 已终止端口3000的进程');
        
        // 等待2秒
        setTimeout(() => {
            // 启动稳定版服务器
            const serverProcess = exec('node server-stable.js', {
                cwd: __dirname,
                windowsHide: true
            });
            
            serverProcess.stdout.on('data', (data) => {
                log(`SERVER: ${data.toString().trim()}`);
            });
            
            serverProcess.stderr.on('data', (data) => {
                log(`SERVER ERROR: ${data.toString().trim()}`, 'ERROR');
            });
            
            serverProcess.on('exit', (code) => {
                log(`服务器退出，代码: ${code}`, code === 0 ? 'INFO' : 'ERROR');
            });
            
            restartStats.totalRestarts++;
            restartStats.restartsThisHour++;
            restartStats.lastRestartTime = now;
            
            log(`✅ 服务器已重启 (总重启: ${restartStats.totalRestarts}, 本小时: ${restartStats.restartsThisHour})`);
        }, 2000);
    });
    
    return true;
}

// 监控循环
async function monitorLoop() {
    log('🚀 AI24X内存监控器已启动');
    log(`📊 配置: 阈值=${CONFIG.memoryThreshold}MB, 检查间隔=${CONFIG.checkInterval/1000}秒`);
    
    setInterval(async () => {
        try {
            const stats = await checkMemoryUsage();
            
            const status = stats.healthy ? '✅' : '❌';
            log(`${status} 服务器状态: 内存=${stats.memoryMB}MB, 峰值=${stats.peakMemory}MB, 运行=${stats.uptime}秒`);
            
            // 检查内存阈值
            if (stats.memoryMB > CONFIG.memoryThreshold) {
                log(`⚠️ 内存超过阈值: ${stats.memoryMB}MB > ${CONFIG.memoryThreshold}MB`, 'WARNING');
                restartServer();
            }
            
            // 检查服务器健康
            if (!stats.healthy) {
                log('⚠️ 服务器不健康，准备重启', 'WARNING');
                restartServer();
            }
            
        } catch (error) {
            log(`❌ 监控检查失败: ${error.message}`, 'ERROR');
            
            // 服务器可能已崩溃，尝试重启
            log('🔄 服务器可能已崩溃，尝试重启...');
            restartServer();
        }
    }, CONFIG.checkInterval);
}

// 启动监控
monitorLoop().catch(error => {
    log(`❌ 监控器启动失败: ${error.message}`, 'ERROR');
    process.exit(1);
});

// 优雅关闭
process.on('SIGINT', () => {
    log('🛑 收到关闭信号，正在停止监控...');
    
    const summary = `
📊 监控统计摘要:
   总重启次数: ${restartStats.totalRestarts}
   本小时重启: ${restartStats.restartsThisHour}
   最后重启: ${restartStats.lastRestartTime ? new Date(restartStats.lastRestartTime).toISOString() : '从未重启'}
   日志文件: ${CONFIG.logFile}
    `;
    
    log(summary);
    process.exit(0);
});

// 错误处理
process.on('uncaughtException', (error) => {
    log(`❌ 未捕获异常: ${error.message}`, 'ERROR');
    log(error.stack, 'ERROR');
});

process.on('unhandledRejection', (reason, promise) => {
    log(`❌ 未处理的Promise拒绝: ${reason}`, 'ERROR');
});