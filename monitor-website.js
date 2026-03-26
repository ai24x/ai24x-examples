#!/usr/bin/env node

/**
 * AI24X网站监控脚本
 * 监控网站运行状态，自动重启失败的服务
 * 创建时间：2026-03-18
 * 创建者：AI24X首席开发官
 */

const http = require('http');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const WEBSITE_URL = 'http://localhost:3000';
const CHECK_INTERVAL = 300000; // 5分钟检查一次
const MAX_RETRIES = 3;
const LOG_FILE = path.join(__dirname, 'logs', 'website-monitor.log');

// 确保日志目录存在
if (!fs.existsSync(path.join(__dirname, 'logs'))) {
    fs.mkdirSync(path.join(__dirname, 'logs'), { recursive: true });
}

// 日志函数
function log(message, level = 'INFO') {
    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    
    // 写入日志文件
    fs.appendFileSync(LOG_FILE, logMessage + '\n', 'utf8');
}

// 检查网站状态
function checkWebsiteStatus() {
    return new Promise((resolve) => {
        const req = http.get(WEBSITE_URL, (res) => {
            const statusCode = res.statusCode;
            res.on('data', () => {});
            res.on('end', () => {
                resolve({ success: true, statusCode });
            });
        });

        req.on('error', (error) => {
            resolve({ success: false, error: error.message });
        });

        req.setTimeout(10000, () => {
            req.destroy();
            resolve({ success: false, error: '请求超时' });
        });
    });
}

// 重启网站服务
function restartWebsiteService() {
    return new Promise((resolve) => {
        log('尝试重启网站服务...', 'WARN');
        
        const startScript = process.platform === 'win32' 
            ? 'start-server.bat' 
            : './start-server.sh';
        
        exec(`cd "${__dirname}" && ${startScript}`, (error, stdout, stderr) => {
            if (error) {
                log(`重启失败: ${error.message}`, 'ERROR');
                resolve(false);
                return;
            }
            
            if (stdout) log(`重启输出: ${stdout}`, 'INFO');
            if (stderr) log(`重启错误: ${stderr}`, 'WARN');
            
            log('网站服务重启命令已执行', 'INFO');
            resolve(true);
        });
    });
}

// 主监控循环
async function monitor() {
    log('AI24X网站监控服务启动', 'INFO');
    log(`监控地址: ${WEBSITE_URL}`, 'INFO');
    log(`检查间隔: ${CHECK_INTERVAL / 60000}分钟`, 'INFO');
    
    let consecutiveFailures = 0;
    
    while (true) {
        try {
            const result = await checkWebsiteStatus();
            
            if (result.success) {
                log(`网站运行正常 (状态码: ${result.statusCode})`, 'INFO');
                consecutiveFailures = 0;
            } else {
                consecutiveFailures++;
                log(`网站检查失败 (${consecutiveFailures}/${MAX_RETRIES}): ${result.error}`, 'ERROR');
                
                if (consecutiveFailures >= MAX_RETRIES) {
                    log(`连续失败${MAX_RETRIES}次，尝试重启服务`, 'WARN');
                    const restartSuccess = await restartWebsiteService();
                    
                    if (restartSuccess) {
                        log('服务重启成功，等待60秒后重新检查', 'INFO');
                        consecutiveFailures = 0;
                        await new Promise(resolve => setTimeout(resolve, 60000));
                    } else {
                        log('服务重启失败，等待5分钟后重试', 'ERROR');
                        await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL));
                    }
                }
            }
        } catch (error) {
            log(`监控过程发生错误: ${error.message}`, 'ERROR');
        }
        
        // 等待下一次检查
        await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL));
    }
}

// 处理进程退出
process.on('SIGINT', () => {
    log('收到中断信号，关闭监控服务', 'INFO');
    process.exit(0);
});

process.on('SIGTERM', () => {
    log('收到终止信号，关闭监控服务', 'INFO');
    process.exit(0);
});

// 启动监控
if (require.main === module) {
    monitor().catch(error => {
        log(`监控服务启动失败: ${error.message}`, 'ERROR');
        process.exit(1);
    });
}

module.exports = { checkWebsiteStatus, restartWebsiteService };