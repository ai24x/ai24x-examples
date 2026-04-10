/**
 * AI24X性能监控系统
 * 实时监控系统性能，提供预警和优化建议
 */

const os = require('os');
const v8 = require('v8');

class PerformanceMonitor {
    constructor() {
        this.metrics = {
            startTime: new Date(),
            requests: [],
            errors: [],
            warnings: [],
            systemMetrics: []
        };
        
        this.thresholds = {
            cpu: 80, // CPU使用率阈值
            memory: 85, // 内存使用率阈值
            responseTime: 1000, // 响应时间阈值(ms)
            errorRate: 1 // 错误率阈值(%)
        };
        
        this.startMonitoring();
    }
    
    // 开始监控
    startMonitoring() {
        // 每30秒收集一次系统指标
        this.monitorInterval = setInterval(() => {
            this.collectSystemMetrics();
            this.checkThresholds();
        }, 30000);
        
        console.log('[PerformanceMonitor] 性能监控已启动');
    }
    
    // 停止监控
    stopMonitoring() {
        if (this.monitorInterval) {
            clearInterval(this.monitorInterval);
            console.log('[PerformanceMonitor] 性能监控已停止');
        }
    }
    
    // 收集系统指标
    collectSystemMetrics() {
        const metrics = {
            timestamp: new Date().toISOString(),
            cpu: {
                loadavg: os.loadavg(),
                cores: os.cpus().length,
                usage: this.getCpuUsage()
            },
            memory: {
                total: os.totalmem(),
                free: os.freemem(),
                used: os.totalmem() - os.freemem(),
                usage: ((os.totalmem() - os.freemem()) / os.totalmem() * 100).toFixed(2)
            },
            heap: {
                total: v8.getHeapStatistics().total_heap_size,
                used: v8.getHeapStatistics().used_heap_size,
                usage: (v8.getHeapStatistics().used_heap_size / v8.getHeapStatistics().total_heap_size * 100).toFixed(2)
            },
            uptime: {
                system: os.uptime(),
                process: process.uptime()
            },
            network: {
                interfaces: os.networkInterfaces()
            }
        };
        
        this.metrics.systemMetrics.push(metrics);
        
        // 只保留最近100条记录
        if (this.metrics.systemMetrics.length > 100) {
            this.metrics.systemMetrics = this.metrics.systemMetrics.slice(-100);
        }
        
        return metrics;
    }
    
    // 获取CPU使用率
    getCpuUsage() {
        const cpus = os.cpus();
        let totalIdle = 0;
        let totalTick = 0;
        
        cpus.forEach(cpu => {
            for (const type in cpu.times) {
                totalTick += cpu.times[type];
            }
            totalIdle += cpu.times.idle;
        });
        
        return {
            idle: totalIdle / cpus.length,
            total: totalTick / cpus.length,
            usage: ((totalTick - totalIdle) / totalTick * 100).toFixed(2)
        };
    }
    
    // 记录请求
    recordRequest(req, res, duration) {
        const requestInfo = {
            timestamp: new Date().toISOString(),
            method: req.method,
            path: req.path,
            statusCode: res.statusCode,
            duration: duration,
            userAgent: req.headers['user-agent'] || 'unknown',
            ip: req.ip || req.connection.remoteAddress
        };
        
        this.metrics.requests.push(requestInfo);
        
        // 只保留最近1000条请求记录
        if (this.metrics.requests.length > 1000) {
            this.metrics.requests = this.metrics.requests.slice(-1000);
        }
        
        // 检查是否超过响应时间阈值
        if (duration > this.thresholds.responseTime) {
            this.recordWarning({
                type: 'slow_request',
                message: `慢请求检测: ${req.method} ${req.path} - ${duration}ms`,
                data: requestInfo,
                timestamp: new Date().toISOString()
            });
        }
        
        // 检查错误状态码
        if (res.statusCode >= 400) {
            this.recordError({
                type: 'http_error',
                message: `HTTP错误: ${req.method} ${req.path} - ${res.statusCode}`,
                data: requestInfo,
                timestamp: new Date().toISOString()
            });
        }
        
        return requestInfo;
    }
    
