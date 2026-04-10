/**
 * AI24X邀请码生成器
 * 版本: 1.0.0
 * 功能: 生成唯一邀请码、管理邀请数据、本地存储
 */

class InviteGenerator {
    constructor() {
        this.storageKey = 'ai24x_invite_data';
        this.defaultData = {
            inviteCode: null,
            generatedAt: null,
            shares: 0,
            clicks: 0,
            registrations: 0,
            lastShareTime: null,
            userInfo: {
                name: 'AI24X用户',
                email: 'user@example.com'
            }
        };
        
        this.init();
    }
    
    /**
     * 初始化邀请系统
     */
    init() {
        console.log('🎯 初始化邀请码生成器...');
        
        // 加载或创建邀请数据
        this.loadInviteData();
        
        // 如果没有邀请码，生成一个
        if (!this.inviteData.inviteCode) {
            this.generateInviteCode();
        }
        
        // 更新页面显示
        this.updateDisplay();
        
        console.log('✅ 邀请系统初始化完成');
        console.log('   邀请码:', this.inviteData.inviteCode);
        console.log('   生成时间:', new Date(this.inviteData.generatedAt).toLocaleString());
    }
    
    /**
     * 生成唯一邀请码
     * 格式: AI24X-XXXX-XXXX
     */
    generateInviteCode() {
        const prefix = "AI24X";
        
        // 使用时间戳和随机数生成唯一码
        const timestamp = Date.now().toString(36).toUpperCase().slice(-4);
        const random = Math.random().toString(36).substr(2, 4).toUpperCase();
        
        const inviteCode = `${prefix}-${timestamp}-${random}`;
        
        // 保存数据
        this.inviteData.inviteCode = inviteCode;
        this.inviteData.generatedAt = Date.now();
        this.inviteData.shares = 0;
        this.inviteData.clicks = 0;
        this.inviteData.registrations = 0;
        
        this.saveInviteData();
        
        console.log('🎉 生成新邀请码:', inviteCode);
        return inviteCode;
    }
    
    /**
     * 获取当前邀请码
     */
    getInviteCode() {
        return this.inviteData.inviteCode;
    }
    
    /**
     * 生成分享链接
     */
    generateShareLink() {
        const code = this.getInviteCode();
        if (!code) return null;
        
        const baseUrl = window.location.origin;
        return `${baseUrl}/invite/${code}`;
    }
    
    /**
     * 记录分享行为
     */
    recordShare(platform = 'direct') {
        this.inviteData.shares++;
        this.inviteData.lastShareTime = Date.now();
        
        // 记录平台统计
        if (!this.inviteData.platformStats) {
            this.inviteData.platformStats = {};
        }
        
        this.inviteData.platformStats[platform] = (this.inviteData.platformStats[platform] || 0) + 1;
        
        this.saveInviteData();
        this.updateDisplay();
        
        console.log(`📤 记录分享到 ${platform}, 总分享次数: ${this.inviteData.shares}`);
        
        // 显示通知
        this.showNotification(`分享成功！总分享次数: ${this.inviteData.shares}`);
        
        return this.inviteData.shares;
    }
    
    /**
     * 记录链接点击
     */
    recordClick() {
        this.inviteData.clicks++;
        this.saveInviteData();
        this.updateDisplay();
        
        console.log(`👆 记录链接点击, 总点击次数: ${this.inviteData.clicks}`);
        
        return this.inviteData.clicks;
    }
    
    /**
     * 记录注册成功
     */
    recordRegistration() {
        this.inviteData.registrations++;
        this.saveInviteData();
        this.updateDisplay();
        
        console.log(`🎊 记录注册成功, 总注册人数: ${this.inviteData.registrations}`);
        
        // 显示庆祝通知
        this.showNotification(`🎉 恭喜！成功邀请第 ${this.inviteData.registrations} 位好友！`, 'success');
        
        return this.inviteData.registrations;
    }
    
    /**
     * 获取统计数据
     */
    getStats() {
        return {
            shares: this.inviteData.shares,
            clicks: this.inviteData.clicks,
            registrations: this.inviteData.registrations,
            conversionRate: this.inviteData.clicks > 0 
                ? ((this.inviteData.registrations / this.inviteData.clicks) * 100).toFixed(1)
                : 0,
            platformStats: this.inviteData.platformStats || {}
        };
    }
    
    /**
     * 复制邀请码到剪贴板
     */
    copyInviteCode() {
        const code = this.getInviteCode();
        if (!code) {
            this.showNotification('邀请码未生成，请刷新页面重试', 'error');
            return false;
        }
        
        return this.copyToClipboard(code, '邀请码');
    }
    
