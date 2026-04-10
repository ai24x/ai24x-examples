// 认证相关功能 - 登录/注册

document.addEventListener('DOMContentLoaded', function() {
    console.log('认证模块已加载');
    
    // 初始化认证功能
    initLoginForm();
    initPasswordToggle();
    initSocialLogin();
    initFormValidation();
    
    // 检查URL参数
    checkUrlParams();
});

// 初始化登录表单
function initLoginForm() {
    const loginForm = document.getElementById('loginForm');
    if (!loginForm) return;
    
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // 验证表单
        if (!validateLoginForm()) {
            return;
        }
        
        // 获取表单数据
        const formData = {
            email: document.getElementById('email').value.trim(),
            password: document.getElementById('password').value,
            remember: document.getElementById('remember').checked
        };
        
        // 显示加载状态
        const loginBtn = document.getElementById('loginBtn');
        const originalText = loginBtn.innerHTML;
        loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 登录中...';
        loginBtn.disabled = true;
        
        try {
            // 模拟API调用
            const response = await simulateLogin(formData);
            
            if (response.success) {
                // 登录成功
                showSuccessMessage('登录成功！正在跳转到控制台...');
                
                // 保存登录状态
                saveLoginState(formData, response);
                
                // 3秒后跳转
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, 2000);
            } else {
                // 登录失败
                showErrorMessage(response.message || '登录失败，请检查邮箱和密码');
                loginBtn.innerHTML = originalText;
                loginBtn.disabled = false;
            }
        } catch (error) {
            console.error('登录错误:', error);
            showErrorMessage('网络错误，请稍后重试');
            loginBtn.innerHTML = originalText;
            loginBtn.disabled = false;
        }
    });
}

// 模拟登录API
function simulateLogin(formData) {
    return new Promise((resolve) => {
        setTimeout(() => {
            // 模拟验证逻辑
            const testAccounts = [
                { email: 'admin@ai24x.com', password: 'admin123' },
                { email: 'user@example.com', password: 'password123' },
                { email: 'test@ai24x.com', password: 'test123' }
            ];
            
            const isValid = testAccounts.some(account => 
                account.email === formData.email && account.password === formData.password
            );
            
            if (isValid) {
                resolve({
                    success: true,
                    message: '登录成功',
                    user: {
                        id: 'user_' + Date.now(),
                        email: formData.email,
                        name: formData.email.split('@')[0],
                        avatar: 'https://ui-avatars.com/api/?name=' + encodeURIComponent(formData.email.split('@')[0]),
                        token: 'mock_jwt_token_' + Date.now(),
                        expiresIn: 3600
                    }
                });
            } else {
                resolve({
                    success: false,
                    message: '邮箱或密码错误'
                });
            }
        }, 1500); // 模拟网络延迟
    });
}

// 验证登录表单
function validateLoginForm() {
    let isValid = true;
    
    // 验证邮箱
    const email = document.getElementById('email').value.trim();
    const emailError = document.getElementById('emailError');
    
    if (!email) {
        emailError.textContent = '请输入邮箱地址';
        isValid = false;
    } else if (!isValidEmail(email)) {
        emailError.textContent = '请输入有效的邮箱地址';
        isValid = false;
    } else {
        emailError.textContent = '';
    }
    
    // 验证密码
    const password = document.getElementById('password').value;
    const passwordError = document.getElementById('passwordError');
    
    if (!password) {
        passwordError.textContent = '请输入密码';
        isValid = false;
    } else if (password.length < 6) {
        passwordError.textContent = '密码至少6位字符';
        isValid = false;
    } else {
        passwordError.textContent = '';
    }
    
    return isValid;
}

// 邮箱验证
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// 密码显示/隐藏切换
function initPasswordToggle() {
    const toggleBtn = document.getElementById('togglePassword');
    if (!toggleBtn) return;
    
    const passwordInput = document.getElementById('password');
    
    toggleBtn.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        
        // 切换图标
        const icon = this.querySelector('i');
        if (type === 'text') {
            icon.className = 'fas fa-eye-slash';
            this.setAttribute('aria-label', '隐藏密码');
        } else {
            icon.className = 'fas fa-eye';
            this.setAttribute('aria-label', '显示密码');
        }
    });
}

// 社交登录
function initSocialLogin() {
    // GitHub 登录
    const githubBtn = document.querySelector('.btn-github');
    if (githubBtn) {
        githubBtn.addEventListener('click', function() {
            showInfoMessage('GitHub 登录功能开发中...');
            // 实际实现时跳转到 GitHub OAuth
            // window.location.href = 'https://github.com/login/oauth/authorize?client_id=YOUR_CLIENT_ID';
        });
    }
    
    // Google 登录
    const googleBtn = document.querySelector('.btn-google');
    if (googleBtn) {
        googleBtn.addEventListener('click', function() {
            showInfoMessage('Google 登录功能开发中...');
            // 实际实现时跳转到 Google OAuth
            // window.location.href = 'https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_CLIENT_ID';
        });
    }
}

