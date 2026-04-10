/**
 * AI24X注册页面增强验证脚本
 * 版本: 1.0.0
 * 创建时间: 2026-03-15
 * 功能: 增强表单验证、实时反馈、用户体验优化
 */

document.addEventListener('DOMContentLoaded', function() {
    // 表单元素
    const signupForm = document.getElementById('signupForm');
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const termsCheckbox = document.getElementById('terms');
    
    // 错误信息元素
    const usernameError = document.getElementById('usernameError');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');
    const confirmPasswordError = document.getElementById('confirmPasswordError');
    const successMessage = document.getElementById('successMessage');
    
    // 密码强度指示器
    const passwordStrength = document.getElementById('passwordStrength');
    const strengthText = document.getElementById('strengthText');
    
    // 注册按钮
    const submitButton = document.querySelector('.auth-card .btn-primary');
    
    // 初始化
    initFormValidation();
    
    /**
     * 初始化表单验证
     */
    function initFormValidation() {
        // 实时验证用户名
        usernameInput.addEventListener('input', function() {
            validateUsernameRealTime(this.value.trim());
            updateSubmitButtonState();
        });
        
        // 实时验证邮箱
        emailInput.addEventListener('input', function() {
            validateEmailRealTime(this.value.trim());
            updateSubmitButtonState();
        });
        
        // 实时验证密码
        passwordInput.addEventListener('input', function() {
            validatePasswordRealTime(this.value);
            validateConfirmPasswordRealTime();
            updateSubmitButtonState();
        });
        
        // 实时验证确认密码
        confirmPasswordInput.addEventListener('input', function() {
            validateConfirmPasswordRealTime();
            updateSubmitButtonState();
        });
        
        // 条款勾选状态变化
        termsCheckbox.addEventListener('change', function() {
            updateSubmitButtonState();
        });
        
        // 表单提交
        signupForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (validateForm()) {
                submitRegistration();
            }
        });
        
        // 初始状态
        updateSubmitButtonState();
    }
    
    /**
     * 实时验证用户名
     */
    function validateUsernameRealTime(username) {
        if (!username) {
            showError(usernameError, '用户名不能为空');
            return false;
        }
        
        if (username.length < 3) {
            showError(usernameError, '用户名至少3个字符');
            return false;
        }
        
        if (username.length > 20) {
            showError(usernameError, '用户名不能超过20个字符');
            return false;
        }
        
        const regex = /^[a-zA-Z0-9_]+$/;
        if (!regex.test(username)) {
            showError(usernameError, '只能包含字母、数字和下划线');
            return false;
        }
        
        // 检查是否包含保留字
        const reservedWords = ['admin', 'root', 'system', 'administrator', 'moderator'];
        if (reservedWords.includes(username.toLowerCase())) {
            showError(usernameError, '该用户名不可用');
            return false;
        }
        
        clearError(usernameError);
        return true;
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
        
        // 检查常见邮箱服务商
        const commonDomains = ['gmail.com', 'qq.com', '163.com', '126.com', 'outlook.com', 'hotmail.com', 'yahoo.com'];
        const domain = email.split('@')[1];
        if (!commonDomains.includes(domain.toLowerCase())) {
            // 非常见域名，额外验证格式
            const domainRegex = /^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            if (!domainRegex.test(domain)) {
                showError(emailError, '邮箱域名格式不正确');
                return false;
            }
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
            updatePasswordStrength(0);
            return false;
        }
        
        if (password.length < 8) {
            showError(passwordError, '密码至少8个字符');
            updatePasswordStrength(1);
            return false;
        }
        
        // 密码强度计算
        let strength = 0;
        
        // 长度加分
        if (password.length >= 8) strength += 1;
        if (password.length >= 12) strength += 1;
        
        // 包含小写字母
        if (/[a-z]/.test(password)) strength += 1;
        
        // 包含大写字母
        if (/[A-Z]/.test(password)) strength += 1;
        
        // 包含数字
        if (/\d/.test(password)) strength += 1;
        
        // 包含特殊字符
        if (/[@$!%*#?&]/.test(password)) strength += 1;
        
        // 更新密码强度显示
        updatePasswordStrength(strength);
        
        // 验证通过
        if (strength >= 4) {
            clearError(passwordError);
            return true;
        } else {
            showError(passwordError, '密码强度不足，建议包含大小写字母、数字和特殊字符');
            return false;
        }
    }
    
    /**
     * 更新密码强度显示
     */
    function updatePasswordStrength(strength) {
        if (!passwordStrength || !strengthText) return;
        
        const strengthLevels = [
            { text: '非常弱', color: '#ff4757', width: '20%' },
            { text: '弱', color: '#ffa502', width: '40%' },
            { text: '一般', color: '#ffd32a', width: '60%' },
            { text: '强', color: '#2ed573', width: '80%' },
            { text: '非常强', color: '#00d4ff', width: '100%' }
        ];
        
        const level = Math.min(strength, 4);
        passwordStrength.style.width = strengthLevels[level].width;
        passwordStrength.style.backgroundColor = strengthLevels[level].color;
        strengthText.textContent = strengthLevels[level].text;
        strengthText.style.color = strengthLevels[level].color;
    }
    
    /**
     * 实时验证确认密码
     */
    function validateConfirmPasswordRealTime() {
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        
        if (!confirmPassword) {
            showError(confirmPasswordError, '请确认密码');
            return false;
        }
        
        if (password !== confirmPassword) {
            showError(confirmPasswordError, '两次输入的密码不一致');
            return false;
        }
        
        clearError(confirmPasswordError);
        return true;
    }
    
    /**
     * 验证整个表单
     */
    function validateForm() {
        const usernameValid = validateUsernameRealTime(usernameInput.value.trim());
        const emailValid = validateEmailRealTime(emailInput.value.trim());
        const passwordValid = validatePasswordRealTime(passwordInput.value);
        const confirmPasswordValid = validateConfirmPasswordRealTime();
        const termsAccepted = termsCheckbox.checked;
        
        if (!termsAccepted) {
            alert('请阅读并同意服务条款和隐私政策');
            return false;
        }
        
        return usernameValid && emailValid && passwordValid && confirmPasswordValid && termsAccepted;
    }
    
    /**
     * 更新提交按钮状态
     */
    function updateSubmitButtonState() {
        if (!submitButton) return;
        
        const username = usernameInput.value.trim();
        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        const termsAccepted = termsCheckbox.checked;
        
        const isFormValid = username && email && password && confirmPassword && termsAccepted;
        
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
     * 提交注册
     */
    function submitRegistration() {
        if (!validateForm()) return;
        
        // 禁用提交按钮
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 注册中...';
        
        // 收集表单数据
        const formData = {
            username: usernameInput.value.trim(),
            email: emailInput.value.trim(),
            password: passwordInput.value,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent
        };
        
        // 显示成功消息
        successMessage.style.display = 'block';
        successMessage.innerHTML = `
            <i class="fas fa-check-circle"></i>
            <span>注册成功！正在为您创建账户...</span>
        `;
        
        // 模拟API调用（实际项目中替换为真实API）
        setTimeout(() => {
            console.log('注册信息提交:', formData);
            
            // 模拟成功响应
            successMessage.innerHTML = `
                <i class="fas fa-check-circle"></i>
                <span>账户创建成功！3秒后跳转到登录页面...</span>
            `;
            
            // 保存用户信息到本地存储（模拟）
            localStorage.setItem('ai24x_registration_pending', JSON.stringify({
                username: formData.username,
                email: formData.email,
                registeredAt: new Date().toISOString()
            }));
            
            // 3秒后跳转到用户中心（模拟自动登录）
            setTimeout(() => {
                // 模拟自动登录
                localStorage.setItem('ai24x_logged_in', 'true');
                localStorage.setItem('ai24x_user_email', formData.email);
                localStorage.setItem('ai24x_username', formData.username);
                localStorage.setItem('ai24x_last_login', new Date().toISOString());
                
                // 跳转到用户中心
                window.location.href = '/user-center?registered=true&username=' + encodeURIComponent(formData.username);
            }, 3000);
            
        }, 2000);
    }
    
    /**
     * 显示错误信息
     */
    function showError(element, message) {
        if (!element) return;
        element.textContent = message;
        element.style.display = 'block';
        element.style.animation = 'shake 0.5s ease-in-out';
        
        // 添加抖动动画
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
        
        .password-strength-container {
            margin-top: 8px;
            margin-bottom: 16px;
        }
        
        .password-strength-bar {
            height: 4px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 2px;
            overflow: hidden;
            margin-bottom: 4px;
        }
        
        .password-strength-fill {
            height: 100%;
            width: 0%;
            transition: width 0.3s ease, background-color 0.3s ease;
            border-radius: 2px;
        }
        
        .password-strength-text {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
            text-align: right;
        }
    `;
    document.head.appendChild(style);
});