/**
 * AI24X分享管理器
 * 版本: 1.0.0
 * 功能: 管理分享功能、社交媒体分享、分享统计
 */

class ShareManager {
    constructor() {
        this.sharePlatforms = {
            wechat: {
                name: '微信',
                icon: 'fab fa-weixin',
                color: '#07c160',
                shareUrl: (link, title, description) => {
                    // 微信分享需要特殊处理，这里使用通用分享
                    return `https://wx.qq.com/`;
                }
            },
            qq: {
                name: 'QQ',
                icon: 'fab fa-qq',
                color: '#12b7f5',
                shareUrl: (link, title, description) => {
                    return `https://connect.qq.com/widget/shareqq/index.html?url=${encodeURIComponent(link)}&title=${encodeURIComponent(title)}&summary=${encodeURIComponent(description)}`;
                }
            },
            weibo: {
                name: '微博',
                icon: 'fab fa-weibo',
                color: '#e6162d',
                shareUrl: (link, title, description) => {
                    return `https://service.weibo.com/share/share.php?url=${encodeURIComponent(link)}&title=${encodeURIComponent(title)}&pic=&appkey=`;
                }
            },
            qzone: {
                name: 'QQ空间',
                icon: 'fab fa-qq',
                color: '#F7B500',
                shareUrl: (link, title, description) => {
                    return `https://sns.qzone.qq.com/cgi-bin/qzshare/cgi_qzshare_onekey?url=${encodeURIComponent(link)}&title=${encodeURIComponent(title)}&summary=${encodeURIComponent(description)}`;
                }
            },
            linkedin: {
                name: '领英',
                icon: 'fab fa-linkedin',
                color: '#0077B5',
                shareUrl: (link, title, description) => {
                    return `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(link)}`;
                }
            },
            twitter: {
                name: 'Twitter',
                icon: 'fab fa-twitter',
                color: '#1DA1F2',
                shareUrl: (link, title, description) => {
                    return `https://twitter.com/intent/tweet?url=${encodeURIComponent(link)}&text=${encodeURIComponent(title)}`;
                }
            },
            facebook: {
                name: 'Facebook',
                icon: 'fab fa-facebook',
                color: '#1877F2',
                shareUrl: (link, title, description) => {
                    return `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(link)}`;
                }
            }
        };
        
        this.shareData = {
            title: '加入AI24X，探索AI无限可能！',
            description: 'AI24X为您提供最先进的AI工具和资源，让AI技术触手可及。立即加入，开启智能未来！',
            hashtags: 'AI,人工智能,AI工具,科技创新',
            image: window.location.origin + '/images/ai24x-share.jpg'
        };
        
        this.init();
    }
    
    /**
     * 初始化分享管理器
     */
    init() {
        console.log('🎯 初始化分享管理器...');
        
        // 绑定分享按钮事件
        this.bindShareButtons();
        
        // 绑定复制链接按钮
        this.bindCopyButtons();
        
        // 绑定菜单切换
        this.bindMenuNavigation();
        
        console.log('✅ 分享管理器初始化完成');
    }
    
    /**
     * 绑定分享按钮事件
     */
    bindShareButtons() {
        // 微信分享
        const wechatBtn = document.getElementById('shareWechatBtn');
        if (wechatBtn) {
            wechatBtn.addEventListener('click', () => this.shareToPlatform('wechat'));
        }
        
        // QQ分享
        const qqBtn = document.getElementById('shareQQBtn');
        if (qqBtn) {
            qqBtn.addEventListener('click', () => this.shareToPlatform('qq'));
        }
        
        // 微博分享
        const weiboBtn = document.getElementById('shareWeiboBtn');
        if (weiboBtn) {
            weiboBtn.addEventListener('click', () => this.shareToPlatform('weibo'));
        }
        
        // 复制链接
        const linkBtn = document.getElementById('shareLinkBtn');
        if (linkBtn) {
            linkBtn.addEventListener('click', () => this.copyShareLink());
        }
        
        // 复制邀请码按钮
        const copyCodeBtn = document.getElementById('copyInviteCodeBtn');
        if (copyCodeBtn) {
            copyCodeBtn.addEventListener('click', () => this.copyInviteCode());
        }
    }
    
    /**
     * 绑定复制按钮事件
     */
    bindCopyButtons() {
        // 复制邀请码按钮的tooltip交互
        const copyBtn = document.getElementById('copyInviteCodeBtn');
        if (copyBtn) {
            copyBtn.addEventListener('mouseenter', () => {
                copyBtn.setAttribute('data-tooltip', '点击复制邀请码');
            });
            
            copyBtn.addEventListener('click', () => {
                setTimeout(() => {
                    copyBtn.setAttribute('data-tooltip', '已复制！');
                }, 100);
                
                setTimeout(() => {
                    copyBtn.setAttribute('data-tooltip', '点击复制');
                }, 2000);
            });
        }
    }
    
