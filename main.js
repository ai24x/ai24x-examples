// AI24X 网站主JavaScript文件

document.addEventListener('DOMContentLoaded', function() {
    console.log('AI24X网站已加载');
    
    // 移动端菜单切换 - 增强版
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mainNav = document.querySelector('.main-nav');
    
    if (mobileMenuBtn && mainNav) {
        mobileMenuBtn.addEventListener('click', function() {
            const isShowing = mainNav.classList.contains('show');
            
            if (isShowing) {
                // 关闭菜单
                mainNav.classList.remove('show');
                this.innerHTML = '<i class="fas fa-bars"></i>';
                this.setAttribute('aria-expanded', 'false');
            } else {
                // 打开菜单
                mainNav.classList.add('show');
                this.innerHTML = '<i class="fas fa-times"></i>';
                this.setAttribute('aria-expanded', 'true');
                
                // 点击菜单外区域关闭
                document.addEventListener('click', function closeMenu(e) {
                    if (!mainNav.contains(e.target) && e.target !== mobileMenuBtn) {
                        mainNav.classList.remove('show');
                        mobileMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
                        mobileMenuBtn.setAttribute('aria-expanded', 'false');
                        document.removeEventListener('click', closeMenu);
                    }
                });
            }
        });
        
        // 菜单链接点击后关闭菜单（移动端）
        const navLinks = mainNav.querySelectorAll('a');
        navLinks.forEach(link => {
            link.addEventListener('click', function() {
                if (window.innerWidth <= 768) {
                    mainNav.classList.remove('show');
                    mobileMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
                    mobileMenuBtn.setAttribute('aria-expanded', 'false');
                }
            });
        });
    }

    // 语言切换功能
    const langToggle = document.getElementById('langToggle');
    const langDropdown = document.getElementById('langDropdown');
    const currentLang = document.getElementById('currentLang');
    const langOptions = document.querySelectorAll('.lang-option');
    
    if (langToggle && langDropdown) {
        // 切换语言下拉菜单
        langToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            const isShowing = langDropdown.classList.contains('show');
            
            if (isShowing) {
                langDropdown.classList.remove('show');
            } else {
                langDropdown.classList.add('show');
                
                // 点击外部关闭
                document.addEventListener('click', function closeLangDropdown(e) {
                    if (!langDropdown.contains(e.target) && e.target !== langToggle) {
                        langDropdown.classList.remove('show');
                        document.removeEventListener('click', closeLangDropdown);
                    }
                });
            }
        });
        
        // 选择语言
        langOptions.forEach(option => {
            option.addEventListener('click', function() {
                const lang = this.getAttribute('data-lang');
                
                // 更新当前语言显示
                if (lang === 'zh') {
                    currentLang.textContent = '中文';
                } else if (lang === 'en') {
                    currentLang.textContent = 'English';
                }
                
                // 更新激活状态
                langOptions.forEach(opt => opt.classList.remove('active'));
                this.classList.add('active');
                
                // 切换网站语言
                switchLanguage(lang);
                
                // 关闭下拉菜单
                langDropdown.classList.remove('show');
            });
        });
        
        // 语言切换函数
        function switchLanguage(lang) {
            console.log(`切换语言到: ${lang}`);
            
            // 这里可以添加实际的语言切换逻辑
            // 例如：发送请求到服务器，或者更新本地存储
            
            // 更新页面文本（示例）
            updatePageText(lang);
            
            // 保存语言偏好
            localStorage.setItem('preferredLanguage', lang);
        }
        
        // 更新页面文本（示例函数）
        function updatePageText(lang) {
            // 这里可以根据语言更新页面上的所有文本
            // 实际项目中应该使用i18n库
            
            if (lang === 'en') {
                // 更新搜索框placeholder
                const searchInput = document.querySelector('.search-box input');
                if (searchInput) searchInput.placeholder = 'Search AI tools...';
                
                // 更新按钮文本
                const loginBtn = document.querySelector('.auth-buttons .btn-outline');
                const signupBtn = document.querySelector('.auth-buttons .btn-primary');
                if (loginBtn) loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
                if (signupBtn) signupBtn.innerHTML = '<i class="fas fa-user-plus"></i> Sign Up';
                
                // 更新导航文本
                const navLinks = document.querySelectorAll('.main-nav a');
                navLinks.forEach((link, index) => {
                    const texts = ['Home', 'AI Tools', 'Categories', 'Rankings'];
                    if (texts[index]) {
                        const icon = link.querySelector('i').outerHTML;
                        link.innerHTML = icon + ' ' + texts[index];
                    }
                });
                
                // 更新英雄区域
                const heroTitle = document.querySelector('.hero h1');
                const heroDesc = document.querySelector('.hero p');
                if (heroTitle) heroTitle.textContent = 'AI24X - Next Generation AI Platform';
                if (heroDesc) heroDesc.textContent = 'Discover, compare and use the best AI tools to boost your productivity and creativity';
                
                // 更新功能区域标题
                const featuresTitle = document.querySelector('.features .section-title');
                if (featuresTitle) featuresTitle.textContent = 'Core Features';
                
                // 更新功能卡片
                const featureCards = document.querySelectorAll('.feature-card h3');
                const featureDescs = document.querySelectorAll('.feature-card p');
                const featureTexts = [
                    { title: 'Smart Search', desc: 'Quickly find the AI tools you need with multi-dimensional filtering' },
                    { title: 'Real-time Rankings', desc: 'Popular tool rankings based on user reviews and usage data' },
                    { title: 'Personalized Recommendations', desc: 'Recommend suitable AI tools based on your usage habits' },
                    { title: 'Detailed Tutorials', desc: 'Rich usage tutorials and best practices' }
                ];
                
                featureCards.forEach((card, index) => {
                    if (featureTexts[index]) {
                        card.textContent = featureTexts[index].title;
                    }
                });
                
                featureDescs.forEach((desc, index) => {
                    if (featureTexts[index]) {
                        desc.textContent = featureTexts[index].desc;
                    }
                });
                
                // 更新热门工具标题
                const toolsTitle = document.querySelector('.popular-tools .section-title');
                if (toolsTitle) toolsTitle.textContent = '🔥 Popular AI Tools';
                
            } else {
                // 切换回中文
                const searchInput = document.querySelector('.search-box input');
                if (searchInput) searchInput.placeholder = '搜索AI工具...';
                
                const loginBtn = document.querySelector('.auth-buttons .btn-outline');
                const signupBtn = document.querySelector('.auth-buttons .btn-primary');
                if (loginBtn) loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> 登录';
                if (signupBtn) signupBtn.innerHTML = '<i class="fas fa-user-plus"></i> 注册';
                
                const navLinks = document.querySelectorAll('.main-nav a');
                const texts = ['首页', 'AI工具库', '分类', '热门排行'];
                navLinks.forEach((link, index) => {
                    if (texts[index]) {
                        const icon = link.querySelector('i').outerHTML;
                        link.innerHTML = icon + ' ' + texts[index];
                    }
                });
                
                const heroTitle = document.querySelector('.hero h1');
                const heroDesc = document.querySelector('.hero p');
                if (heroTitle) heroTitle.textContent = 'AI24X - 下一代AI平台';
                if (heroDesc) heroDesc.textContent = '发现、比较和使用最佳的AI工具，提升您的生产力和创造力';
                
                const featuresTitle = document.querySelector('.features .section-title');
                if (featuresTitle) featuresTitle.textContent = '核心功能';
                
                const featureCards = document.querySelectorAll('.feature-card h3');
                const featureDescs = document.querySelectorAll('.feature-card p');
                const featureTexts = [
                    { title: '智能搜索', desc: '快速找到您需要的AI工具，支持多维度筛选' },
                    { title: '实时排行', desc: '基于用户评价和使用数据的热门工具排行' },
                    { title: '个性推荐', desc: '根据您的使用习惯推荐合适的AI工具' },
                    { title: '详细教程', desc: '提供丰富的使用教程和最佳实践' }
                ];
                
                featureCards.forEach((card, index) => {
                    if (featureTexts[index]) {
                        card.textContent = featureTexts[index].title;
                    }
                });
                
                featureDescs.forEach((desc, index) => {
                    if (featureTexts[index]) {
                        desc.textContent = featureTexts[index].desc;
                    }
                });
                
                const toolsTitle = document.querySelector('.popular-tools .section-title');
                if (toolsTitle) toolsTitle.textContent = '🔥 热门AI工具';
            }
        }
        
        // 初始化语言
        const savedLang = localStorage.getItem('preferredLanguage') || 'zh';
        if (savedLang === 'en') {
            const enOption = document.querySelector('.lang-option[data-lang="en"]');
            if (enOption) {
                enOption.click();
            }
        }
    }
    
    // 搜索功能
    const searchBox = document.querySelector('.search-box input');
    const searchBtn = document.querySelector('.search-btn');
    
    if (searchBox && searchBtn) {
        searchBtn.addEventListener('click', function() {
            performSearch(searchBox.value);
        });
        
        searchBox.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch(this.value);
            }
        });
    }
    
    // 工具卡片悬停效果
    const toolCards = document.querySelectorAll('.tool-card');
    toolCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // 导航链接激活状态
    const navLinks = document.querySelectorAll('.main-nav a');
    const currentPath = window.location.pathname;
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
    
    // 加载动画
    const loadingElements = document.querySelectorAll('.loading');
    loadingElements.forEach(element => {
        setTimeout(() => {
            element.style.display = 'none';
        }, 1000);
    });
    
    // 表单验证
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });
    
    // 社交分享
    const shareButtons = document.querySelectorAll('.share-btn');
    shareButtons.forEach(button => {
        button.addEventListener('click', function() {
            const url = window.location.href;
            const title = document.title;
            shareContent(url, title);
        });
    });
});

