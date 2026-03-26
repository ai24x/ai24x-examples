/**
 * AI24X登录页面增强验证脚本
 * 版本: 1.0.0
 * 创建时间: 2026-03-15
 * 功能: 增强登录验证、记住我功能、用户体验优化
 */

document.addEventListener('DOMContentLoaded', function() {
    // 表单元素
    const loginForm = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const rememberMeCheckbox = document.getElementById('rememberMe');
    const forgotPasswordLink = document.querySelector('.forgot-password');
    
    // 错误信息元素
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');
    const successMessage = document.getElementById('successMessage');
    const welcomeMessage = document.getElementById('welcomeMessage');
    
    // 登录按钮
    const submitButton = loginForm.querySelector('.auth-button');
    
    // 初始化
    initLoginForm();
    
    /**
     * 初始化登录表单
     */
    function initLoginForm() {
        // 检查URL参数，显示注册成功消息
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('registered') === 'true') {
            const username = urlParams.get('username') || '新用户';
            if (welcomeMessage) {
                welcomeMessage.innerHTML = `
                    <i class="fas fa-check-circle"></i>
                    <span>欢迎 ${username}！注册成功，请登录您的账户。</span>
                `;
                welcomeMessage.style.display = 'block';
                
                // 自动填充邮箱（如果从注册页面跳转）
                const registeredEmail = localStorage.getItem('ai24x_registration_pending');
                if (registeredEmail) {
                    try {
                        const userData = JSON.parse(registeredEmail);
                        emailInput.value = userData.email;
                    } catch (e) {
                        console.log('无法解析注册数据');
                    }
                }
            }
        }
        
        // 加载记住我的设置
        loadRememberMeSettings();
        
        // 实时验证邮箱
        emailInput.addEventListener('input', function() {
            validateEmailRealTime(this.value.trim());
            updateSubmitButtonState();
        });
        
        // 实时验证密码
        passwordInput.addEventListener('input', function() {
            validatePasswordRealTime(this.value);
            updateSubmitButtonState();
        });
        
        // 记住我状态变化
        rememberMeCheckbox.addEventListener('change', function() {
            updateSubmitButtonState();
        });
        
        // 表单提交
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (validateForm()) {
                submitLogin();
            }
        });
        
        // 忘记密码功能
        if (forgotPasswordLink) {
            forgotPasswordLink.addEventListener('click', function(e) {
                e.preventDefault();
                showForgotPasswordModal();
            });
        }
        
        // 初始状态
        updateSubmitButtonState();
    }
    
    /**
     * 加载记住我的设置
     */
    function loadRememberMeSettings() {
        const rememberMe = localStorage.getItem('ai24x_remember_me');
        const savedEmail = localStorage.getItem('ai24x_saved_email');
        
        if (rememberMe === 'true' && savedEmail) {
            rememberMeCheckbox.checked = true;
            emailInput.value = savedEmail;
            passwordInput.focus(); // 密码框获取焦点
        }
    }
    
    /**
     * 实时验证邮箱
     */
    function validateEmailRealTime(email) {
        if (!email) {
            showError(emailError, '邮箱不能为空');
            return false;
        }
        
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!regex.test(email)) {
            showError(emailError, '请输入有效的邮箱地址');
            return false;
        }
        
        clearError(emailError);
        return true;
    }
    
    /**
     * 实时验证密码
     */
    function validatePasswordRealTime(password) {
        if (!password) {
            showError(passwordError, '密码不能为空');
            return false;
        }
        
        if (password.length < 6) {
            showError(passwordError, '密码至少需要6个字符');
            return false;
        }
        
        clearError(passwordError);
        return true;
    }
    
    /**
     * 验证整个表单
     */
    function validateForm() {
        const emailValid = validateEmailRealTime(emailInput.value.trim());
        const passwordValid = validatePasswordRealTime(passwordInput.value);
        
        return emailValid && passwordValid;
    }
    
    /**
     * 更新提交按钮状态
     */
    function updateSubmitButtonState() {
        if (!submitButton) return;
        
        const email = emailInput.value.trim();
        const password = passwordInput.value;
        
        const isFormValid = email && password;
        
        if (isFormValid) {
            submitButton.disabled = false;
            submitButton.style.opacity = '1';
            submitButton.style.cursor = 'pointer';
        } else {
            submitButton.disabled = true;
            submitButton.style.opacity = '0.6';
            submitButton.style.cursor = 'not-allowed';
        }
    }
    
    /**
     * 提交登录
     */
    function submitLogin() {
        if (!validateForm()) return;
        
        // 禁用提交按钮
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 登录中...';
        
        // 收集表单数据
        const formData = {
            email: emailInput.value.trim(),
            password: passwordInput.value,
            rememberMe: rememberMeCheckbox.checked,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent
        };
        
        // 显示成功消息
        successMessage.style.display = 'block';
        successMessage.innerHTML = `
            <i class="fas fa-spinner fa-spin"></i>
            <span>正在验证您的账户信息...</span>
        `;
        
        // 保存记住我设置
        if (formData.rememberMe) {
            localStorage.setItem('ai24x_remember_me', 'true');
            localStorage.setItem('ai24x_saved_email', formData.email);
        } else {
            localStorage.removeItem('ai24x_remember_me');
            localStorage.removeItem('ai24x_saved_email');
        }
        
        // 模拟API调用（实际项目中替换为真实API）
        setTimeout(() => {
            console.log('登录信息提交:', {
                email: formData.email,
                rememberMe: formData.rememberMe,
                timestamp: formData.timestamp
            });
            
            // 模拟成功响应
            successMessage.innerHTML = `
                <i class="fas fa-check-circle"></i>
                <span>登录成功！3秒后跳转到首页...</span>
            `;
            
            // 保存登录状态
            localStorage.setItem('ai24x_logged_in', 'true');
            localStorage.setItem('ai24x_user_email', formData.email);
            localStorage.setItem('ai24x_last_login', new Date().toISOString());
            
            // 清除注册待处理数据
            localStorage.removeItem('ai24x_registration_pending');
            
            // 3秒后跳转到用户中心
            setTimeout(() => {
                window.location.href = '/user-center?logged_in=true&email=' + encodeURIComponent(formData.email);
            }, 3000);
            
        }, 2000);
    }
    
    /**
     * 显示忘记密码模态框
     */
    function showForgotPasswordModal() {
        // 创建模态框
        const modal = document.createElement('div');
        modal.className = 'forgot-password-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3><i class="fas fa-key"></i> 重置密码</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <p>请输入您的邮箱地址，我们将发送重置密码的链接。</p>
                    <div class="form-group">
                        <input type="email" id="resetEmail" class="form-input" placeholder="输入您的邮箱地址">
                        <div class="error-message" id="resetEmailError"></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-outline modal-cancel">取消</button>
                    <button class="btn btn-primary modal-submit">发送重置链接</button>
                </div>
            </div>
        `;
        
        // 添加样式
        const style = document.createElement('style');
        style.textContent = `
            .forgot-password-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(5px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
                animation: fadeIn 0.3s ease;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            .modal-content {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 212, 255, 0.1);
                border-radius: 16px;
                padding: 25px;
                width: 90%;
                max-width: 400px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                animation: slideUp 0.3s ease;
            }
            
            @keyframes slideUp {
                from { transform: translateY(20px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }
            
            .modal-header h3 {
                color: #fff;
                font-size: 20px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .modal-close {
                background: none;
                border: none;
                color: rgba(255, 255, 255, 0.6);
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                transition: all 0.3s ease;
            }
            
            .modal-close:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #fff;
            }
            
            .modal-body {
                margin-bottom: 25px;
            }
            
            .modal-body p {
                color: rgba(255, 255, 255, 0.7);
                font-size: 14px;
                margin-bottom: 20px;
                line-height: 1.5;
            }
            
            .modal-footer {
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            }
        `;
        
        document.head.appendChild(style);
        document.body.appendChild(modal);
        
        // 模态框功能
        const closeBtn = modal.querySelector('.modal-close');
        const cancelBtn = modal.querySelector('.modal-cancel');
        const submitBtn = modal.querySelector('.modal-submit');
        const resetEmailInput = modal.querySelector('#resetEmail');
        const resetEmailError = modal.querySelector('#resetEmailError');
        
        // 关闭模态框
        function closeModal() {
            modal.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(modal);
                document.head.removeChild(style);
            }, 300);
        }
        
        // 添加关闭动画
        const closeStyle = document.createElement('style');
        closeStyle.textContent = `
            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
        `;
        document.head.appendChild(closeStyle);
        
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        
        // 点击背景关闭
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        // 提交重置请求
        submitBtn.addEventListener('click', function() {
            const email = resetEmailInput.value.trim();
            
            if (!email) {
                showError(resetEmailError, '请输入邮箱地址');
                return;
            }
            
            const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!regex.test(email)) {
                showError(resetEmailError, '请输入有效的邮箱地址');
                return;
            }
            
            clearError(resetEmailError);
            
            // 模拟发送重置链接
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 发送中...';
            
            setTimeout(() => {
                submitBtn.innerHTML = '<i class="fas fa-check"></i> 已发送';
                submitBtn.style.background = '#2ed573';
                
                setTimeout(() => {
                    closeModal();
                    alert('重置密码链接已发送到您的邮箱，请查收。');
                }, 1000);
            }, 1500);
        });
        
        // 回车键提交
        resetEmailInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                submitBtn.click();
            }
        });
        
        // 自动聚焦
        setTimeout(() => {
            resetEmailInput.focus();
        }, 100);
    }
    
    /**
     * 显示错误信息
     */
    function showError(element, message) {
        if (!element) return;
        element.textContent = message;
        element.style.display = 'block';
        element.style.animation = 'shake 0.5s ease-in-out';
        
        setTimeout(() => {
            element.style.animation = '';
        }, 500);
    }
    
    /**
     * 清除错误信息
     */
    function clearError(element) {
        if (!element) return;
        element.style.display = 'none';
    }
    
    // 添加CSS动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
            20%, 40%, 60%, 80% { transform: translateX(5px); }
        }
    `;
    document.head.appendChild(style);
});