    /**
     * 绑定菜单导航
     */
    bindMenuNavigation() {
        const menuItems = document.querySelectorAll('.menu-item');
        const sections = document.querySelectorAll('.dashboard-section');
        
        menuItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                
                const targetId = item.getAttribute('href').substring(1);
                
                // 更新活跃菜单项
                menuItems.forEach(menuItem => {
                    menuItem.classList.remove('active');
                });
                item.classList.add('active');
                
                // 显示对应区域
                sections.forEach(section => {
                    section.classList.remove('active');
                    if (section.id === targetId) {
                        section.classList.add('active');
                    }
                });
                
                // 平滑滚动到对应区域
                const targetSection = document.getElementById(targetId);
                if (targetSection) {
                    targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
    }
    
    /**
     * 分享到指定平台
     */
    shareToPlatform(platform) {
        if (!window.inviteGenerator) {
            console.error('邀请生成器未初始化');
            this.showNotification('分享功能暂不可用', 'error');
            return;
        }
        
        const platformInfo = this.sharePlatforms[platform];
        if (!platformInfo) {
            console.error('不支持的分享平台:', platform);
            return;
        }
        
        // 获取分享链接
        const shareLink = window.inviteGenerator.generateShareLink();
        if (!shareLink) {
            this.showNotification('无法生成分享链接', 'error');
            return;
        }
        
        // 记录分享行为
        window.inviteGenerator.recordShare(platform);
        
        // 生成分享URL
        const shareUrl = platformInfo.shareUrl(
            shareLink,
            this.shareData.title,
            this.shareData.description
        );
        
        console.log(`📤 分享到 ${platformInfo.name}:`, shareUrl);
        
        // 打开分享窗口
        this.openShareWindow(shareUrl, platformInfo.name);
        
        // 显示成功通知
        this.showNotification(`已分享到${platformInfo.name}！`, 'success');
    }
    
    /**
     * 打开分享窗口
     */
    openShareWindow(url, platformName) {
        const windowFeatures = 'width=600,height=400,menubar=no,toolbar=no,location=no,status=no,scrollbars=yes,resizable=yes';
        
        try {
            const shareWindow = window.open(url, `share_${platformName}`, windowFeatures);
            
            if (!shareWindow || shareWindow.closed || typeof shareWindow.closed === 'undefined') {
                // 如果弹窗被阻止，显示提示
                this.showNotification(`请允许弹窗以分享到${platformName}，或手动复制链接分享。`, 'info');
                
                // 提供手动复制选项
                setTimeout(() => {
                    if (confirm(`无法打开${platformName}分享页面，是否复制分享链接手动分享？`)) {
                        this.copyShareLink();
                    }
                }, 500);
            }
        } catch (error) {
            console.error('打开分享窗口失败:', error);
            this.showNotification('分享失败，请重试', 'error');
        }
    }
    
    /**
     * 复制分享链接
     */
    copyShareLink() {
        if (!window.inviteGenerator) {
            this.showNotification('分享功能暂不可用', 'error');
            return false;
        }
        
        const success = window.inviteGenerator.copyShareLink();
        
        if (success) {
            // 记录分享行为（直接复制也算分享）
            window.inviteGenerator.recordShare('direct');
        }
        
        return success;
    }
    
    /**
     * 复制邀请码
     */
    copyInviteCode() {
        if (!window.inviteGenerator) {
            this.showNotification('邀请功能暂不可用', 'error');
            return false;
        }
        
        return window.inviteGenerator.copyInviteCode();
    }
    
    /**
     * 生成分享图片（未来功能）
     */
    generateShareImage() {
        // 这里可以集成生成分享图片的功能
        // 例如使用html2canvas生成包含邀请码的图片
        console.log('🖼️ 生成分享图片功能开发中...');
        this.showNotification('分享图片功能即将上线！', 'info');
        
        return null;
    }
    
    /**
     * 获取分享统计
     */
    getShareStats() {
        if (!window.inviteGenerator) {
            return null;
        }
        
        return window.inviteGenerator.getStats();
    }
    
    /**
     * 显示分享统计面板
     */
    showShareStats() {
        const stats = this.getShareStats();
        if (!stats) return;
        
        const statsHtml = `
            <div class="stats-modal">
                <h3><i class="fas fa-chart-pie"></i> 分享统计</h3>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">${stats.shares}</div>
                        <div class="stat-label">总分享次数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.clicks}</div>
                        <div class="stat-label">链接点击次数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.registrations}</div>
                        <div class="stat-label">成功邀请人数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.conversionRate}%</div>
                        <div class="stat-label">转化率</div>
                    </div>
                </div>
                ${Object.keys(stats.platformStats).length > 0 ? `
                    <div class="platform-stats">
                        <h4>平台分布</h4>
                        <div class="platform-list">
                            ${Object.entries(stats.platformStats).map(([platform, count]) => `
                                <div class="platform-item">
                                    <span class="platform-name">${this.sharePlatforms[platform]?.name || platform}</span>
                                    <span class="platform-count">${count}次</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        
        // 这里可以显示模态框
        console.log('📊 分享统计:', stats);
    }
    
    /**
     * 显示通知
     */
    showNotification(message, type = 'success') {
        if (window.inviteGenerator && window.inviteGenerator.showNotification) {
            window.inviteGenerator.showNotification(message, type);
        } else {
            console.log('通知:', message);
            alert(message);
        }
    }
    
    /**
     * 分享到所有平台（测试用）
     */
    shareToAllPlatforms() {
        Object.keys(this.sharePlatforms).forEach(platform => {
            setTimeout(() => {
                this.shareToPlatform(platform);
            }, 1000 * Object.keys(this.sharePlatforms).indexOf(platform));
        });
    }
    
    /**
     * 设置分享数据
     */
    setShareData(data) {
        this.shareData = { ...this.shareData, ...data };
        console.log('📝 更新分享数据:', this.shareData);
    }
    
    /**
     * 获取当前分享数据
     */
    getShareData() {
        return { ...this.shareData };
    }
}

// 创建全局实例
window.shareManager = new ShareManager();

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 确保邀请生成器已初始化
    if (!window.inviteGenerator) {
        console.warn('邀请生成器未自动初始化，手动初始化...');
        window.inviteGenerator = new (require('./invite-generator.js'))();
    }
    
    // 确保分享管理器已初始化
    if (!window.shareManager) {
        window.shareManager = new ShareManager();
    }
    
    console.log('🚀 AI24X分享系统已就绪');
});

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ShareManager;
}