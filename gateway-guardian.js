/**
 * OpenClaw网关守护者
 * 监控和保护OpenClaw网关，防止意外关闭
 */

const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const CONFIG = {
    gatewayPort: 18789, // OpenClaw网关端口
    checkInterval: 30000, // 每30秒检查一次
    maxRestartAttempts: 3, // 最大重启尝试次数
    restartCooldown: 60000, // 重启冷却时间60秒
    logFile: path.join(__dirname, 'gateway-guardian.log'),
    alertThreshold: 500, // 内存阈值500MB
    gatewayPath: 'C:\\AI24X\\OpenClaw' // OpenClaw安装路径
};

// 监控状态
let monitorStats = {
    startTime: Date.now(),
    checks: 0,
    alerts: 0,
    restarts: 0,
    lastRestart: 0,
    gatewayPid: null
};

// 日志函数
function log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(CONFIG.logFile, logMessage + '\n', 'utf8');
}

// 获取网关PID
function getGatewayPid() {
    return new Promise((resolve, reject) => {
        exec(`netstat -ano | findstr :${CONFIG.gatewayPort}`, (error, stdout, stderr) => {
            if (error) {
                resolve(null);
                return;
            }
            
            const lines = stdout.trim().split('\n');
            for (const line of lines) {
                const parts = line.trim().split(/\s+/);
                if (parts.length >= 5 && parts[1].includes(`:${CONFIG.gatewayPort}`)) {
                    const pid = parseInt(parts[parts.length - 1]);
                    if (!isNaN(pid) && pid > 0) {
                        resolve(pid);
                        return;
                    }
                }
            }
            resolve(null);
        });
    });
}