    // 记录错误
    recordError(error) {
        this.metrics.errors.push(error);
        
        // 只保留最近100条错误记录
        if (this.metrics.errors.length > 100) {
            this.metrics.errors = this.metrics.errors.slice(-100);
        }
        
        console.error(`[PerformanceMonitor] 错误记录: ${error.message}`);
    }
    
    // 记录警告
    recordWarning(warning) {
        this.metrics.warnings.push(warning);
        
        // 只保留最近100条警告记录
        if (this.metrics.warnings.length > 100) {
            this.metrics.warnings = this.metrics.warnings.slice(-100);
        }
        
        console.warn(`[PerformanceMonitor] 警告记录: ${warning.message}`);
    }
    
    // 检查阈值
    checkThresholds() {
        const latestMetrics = this.metrics.systemMetrics[this.metrics.systemMetrics.length - 1];
        if (!latestMetrics) return;
        
        // 检查CPU使用率
        if (parseFloat(latestMetrics.cpu.usage.usage) > this.thresholds.cpu) {
            this.recordWarning({
                type: 'high_cpu',
                message: `CPU使用率过高: ${latestMetrics.cpu.usage.usage}% (阈值: ${this.thresholds.cpu}%)`,
                data: latestMetrics.cpu,
                timestamp: new Date().toISOString()
            });
        }
        
        // 检查内存使用率
        if (parseFloat(latestMetrics.memory.usage) > this.thresholds.memory) {
            this.recordWarning({
                type: 'high_memory',
                message: `内存使用率过高: ${latestMetrics.memory.usage}% (阈值: ${this.thresholds.memory}%)`,
                data: latestMetrics.memory,
                timestamp: new Date().toISOString()
            });
        }
        
        // 检查堆内存使用率
        if (parseFloat(latestMetrics.heap.usage) > 80) {
            this.recordWarning({
                type: 'high_heap',
                message: `堆内存使用率过高: ${latestMetrics.heap.usage}%`,
                data: latestMetrics.heap,
                timestamp: new Date().toISOString()
            });
        }
        
        // 检查错误率
        const recentRequests = this.metrics.requests.filter(req => 
            new Date(req.timestamp) > new Date(Date.now() - 5 * 60 * 1000) // 最近5分钟
        );
        
        if (recentRequests.length > 0) {
            const errorCount = recentRequests.filter(req => req.statusCode >= 400).length;
            const errorRate = (errorCount / recentRequests.length * 100).toFixed(2);
            
            if (parseFloat(errorRate) > this.thresholds.errorRate) {
                this.recordWarning({
                    type: 'high_error_rate',
                    message: `错误率过高: ${errorRate}% (阈值: ${this.thresholds.errorRate}%)`,
                    data: { errorCount, totalRequests: recentRequests.length, errorRate },
                    timestamp: new Date().toISOString()
                });
            }
        }
    }
    
    // 获取性能报告
    getPerformanceReport() {
        const uptime = Date.now() - this.metrics.startTime;
        const uptimeHours = (uptime / (1000 * 60 * 60)).toFixed(2);
        
        const recentRequests = this.metrics.requests.filter(req => 
            new Date(req.timestamp) > new Date(Date.now() - 5 * 60 * 1000) // 最近5分钟
        );
        
        const avgResponseTime = recentRequests.length > 0
            ? recentRequests.reduce((sum, req) => sum + req.duration, 0) / recentRequests.length
            : 0;
        
        const errorCount = recentRequests.filter(req => req.statusCode >= 400).length;
        const errorRate = recentRequests.length > 0
            ? (errorCount / recentRequests.length * 100).toFixed(2)
            : 0;
        
        const latestMetrics = this.metrics.systemMetrics[this.metrics.systemMetrics.length - 1] || {};
        
        return {
            summary: {
                uptime: `${uptimeHours}小时`,
                totalRequests: this.metrics.requests.length,
                recentRequests: recentRequests.length,
                avgResponseTime: `${avgResponseTime.toFixed(2)}ms`,
                errorRate: `${errorRate}%`,
                warnings: this.metrics.warnings.length,
                errors: this.metrics.errors.length
            },
            currentMetrics: latestMetrics,
            thresholds: this.thresholds,
            recentWarnings: this.metrics.warnings.slice(-10),
            recentErrors: this.metrics.errors.slice(-10),
            recommendations: this.generateRecommendations()
        };
    }
    