// 搜索函数
function performSearch(query) {
    if (!query.trim()) {
        alert('请输入搜索关键词');
        return;
    }
    
    console.log('搜索:', query);
    // 实际项目中这里应该发送AJAX请求
    window.location.href = `/search?q=${encodeURIComponent(query)}`;
}

// 表单验证
function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            field.style.borderColor = '#ff4444';
            
            // 显示错误信息
            let errorMsg = field.nextElementSibling;
            if (!errorMsg || !errorMsg.classList.contains('error-message')) {
                errorMsg = document.createElement('div');
                errorMsg.className = 'error-message';
                errorMsg.style.color = '#ff4444';
                errorMsg.style.fontSize = '12px';
                errorMsg.style.marginTop = '5px';
                errorMsg.textContent = '此字段为必填项';
                field.parentNode.appendChild(errorMsg);
            }
        } else {
            field.style.borderColor = '';
            const errorMsg = field.nextElementSibling;
            if (errorMsg && errorMsg.classList.contains('error-message')) {
                errorMsg.remove();
            }
        }
    });
    
    return isValid;
}

// 分享功能
function shareContent(url, title) {
    if (navigator.share) {
        // 使用Web Share API
        navigator.share({
            title: title,
            url: url
        }).catch(error => {
            console.log('分享失败:', error);
        });
    } else {
        // 回退方案：复制到剪贴板
        navigator.clipboard.writeText(url).then(() => {
            alert('链接已复制到剪贴板！');
        }).catch(err => {
            console.log('复制失败:', err);
        });
    }
}