// 获取进程信息
function getProcessInfo(pid) {
    return new Promise((resolve, reject) => {
        exec(`tasklist /FI "PID eq ${pid}" /FO CSV`, (error, stdout, stderr) => {
            if (error) {
                resolve(null);
                return;
            }
            
            const lines = stdout.trim().split('\n');
            if (lines.length > 1) {
                const parts = lines[1].split(',');
                if (parts.length >= 5) {
                    // 解析内存字符串 "335,100 K" -> 335100
                    const memoryStr = parts[4].replace(/"/g, '').replace(/,/g, '').replace(' K', '');
                    const memoryKB = parseInt(memoryStr);
                    
                    resolve({
                        pid: pid,
                        name: parts[0].replace(/"/g, ''),
                        session: parts[1].replace(/"/g, ''),
                        sessionNum: parts[2].replace(/"/g, ''),
                        memoryKB: memoryKB,
                        memoryMB: Math.round(memoryKB / 1024 * 100) / 100
                    });
                    return;
                }
            }
            resolve(null);
        });
    });
}

// 检查网关状态
async function checkGatewayStatus() {
    monitorStats.checks++;
    
    const pid = await getGatewayPid();
    
    if (!pid) {
        log(`❌ 网关未运行 (端口${CONFIG.gatewayPort})`, 'ALERT');
        monitorStats.alerts++;
        return { running: false, pid: null, info: null };
    }
    
    const info = await getProcessInfo(pid);
    
    if (!info) {
        log(`⚠️ 找到PID但无法获取进程信息: ${pid}`, 'WARNING');
        return { running: true, pid: pid, info: null };
    }
    
    // 检查内存使用
    if (info.memoryMB > CONFIG.alertThreshold) {
        log(`⚠️ 网关内存使用过高: ${info.memoryMB}MB > ${CONFIG.alertThreshold}MB`, 'WARNING');
        monitorStats.alerts++;
    }
    
    // 更新网关PID
    if (monitorStats.gatewayPid !== pid) {
        log(`🔍 网关PID更新: ${monitorStats.gatewayPid || '无'} → ${pid}`);
        monitorStats.gatewayPid = pid;
    }
    
    return {
        running: true,
        pid: pid,
        info: info,
        memoryOK: info.memoryMB <= CONFIG.alertThreshold
    };
}

// 重启网关（谨慎使用）
function restartGateway() {
    const now = Date.now();
    const cooldownRemaining = CONFIG.restartCooldown - (now - monitorStats.lastRestart);
    
    // 检查冷却时间
    if (cooldownRemaining > 0) {
        log(`⏳ 重启冷却中，还需${Math.round(cooldownRemaining/1000)}秒`, 'WARNING');
        return false;
    }
    
    // 检查重启次数
    if (monitorStats.restarts >= CONFIG.maxRestartAttempts) {
        log(`❌ 已达到最大重启次数 (${CONFIG.maxRestartAttempts})`, 'ERROR');
        return false;
    }
    
    log(`🔄 正在重启OpenClaw网关... (尝试 ${monitorStats.restarts + 1}/${CONFIG.maxRestartAttempts})`);
    
    // 优雅重启命令
    exec(`cd "${CONFIG.gatewayPath}" && openclaw gateway restart`, (error, stdout, stderr) => {
        if (error) {
            log(`❌ 网关重启失败: ${error.message}`, 'ERROR');
            return;
        }
        
        log(`✅ 网关重启命令已发送`);
        log(`📋 输出: ${stdout}`);
        
        if (stderr) {
            log(`⚠️ 错误输出: ${stderr}`, 'WARNING');
        }
        
        monitorStats.restarts++;
        monitorStats.lastRestart = now;
        
        // 记录重启统计
        log(`📊 重启统计: 总重启=${monitorStats.restarts}, 最后重启=${new Date(now).toISOString()}`);
    });
    
    return true;
}

// 监控循环
async function monitorLoop() {
    log('='.repeat(60));
    log('🛡️ OpenClaw网关守护者已启动');
    log(`📊 配置: 端口=${CONFIG.gatewayPort}, 检查间隔=${CONFIG.checkInterval/1000}秒`);
    log(`🎯 目标: 保护网关，防止意外关闭`);
    log('='.repeat(60));
    
    setInterval(async () => {
        try {
            const status = await checkGatewayStatus();
            
            if (status.running) {
                const statusIcon = status.memoryOK ? '✅' : '⚠️';
                log(`${statusIcon} 网关运行中: PID=${status.pid}, 内存=${status.info?.memoryMB || '未知'}MB, 进程=${status.info?.name || '未知'}`);
                
                // 内存过高警告
                if (!status.memoryOK && status.info) {
                    log(`⚠️ 网关内存使用警告: ${status.info.memoryMB}MB`, 'WARNING');
                    
                    // 可以考虑发送警报但不自动重启
                    // 自动重启网关风险较大，建议人工干预
                }
            } else {
                log(`❌ 网关未运行，需要干预`, 'ALERT');
                
                // 网关未运行，尝试重启
                log(`🔄 检测到网关停止，准备重启...`);
                const restartAttempted = restartGateway();
                
                if (!restartAttempted) {
                    log(`⏸️ 重启未执行（冷却中或已达上限）`, 'WARNING');
                }
            }
            
            // 定期输出统计
            if (monitorStats.checks % 10 === 0) {
                const uptime = Math.round((Date.now() - monitorStats.startTime) / 1000);
                log(`📊 监控统计: 运行=${uptime}秒, 检查=${monitorStats.checks}, 警报=${monitorStats.alerts}, 重启=${monitorStats.restarts}`);
            }
            
        } catch (error) {
            log(`❌ 监控检查失败: ${error.message}`, 'ERROR');
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
    log('='.repeat(60));
    log('🛑 收到关闭信号，正在停止网关守护者...');
    log('='.repeat(60));
    
    const summary = `
📊 网关守护者运行摘要:
   启动时间: ${new Date(monitorStats.startTime).toISOString()}
   运行时长: ${Math.round((Date.now() - monitorStats.startTime) / 1000)} 秒
   检查次数: ${monitorStats.checks}
   警报次数: ${monitorStats.alerts}
   重启次数: ${monitorStats.restarts}
   当前网关PID: ${monitorStats.gatewayPid || '未知'}
   日志文件: ${CONFIG.logFile}
    `;
    
    log(summary);
    log('🛡️ 网关守护者已停止');
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

// 导出函数供其他脚本使用
module.exports = {
    checkGatewayStatus,
    getGatewayPid,
    getProcessInfo,
    restartGateway,
    CONFIG,
    monitorStats
};