    // 生成优化建议
    generateRecommendations() {
        const recommendations = [];
        const latestMetrics = this.metrics.systemMetrics[this.metrics.systemMetrics.length - 1];
        
        if (!latestMetrics) return recommendations;
        
        // CPU建议
        if (parseFloat(latestMetrics.cpu.usage.usage) > 70) {
            recommendations.push({
                type: 'cpu',
                priority: 'high',
                message: 'CPU使用率较高，建议优化代码或增加服务器资源',
                details: `当前CPU使用率: ${latestMetrics.cpu.usage.usage}%`
            });
        }
        
        // 内存建议
        if (parseFloat(latestMetrics.memory.usage) > 75) {
            recommendations.push({
                type: 'memory',
                priority: 'high',
                message: '内存使用率较高，建议检查内存泄漏或增加内存',
                details: `当前内存使用率: ${latestMetrics.memory.usage}%`
            });
        }
        
        // 堆内存建议
        if (parseFloat(latestMetrics.heap.usage) > 70) {
            recommendations.push({
                type: 'heap',
                priority: 'medium',
                message: '堆内存使用率较高，建议优化内存使用',
                details: `当前堆内存使用率: ${latestMetrics.heap.usage}%`
            });
        }
        
        // 响应时间建议
        const recentRequests = this.metrics.requests.filter(req => 
            new Date(req.timestamp) > new Date(Date.now() - 5 * 60 * 1000)
        );
        
        if (recentRequests.length > 0) {
            const slowRequests = recentRequests.filter(req => req.duration > 500);
            if (slowRequests.length > 10) {
                recommendations.push({
                    type: 'response_time',
                    priority: 'high',
                    message: '检测到多个慢请求，建议优化数据库查询或API逻辑',
                    details: `最近5分钟慢请求数量: ${slowRequests.length}`
                });
            }
        }
        
        return recommendations;
    }
    
    // 获取实时指标
    getRealtimeMetrics() {
        const latestMetrics = this.metrics.systemMetrics[this.metrics.systemMetrics.length - 1] || {};
        const recentRequests = this.metrics.requests.filter(req => 
            new Date(req.timestamp) > new Date(Date.now() - 60 * 1000) // 最近1分钟
        );
        
        return {
            timestamp: new Date().toISOString(),
            system: {
                cpu: latestMetrics.cpu ? `${latestMetrics.cpu.usage.usage}%` : 'N/A',
                memory: latestMetrics.memory ? `${latestMetrics.memory.usage}%` : 'N/A',
                heap: latestMetrics.heap ? `${latestMetrics.heap.usage}%` : 'N/A'
            },
            requests: {
                perMinute: recentRequests.length,
                avgResponseTime: recentRequests.length > 0
                    ? recentRequests.reduce((sum, req) => sum + req.duration, 0) / recentRequests.length
                    : 0
            },
            status: this.getSystemStatus()
        };
    }
    
    // 获取系统状态
    getSystemStatus() {
        const latestMetrics = this.metrics.systemMetrics[this.metrics.systemMetrics.length - 1];
        if (!latestMetrics) return 'unknown';
        
        const cpuUsage = parseFloat(latestMetrics.cpu.usage.usage);
        const memoryUsage = parseFloat(latestMetrics.memory.usage);
        
        if (cpuUsage > 90 || memoryUsage > 90) {
            return 'critical';
        } else if (cpuUsage > 70 || memoryUsage > 70) {
            return 'warning';
        } else {
            return 'healthy';
        }
    }
    
    // 重置指标
    resetMetrics() {
        this.metrics = {
            startTime: new Date(),
            requests: [],
            errors: [],
            warnings: [],
            systemMetrics: []
        };
        
        console.log('[PerformanceMonitor] 性能指标已重置');
    }
}

// 创建全局监控实例
const performanceMonitor = new PerformanceMonitor();

// 导出
module.exports = performanceMonitor;