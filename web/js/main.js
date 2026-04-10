// AI24X Token 聚合平台 - 主JavaScript文件
// 功能：交互效果、表单验证、API调用

document.addEventListener('DOMContentLoaded', function() {
    console.log('AI24X Token 聚合平台已加载');
    
    // 初始化功能
    initSmoothScroll();
    initAnimations();
    initStatsCounter();
    initModelCards();
    initMobileMenu();
    
    // 显示欢迎消息
    showWelcomeMessage();
});

// 平滑滚动
function initSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// 动画效果
function initAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
            }
        });
    }, observerOptions);
    
    // 观察所有需要动画的元素
    document.querySelectorAll('.feature-card, .model-card, .stat').forEach(el => {
        observer.observe(el);
    });
}

// 统计数字动画
function initStatsCounter() {
    const stats = document.querySelectorAll('.stat-number');
    
    stats.forEach(stat => {
        const target = parseInt(stat.textContent);
        const duration = 2000; // 2秒
        const increment = target / (duration / 16); // 60fps
        
        let current = 0;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            stat.textContent = Math.floor(current);
        }, 16);
    });
}

// 模型卡片交互
function initModelCards() {
    const cards = document.querySelectorAll('.model-card');
    
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            const icon = card.querySelector('.model-logo i');
            if (icon) {
                icon.style.transform = 'scale(1.2)';
                icon.style.transition = 'transform 0.3s ease';
            }
        });
        
        card.addEventListener('mouseleave', () => {
            const icon = card.querySelector('.model-logo i');
            if (icon) {
                icon.style.transform = 'scale(1)';
            }
        });
        
        card.addEventListener('click', () => {
            const modelName = card.querySelector('.model-name').textContent;
            showModelInfo(modelName);
        });
    });
}

// 显示模型信息
function showModelInfo(modelName) {
    const messages = {
        'DeepSeek': 'DeepSeek 是深度求索公司开发的高性能 AI 模型，在中文理解和代码生成方面表现优异。',
        '硅基流动': '硅基流动是国内优质的 AI 模型服务，提供稳定可靠的 API 接口。',
        '百度千帆': '百度千帆是企业级 AI 服务平台，集成了文心一言等多种模型能力。',
        '阿里通义': '阿里通义是阿里云推出的 AI 模型系列，涵盖文本、图像、语音等多种能力。',
        '豆包': '豆包是字节跳动推出的 AI 助手，在对话和创作方面表现突出。',
        '更多模型': '我们持续接入更多优质 AI 模型，为用户提供更丰富的选择。'
    };
    
    const message = messages[modelName] || `了解更多关于 ${modelName} 的信息`;
    
    // 创建提示框
    const tooltip = document.createElement('div');
    tooltip.className = 'model-tooltip';
    tooltip.innerHTML = `
        <div class="tooltip-content">
            <h4>${modelName}</h4>
            <p>${message}</p>
            <button class="btn btn-primary btn-small">了解更多</button>
        </div>
    `;
    
    // 样式
    tooltip.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        z-index: 10000;
        max-width: 400px;
        text-align: center;
    `;
    
    // 添加到页面
    document.body.appendChild(tooltip);
    
    // 点击关闭
    tooltip.addEventListener('click', (e) => {
        if (e.target === tooltip || e.target.className.includes('btn')) {
            document.body.removeChild(tooltip);
        }
    });
    
    // 3秒后自动关闭
    setTimeout(() => {
        if (document.body.contains(tooltip)) {
            document.body.removeChild(tooltip);
        }
    }, 3000);
}

// 移动端菜单
function initMobileMenu() {
    const menuToggle = document.createElement('button');
    menuToggle.className = 'mobile-menu-toggle';
    menuToggle.innerHTML = '<i class="fas fa-bars"></i>';
    menuToggle.style.cssText = `
        display: none;
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1001;
        background: var(--primary-color);
        color: white;
        border: none;
        width: 48px;
        height: 48px;
        border-radius: 50%;
        font-size: 1.5rem;
        cursor: pointer;
        box-shadow: var(--shadow-lg);
    `;
    
    document.body.appendChild(menuToggle);
    
    // 响应式显示
    function checkMobile() {
        if (window.innerWidth <= 768) {
            menuToggle.style.display = 'flex';
            menuToggle.style.alignItems = 'center';
            menuToggle.style.justifyContent = 'center';
            
            // 隐藏桌面导航
            const navLinks = document.querySelector('.nav-links');
            if (navLinks) {
                navLinks.style.display = 'none';
            }
        } else {
            menuToggle.style.display = 'none';
            
            // 显示桌面导航
            const navLinks = document.querySelector('.nav-links');
            if (navLinks) {
                navLinks.style.display = 'flex';
            }
        }
    }
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    
    // 菜单切换
    menuToggle.addEventListener('click', () => {
        const navLinks = document.querySelector('.nav-links');
        if (navLinks) {
            if (navLinks.style.display === 'flex') {
                navLinks.style.display = 'none';
                menuToggle.innerHTML = '<i class="fas fa-bars"></i>';
            } else {
                navLinks.style.display = 'flex';
                navLinks.style.flexDirection = 'column';
                navLinks.style.position = 'fixed';
                navLinks.style.top = '80px';
                navLinks.style.right = '1rem';
                navLinks.style.background = 'white';
                navLinks.style.padding = '1rem';
                navLinks.style.borderRadius = '0.5rem';
                navLinks.style.boxShadow = 'var(--shadow-xl)';
                navLinks.style.zIndex = '1000';
                menuToggle.innerHTML = '<i class="fas fa-times"></i>';
            }
        }
    });
}

// 显示欢迎消息
function showWelcomeMessage() {
    // 检查是否第一次访问
    if (!localStorage.getItem('ai24x_welcome_shown')) {
        setTimeout(() => {
            const welcomeMsg = document.createElement('div');
            welcomeMsg.className = 'welcome-message';
            welcomeMsg.innerHTML = `
                <div class="welcome-content">
                    <h3>🎉 欢迎使用 AI24X Token 聚合平台！</h3>
                    <p>Token 自由 · 全球 AI 人共创</p>
                    <p>开始您的 AI Token 管理之旅</p>
                    <button class="btn btn-primary" onclick="this.parentElement.parentElement.remove()">
                        开始探索
                    </button>
                </div>
            `;
            
            welcomeMsg.style.cssText = `
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                background: white;
                padding: 1.5rem;
                border-radius: 1rem;
                box-shadow: var(--shadow-xl);
                z-index: 10000;
                max-width: 300px;
                animation: slideIn 0.5s ease-out;
            `;
            
            document.body.appendChild(welcomeMsg);
            
            // 添加动画
            const style = document.createElement('style');
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                
                .welcome-content h3 {
                    color: var(--primary-color);
                    margin-bottom: 0.5rem;
                }
                
                .welcome-content p {
                    color: var(--gray-color);
                    margin-bottom: 0.5rem;
                }
            `;
            document.head.appendChild(style);
            
            // 标记为已显示
            localStorage.setItem('ai24x_welcome_shown', 'true');
            
            // 10秒后自动关闭
            setTimeout(() => {
                if (document.body.contains(welcomeMsg)) {
                    welcomeMsg.remove();
                }
            }, 10000);
        }, 1000);
    }
}

