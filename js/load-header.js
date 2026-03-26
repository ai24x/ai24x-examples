// 加载统一头部
function loadHeader() {
    const headerContainer = document.querySelector('.header-container');
    if (!headerContainer) return;
    
    fetch('/header.html')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load header');
            }
            return response.text();
        })
        .then(html => {
            headerContainer.innerHTML = html;
            
            // 重新执行头部中的脚本
            const scripts = headerContainer.querySelectorAll('script');
            scripts.forEach(script => {
                const newScript = document.createElement('script');
                if (script.src) {
                    newScript.src = script.src;
                } else {
                    newScript.textContent = script.textContent;
                }
                document.body.appendChild(newScript);
            });
            
            // 加载移动端菜单脚本
            loadMobileMenuScript();
        })
        .catch(error => {
            console.error('Error loading header:', error);
            // 如果加载失败，使用默认头部
            headerContainer.innerHTML = getDefaultHeader();
        });
}

// 获取默认头部（当fetch失败时使用）
function getDefaultHeader() {
    return `
        <header class="header">
            <div class="container">
                <div class="header-content">
                    <div class="logo">
                        <a href="/">
                            <i class="fas fa-robot"></i>
                            <span>AI24X</span>
                        </a>
                    </div>
                    
                    <nav class="main-nav">
                        <ul>
                            <li><a href="/" class="nav-link active"><i class="fas fa-home"></i> <span class="nav-text">首页</span></a></li>
                            <li><a href="/tools" class="nav-link"><i class="fas fa-tools"></i> <span class="nav-text">AI工具库</span></a></li>
                            <li><a href="/rankings" class="nav-link"><i class="fas fa-chart-bar"></i> <span class="nav-text">实时排行</span></a></li>
                            <li><a href="/tutorials" class="nav-link"><i class="fas fa-chart-line"></i> <span class="nav-text">热门教程</span></a></li>
                            <li><a href="/custom" class="nav-link"><i class="fas fa-cogs"></i> <span class="nav-text">定制开发</span></a></li>
                        </ul>
                    </nav>
                    
                    <div class="header-actions">
                        <div class="auth-buttons">
                            <a href="/login" class="btn btn-outline"><i class="fas fa-sign-in-alt"></i> 登录</a>
                            <a href="/signup" class="btn btn-primary"><i class="fas fa-user-plus"></i> 注册</a>
                        </div>
                        <button class="mobile-menu-btn">
                            <i class="fas fa-bars"></i>
                        </button>
                    </div>
                </div>
            </div>
        </header>
    `;
}

// 加载移动端菜单脚本
function loadMobileMenuScript() {
    // 检查是否已经加载了移动端菜单脚本
    if (typeof initMobileMenu === 'function') {
        initMobileMenu();
        return;
    }
    
    // 如果没有加载，则动态加载
    const script = document.createElement('script');
    script.src = '/js/mobile-menu.js';
    script.onload = function() {
        if (typeof initMobileMenu === 'function') {
            initMobileMenu();
        }
    };
    document.body.appendChild(script);
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 如果页面已经有.header-container，则加载头部
    if (document.querySelector('.header-container')) {
        loadHeader();
    }
});