// 工具分类过滤
function filterTools(category) {
    const tools = document.querySelectorAll('.tool-card');
    const categoryButtons = document.querySelectorAll('.category-btn');
    
    // 更新按钮状态
    categoryButtons.forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.category === category) {
            btn.classList.add('active');
        }
    });
    
    // 过滤工具
    tools.forEach(tool => {
        if (category === 'all' || tool.dataset.category === category) {
            tool.style.display = 'block';
        } else {
            tool.style.display = 'none';
        }
    });
}

// 滚动到顶部
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// 显示消息提示
function showMessage(type, message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `alert alert-${type}`;
    messageDiv.textContent = message;
    
    document.body.prepend(messageDiv);
    
    setTimeout(() => {
        messageDiv.remove();
    }, 5000);
}

// 页面加载进度
window.addEventListener('load', function() {
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = '100%';
        setTimeout(() => {
            progressBar.style.opacity = '0';
            setTimeout(() => {
                progressBar.remove();
            }, 300);
        }, 300);
    }
    
    // 显示页面加载完成
    console.log('页面完全加载完成');
});

// 响应式调整
window.addEventListener('resize', function() {
    const mainNav = document.querySelector('.main-nav');
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    
    if (window.innerWidth > 768 && mainNav && mainNav.classList.contains('show')) {
        mainNav.classList.remove('show');
        if (mobileMenuBtn) {
            mobileMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        }
    }
});