// 平台状态检查
function checkPlatformStatus() {
    // 模拟平台状态检查
    const status = {
        api: 'online',
        database: 'online',
        payment: 'online',
        overall: 'healthy'
    };
    
    console.log('平台状态检查:', status);
    
    // 更新状态指示器
    updateStatusIndicator(status);
}

function updateStatusIndicator(status) {
    // 在控制台显示状态
    const statusText = `🟢 平台状态: ${status.overall === 'healthy' ? '健康' : '异常'}`;
    console.log(`%c${statusText}`, 'color: #10b981; font-weight: bold;');
    
    // 可以在页面上添加状态指示器
    const statusIndicator = document.createElement('div');
    statusIndicator.className = 'status-indicator';
    statusIndicator.innerHTML = `
        <span class="status-dot ${status.overall === 'healthy' ? 'online' : 'offline'}"></span>
        <span class="status-text">平台状态: ${status.overall === 'healthy' ? '正常' : '维护中'}</span>
    `;
    
    statusIndicator.style.cssText = `
        position: fixed;
        bottom: 1rem;
        left: 1rem;
        background: rgba(255, 255, 255, 0.9);
        padding: 0.5rem 1rem;
        border-radius: 2rem;
        font-size: 0.875rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        box-shadow: var(--shadow-md);
        z-index: 9999;
    `;
    
    // 添加到页面
    document.body.appendChild(statusIndicator);
    
    // 状态点样式
    const style = document.createElement('style');
    style.textContent = `
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .status-dot.online {
            background-color: #10b981;
            animation: pulse 2s infinite;
        }
        
        .status-dot.offline {
            background-color: #ef4444;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    `;
    document.head.appendChild(style);
}

// 页面性能监控
function monitorPerformance() {
    // 记录页面加载时间
    window.addEventListener('load', () => {
        const timing = performance.timing;
        const loadTime = timing.loadEventEnd - timing.navigationStart;
        
        console.log(`📊 页面加载时间: ${loadTime}ms`);
        
        if (loadTime > 3000) {
            console.warn('⚠️ 页面加载较慢，建议优化');
        }
    });
}

// 初始化性能监控
monitorPerformance();

// 导出全局函数
window.AI24X = {
    showModelInfo,
    checkPlatformStatus,
    initMobileMenu
};

// 页面完全加载后执行
window.addEventListener('load', () => {
    checkPlatformStatus();
    
    // 添加控制台欢迎信息
    console.log(`
    %c
    ╔══════════════════════════════════════╗
    ║      AI24X Token 聚合平台           ║
    ║      Token 自由 · 全球 AI 人共创     ║
    ║                                      ║
    ║      版本: 1.0.0                     ║
    ║      环境: 开发版                    ║
    ║      状态: 🟢 运行中                 ║
    ╚══════════════════════════════════════╝
    `, 'color: #2563eb; font-weight: bold;');
});