    /**
     * 复制分享链接到剪贴板
     */
    copyShareLink() {
        const link = this.generateShareLink();
        if (!link) {
            this.showNotification('无法生成分享链接', 'error');
            return false;
        }
        
        return this.copyToClipboard(link, '分享链接');
    }
    
    /**
     * 通用复制到剪贴板函数
     */
    copyToClipboard(text, itemName = '内容') {
        return new Promise((resolve) => {
            // 使用现代Clipboard API
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text)
                    .then(() => {
                        this.showNotification(`${itemName}已复制到剪贴板！`);
                        resolve(true);
                    })
                    .catch(err => {
                        console.error('复制失败:', err);
                        this.fallbackCopy(text, itemName, resolve);
                    });
            } else {
                // 降级方案
                this.fallbackCopy(text, itemName, resolve);
            }
        });
    }
    
    /**
     * 降级复制方案
     */
    fallbackCopy(text, itemName, resolve) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                this.showNotification(`${itemName}已复制到剪贴板！`);
                resolve(true);
            } else {
                this.showNotification('复制失败，请手动复制', 'error');
                resolve(false);
            }
        } catch (err) {
            console.error('降级复制失败:', err);
            this.showNotification('复制失败，请手动复制', 'error');
            resolve(false);
        } finally {
            document.body.removeChild(textArea);
        }
    }
    
    /**
     * 显示通知
     */
    showNotification(message, type = 'success') {
        const notification = document.getElementById('notification');
        const notificationText = document.getElementById('notificationText');
        
        if (!notification || !notificationText) {
            console.log('通知:', message);
            return;
        }
        
        // 设置消息和类型
        notificationText.textContent = message;
        
        // 根据类型设置样式
        notification.className = 'notification';
        if (type === 'success') {
            notification.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';
        } else if (type === 'error') {
            notification.style.background = 'linear-gradient(135deg, #dc3545 0%, #fd7e14 100%)';
        } else if (type === 'info') {
            notification.style.background = 'linear-gradient(135deg, #17a2b8 0%, #20c997 100%)';
        }
        
        // 显示通知
        notification.style.display = 'flex';
        
        // 3秒后自动隐藏
        setTimeout(() => {
            notification.style.display = 'none';
        }, 3000);
    }
    
    /**
     * 更新页面显示
     */
    updateDisplay() {
        // 更新邀请码显示
        const inviteCodeMain = document.getElementById('inviteCodeMain');
        if (inviteCodeMain && this.inviteData.inviteCode) {
            const codeParts = this.inviteData.inviteCode.split('-');
            if (codeParts.length >= 3) {
                inviteCodeMain.textContent = `${codeParts[1]}-${codeParts[2]}`;
            }
        }
        
        // 更新统计数据
        const stats = this.getStats();
        
        const invitedCount = document.getElementById('invitedCount');
        if (invitedCount) invitedCount.textContent = stats.registrations;
        
        const linkClicks = document.getElementById('linkClicks');
        if (linkClicks) linkClicks.textContent = stats.clicks;
        
        const inviteCount = document.getElementById('inviteCount');
        if (inviteCount) inviteCount.textContent = stats.registrations;
        
        const shareCount = document.getElementById('shareCount');
        if (shareCount) shareCount.textContent = stats.shares;
        
        const rewardPoints = document.getElementById('rewardPoints');
        if (rewardPoints) {
            // 简单积分计算：每邀请1人=100分，每分享1次=10分
            const points = (stats.registrations * 100) + (stats.shares * 10);
            rewardPoints.textContent = points;
        }
    }
    
    /**
     * 加载邀请数据
     */
    loadInviteData() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            if (saved) {
                this.inviteData = JSON.parse(saved);
                console.log('📂 加载保存的邀请数据');
            } else {
                this.inviteData = { ...this.defaultData };
                console.log('🆕 创建新的邀请数据');
            }
        } catch (error) {
            console.error('加载邀请数据失败:', error);
            this.inviteData = { ...this.defaultData };
        }
    }
    
    /**
     * 保存邀请数据
     */
    saveInviteData() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.inviteData));
        } catch (error) {
            console.error('保存邀请数据失败:', error);
        }
    }
    
    /**
     * 重置邀请数据（测试用）
     */
    resetData() {
        if (confirm('确定要重置所有邀请数据吗？这将删除所有统计信息。')) {
            localStorage.removeItem(this.storageKey);
            this.inviteData = { ...this.defaultData };
            this.generateInviteCode();
            this.updateDisplay();
            this.showNotification('邀请数据已重置', 'info');
        }
    }
}

// 创建全局实例
window.inviteGenerator = new InviteGenerator();

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InviteGenerator;
}