// 表单验证初始化
function initFormValidation() {
    // 实时验证邮箱
    const emailInput = document.getElementById('email');
    if (emailInput) {
        emailInput.addEventListener('blur', function() {
            const email = this.value.trim();
            const errorElement = document.getElementById('emailError');
            
            if (!email) {
                errorElement.textContent = '';
            } else if (!isValidEmail(email)) {
                errorElement.textContent = '请输入有效的邮箱地址';
                this.classList.add('form-error-animation');
                setTimeout(() => this.classList.remove('form-error-animation'), 500);
            } else {
                errorElement.textContent = '';
            }
        });
    }
    
    // 实时验证密码
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
        passwordInput.addEventListener('input', function() {
            const password = this.value;
            const errorElement = document.getElementById('passwordError');
            
            if (password.length > 0 && password.length < 6) {
                errorElement.textContent = '密码至少6位字符';
            } else {
                errorElement.textContent = '';
            }
        });
    }
}

// 保存登录状态
function saveLoginState(formData, response) {
    const loginData = {
        user: response.user,
        timestamp: Date.now(),
        remember: formData.remember
    };
    
    if (formData.remember) {
        // 长期存储
        localStorage.setItem('ai24x_auth', JSON.stringify(loginData));
    } else {
        // 会话存储
        sessionStorage.setItem('ai24x_auth', JSON.stringify(loginData));
    }
    
    // 设置Cookie（用于服务器端识别）
    document.cookie = `ai24x_token=${response.user.token}; path=/; max-age=${response.user.expiresIn}`;
}

// 检查URL参数
function checkUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);
    
    // 检查注册成功参数
    if (urlParams.get('registered') === 'true') {
        showSuccessMessage('注册成功！请使用您的邮箱和密码登录。');
        
        // 自动填充邮箱
        const email = urlParams.get('email');
        if (email && document.getElementById('email')) {
            document.getElementById('email').value = email;
        }
        
        // 清理URL参数
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // 检查密码重置参数
    if (urlParams.get('reset') === 'success') {
        showSuccessMessage('密码重置成功！请使用新密码登录。');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // 检查错误参数
    const error = urlParams.get('error');
    if (error) {
        showErrorMessage(decodeURIComponent(error));
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

// 显示成功消息
function showSuccessMessage(message) {
    showMessage(message, 'success');
}

// 显示错误消息
function showErrorMessage(message) {
    showMessage(message, 'error');
}

// 显示信息消息
function showInfoMessage(message) {
    showMessage(message, 'info');
}

// 显示消息
function showMessage(message, type = 'info') {
    // 移除现有消息
    const existingMsg = document.querySelector('.auth-message');
    if (existingMsg) {
        existingMsg.remove();
    }
    
    // 创建消息元素
    const messageDiv = document.createElement('div');
    messageDiv.className = `auth-message auth-message-${type}`;
    messageDiv.innerHTML = `
        <div class="message-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            <button class="message-close"><i class="fas fa-times"></i></button>
        </div>
    `;
    
    // 样式
    messageDiv.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-lg);
        z-index: 10000;
        animation: slideInRight 0.3s ease-out;
        max-width: 400px;
    `;
    
    // 添加到页面
    document.body.appendChild(messageDiv);
    
    // 关闭按钮
    const closeBtn = messageDiv.querySelector('.message-close');
    closeBtn.addEventListener('click', () => {
        messageDiv.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => messageDiv.remove(), 300);
    });
    
    // 自动关闭
    setTimeout(() => {
        if (document.body.contains(messageDiv)) {
            messageDiv.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => messageDiv.remove(), 300);
        }
    }, 5000);
    
    // 添加动画样式
    if (!document.querySelector('#message-animations')) {
        const style = document.createElement('style');
        style.id = 'message-animations';
        style.textContent = `
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            @keyframes slideOutRight {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
            
            .message-content {
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }
            
            .message-content i:first-child {
                font-size: 1.25rem;
            }
            
            .message-close {
                background: none;
                border: none;
                color: white;
                cursor: pointer;
                margin-left: auto;
                padding: 0.25rem;
                opacity: 0.7;
                transition: opacity 0.3s ease;
            }
            
            .message-close:hover {
                opacity: 1;
            }
        `;
        document.head.appendChild(style);
    }
}

// 检查登录状态
function checkAuthStatus() {
    const authData = localStorage.getItem('ai24x_auth') || sessionStorage.getItem('ai24x_auth');
    
    if (authData) {
        try {
            const data = JSON.parse(authData);
            const now = Date.now();
            const tokenAge = now - data.timestamp;
            
            // 检查token是否过期（默认24小时）
            const maxAge = 24 * 60 * 60 * 1000; // 24小时
            if (tokenAge < maxAge) {
                return data.user;
            } else {
                // Token过期，清除
                localStorage.removeItem('ai24x_auth');
                sessionStorage.removeItem('ai24x_auth');
                document.cookie = 'ai24x_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
            }
        } catch (error) {
            console.error('解析认证数据失败:', error);
        }
    }
    
    return null;
}

// 登出
function logout() {
    localStorage.removeItem('ai24x_auth');
    sessionStorage.removeItem('ai24x_auth');
    document.cookie = 'ai24x_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    
    // 跳转到登录页
    window.location.href = 'login.html';
}

// 导出全局函数
window.Auth = {
    checkAuthStatus,
    logout,
    showSuccessMessage,
    showErrorMessage,
    showInfoMessage
};

// 页面加载时检查认证状态
window.addEventListener('load', () => {
    const user = checkAuthStatus();
    if (user && window.location.pathname.includes('login.html')) {
        // 如果已登录且当前在登录页，跳转到控制台
        window.location.href = 'dashboard.html';
    }
});