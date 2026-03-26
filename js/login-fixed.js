/**
 * AI24X登录功能修复版
 * 版本: 2.0.0
 * 功能: 完整的用户登录、验证、跳转功能
 */

document.addEventListener('DOMContentLoaded', function() {
    // 表单元素
    const loginForm = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const rememberCheckbox = document.getElementById('rememberMe');
    
    // 错误信息元素
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');
    const successMessage = document.getElementById('successMessage');
    const welcomeMessage = document.getElementById('welcomeMessage');
    
    // 登录按钮
    const submitButton = document.querySelector('.auth-button[type="submit"]') || 
                         document.querySelector('.auth-card .btn-primary') ||
                         document.querySelector('button[type="submit"]');
    
    // 检查URL参数，显示注册成功消息
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('registered') === 'true' && welcomeMessage) {
        welcomeMessage.style.display = 'block';
        welcomeMessage.textContent = '注册成功！请使用您的账户登录。';
    }
    
    // 初始化
    if (loginForm) {
        setupFormSubmit();
        checkRememberedUser();
    }
    
    /**
     * 设置表单提交
     */
    function setupFormSubmit() {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitForm();
        });
    }
    
    /**
     * 检查记住的用户
     */
    function checkRememberedUser() {
        const rememberedEmail = localStorage.getItem('ai24x_remembered_email');
        if (rememberedEmail && emailInput) {
            emailInput.value = rememberedEmail;
            if (rememberCheckbox) {
                rememberCheckbox.checked = true;
            }
        }
    }
    
    /**
     * 验证邮箱
     */
    function validateEmail(email) {
        if (!emailError) return true;
        
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        
        if (!email) {
            showError(emailError, '请输入邮箱地址');
            return false;
        }
        
        if (!emailRegex.test(email)) {
            showError(emailError, '请输入有效的邮箱地址');
            return false;
        }
        
        hideError(emailError);
        return true;
    }
    
    /**
     * 验证密码
     */
    function validatePassword(password) {
        if (!passwordError) return true;
        
        if (!password) {
            showError(passwordError, '请输入密码');
            return false;
        }
        
        if (password.length < 6) {
            showError(passwordError, '密码至少需要6个字符');
            return false;
        }
        
        hideError(passwordError);
        return true;
    }
    
    /**
     * 验证所有字段
     */
    function validateAll() {
        const emailValid = validateEmail(emailInput ? emailInput.value.trim() : '');
        const passwordValid = validatePassword(passwordInput ? passwordInput.value : '');
        
        return emailValid && passwordValid;
    }
    
    /**
     * 提交表单 - 实际登录功能
     */
    function submitForm() {
        if (!validateAll()) {
            return false;
        }
        
        // 显示加载状态
        if (submitButton) {
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 登录中...';
            submitButton.disabled = true;
        }
        
        // 收集登录数据
        const loginData = {
            email: emailInput.value.trim(),
            password: btoa(passwordInput.value), // 简单编码，与注册时一致
            remember: rememberCheckbox ? rememberCheckbox.checked : false
        };
        
        // 验证用户
        try {
            // 从localStorage获取用户数据
            const existingUsers = JSON.parse(localStorage.getItem('ai24x_users') || '[]');
            const user = existingUsers.find(u => u.email === loginData.email && u.password === loginData.password);
            
            if (!user) {
                // 模拟延迟
                setTimeout(() => {
                    showError(passwordError, '邮箱或密码错误，请重试');
                    resetSubmitButton();
                }, 1000);
                return false;
            }
            
            // 保存登录状态
            localStorage.setItem('ai24x_logged_in', 'true');
            localStorage.setItem('ai24x_username', user.username);
            localStorage.setItem('ai24x_email', user.email);
            localStorage.setItem('ai24x_user_id', user.id);
            
            // 记住用户
            if (loginData.remember) {
                localStorage.setItem('ai24x_remembered_email', user.email);
            } else {
                localStorage.removeItem('ai24x_remembered_email');
            }
            
            // 显示成功消息
            if (successMessage) {
                successMessage.textContent = '登录成功！正在跳转到用户中心...';
                successMessage.style.color = '#2ed573';
                successMessage.style.display = 'block';
            }
            
            // 2秒后跳转到用户中心
            setTimeout(function() {
                // 检查是否有重定向参数
                const redirectTo = urlParams.get('redirect') || '/user-center';
                window.location.href = redirectTo;
            }, 2000);
            
        } catch (error) {
            console.error('登录失败:', error);
            showError(passwordError, '登录失败，请稍后重试');
            resetSubmitButton();
        }
        
        return false;
    }
    
    /**
     * 重置提交按钮状态
     */
    function resetSubmitButton() {
        if (submitButton) {
            submitButton.innerHTML = '<i class="fas fa-sign-in-alt"></i> 登录';
            submitButton.disabled = false;
        }
    }
    
    /**
     * 显示错误消息
     */
    function showError(errorElement, message) {
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
    }
    
    /**
     * 隐藏错误消息
     */
    function hideError(errorElement) {
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    }
    
    /**
     * 密码显示/隐藏切换
     */
    const togglePasswordBtn = document.getElementById('togglePassword');
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', function() {
            const icon = this.querySelector('i');
            
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                icon.className = 'fas fa-eye-slash';
            } else {
                passwordInput.type = 'password';
                icon.className = 'fas fa-eye';
            }
        });
    }
});