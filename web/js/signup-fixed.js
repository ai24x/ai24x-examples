/**
 * AI24X注册功能修复版
 * 版本: 2.0.0
 * 功能: 完整的用户注册、登录、用户中心功能
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
    
    // 注册按钮
    const submitButton = document.querySelector('.auth-button[type="submit"]') || 
                         document.querySelector('.auth-card .btn-primary') ||
                         document.querySelector('button[type="submit"]');
    
    // 初始化
    if (signupForm) {
        initFormValidation();
        setupFormSubmit();
    }
    
    /**
     * 初始化表单验证
     */
    function initFormValidation() {
        // 实时验证用户名
        if (usernameInput) {
            usernameInput.addEventListener('input', function() {
                validateUsernameRealTime(this.value.trim());
            });
        }
        
        // 实时验证邮箱
        if (emailInput) {
            emailInput.addEventListener('input', function() {
                validateEmailRealTime(this.value.trim());
            });
        }
        
        // 实时验证密码
        if (passwordInput) {
            passwordInput.addEventListener('input', function() {
                validatePasswordRealTime(this.value);
                if (confirmPasswordInput && confirmPasswordInput.value) {
                    validateConfirmPasswordRealTime(confirmPasswordInput.value, this.value);
                }
            });
        }
        
        // 实时验证确认密码
        if (confirmPasswordInput && passwordInput) {
            confirmPasswordInput.addEventListener('input', function() {
                validateConfirmPasswordRealTime(this.value, passwordInput.value);
            });
        }
        
        // 密码显示/隐藏切换
        const togglePasswordBtn = document.getElementById('togglePassword');
        const toggleConfirmPasswordBtn = document.getElementById('toggleConfirmPassword');
        
        if (togglePasswordBtn && passwordInput) {
            togglePasswordBtn.addEventListener('click', function() {
                togglePasswordVisibility(passwordInput, this);
            });
        }
        
        if (toggleConfirmPasswordBtn && confirmPasswordInput) {
            toggleConfirmPasswordBtn.addEventListener('click', function() {
                togglePasswordVisibility(confirmPasswordInput, this);
            });
        }
    }
    
    /**
     * 设置表单提交
     */
    function setupFormSubmit() {
        signupForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitForm();
        });
    }
    
    /**
     * 验证用户名（实时）
     */
    function validateUsernameRealTime(username) {
        if (!usernameError) return true;
        
        if (username.length < 3) {
            showError(usernameError, '用户名至少需要3个字符');
            return false;
        }
        
        if (username.length > 20) {
            showError(usernameError, '用户名不能超过20个字符');
            return false;
        }
        
        if (!/^[a-zA-Z0-9_]+$/.test(username)) {
            showError(usernameError, '用户名只能包含字母、数字和下划线');
            return false;
        }
        
        hideError(usernameError);
        return true;
    }
    
    /**
     * 验证邮箱（实时）
     */
    function validateEmailRealTime(email) {
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
     * 验证密码（实时）
     */
    function validatePasswordRealTime(password) {
        if (!passwordError) return true;
        
        if (password.length < 8) {
            showError(passwordError, '密码至少需要8个字符');
            return false;
        }
        
        // 检查密码强度
        let strength = 0;
        if (password.length >= 8) strength++;
        if (/[a-z]/.test(password)) strength++;
        if (/[A-Z]/.test(password)) strength++;
        if (/[0-9]/.test(password)) strength++;
        if (/[^A-Za-z0-9]/.test(password)) strength++;
        
        // 更新密码强度指示器
        updatePasswordStrength(strength);
        
        if (strength < 3) {
            showError(passwordError, '密码强度不足，建议包含大小写字母和数字');
            return false;
        }
        
        hideError(passwordError);
        return true;
    }
    
    /**
     * 验证确认密码（实时）
     */
    function validateConfirmPasswordRealTime(confirmPassword, password) {
        if (!confirmPasswordError) return true;
        
        if (!confirmPassword) {
            showError(confirmPasswordError, '请确认密码');
            return false;
        }
        
        if (confirmPassword !== password) {
            showError(confirmPasswordError, '两次输入的密码不一致');
            return false;
        }
        
        hideError(confirmPasswordError);
        return true;
    }
    
    /**
     * 更新密码强度指示器
     */
    function updatePasswordStrength(strength) {
        const strengthBar = document.getElementById('passwordStrength');
        const strengthText = document.getElementById('strengthText');
        
        if (!strengthBar || !strengthText) return;
        
        const strengthLabels = ['极弱', '弱', '中等', '强', '极强'];
        const strengthColors = ['#ff4757', '#ffa502', '#ffd32a', '#2ed573', '#00d4ff'];
        const strengthPercent = (strength / 5) * 100;
        
        strengthBar.style.width = `${strengthPercent}%`;
        strengthBar.style.backgroundColor = strengthColors[strength - 1] || strengthColors[0];
        strengthText.textContent = strengthLabels[strength - 1] || strengthLabels[0];
        strengthText.style.color = strengthColors[strength - 1] || strengthColors[0];
    }
    
    /**
     * 切换密码可见性
     */
    function togglePasswordVisibility(inputElement, buttonElement) {
        const icon = buttonElement.querySelector('i');
        
        if (inputElement.type === 'password') {
            inputElement.type = 'text';
            icon.className = 'fas fa-eye-slash';
        } else {
            inputElement.type = 'password';
            icon.className = 'fas fa-eye';
        }
    }
    
    /**
     * 验证所有字段
     */
    function validateAll() {
        const usernameValid = validateUsernameRealTime(usernameInput ? usernameInput.value.trim() : '');
        const emailValid = validateEmailRealTime(emailInput ? emailInput.value.trim() : '');
        const passwordValid = validatePasswordRealTime(passwordInput ? passwordInput.value : '');
        const confirmPasswordValid = validateConfirmPasswordRealTime(
            confirmPasswordInput ? confirmPasswordInput.value : '',
            passwordInput ? passwordInput.value : ''
        );
        
        // 检查服务条款
        if (termsCheckbox && !termsCheckbox.checked) {
            alert('请阅读并同意服务条款和隐私政策');
            return false;
        }
        
        return usernameValid && emailValid && passwordValid && confirmPasswordValid;
    }
    
    /**
     * 提交表单 - 实际注册功能
     */
    function submitForm() {
        if (!validateAll()) {
            return false;
        }
        
        // 显示加载状态
        if (submitButton) {
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 注册中...';
            submitButton.disabled = true;
        }
        
        // 收集用户数据
        const userData = {
            id: Date.now().toString(),
            username: usernameInput.value.trim(),
            email: emailInput.value.trim(),
            password: btoa(passwordInput.value), // 简单编码，实际项目应该用哈希
            timestamp: new Date().toISOString(),
            termsAccepted: termsCheckbox ? termsCheckbox.checked : false,
            toolsUsed: 0,
            tutorialsCompleted: 0,
            points: 100,
            level: '普通会员'
        };
        
        // 保存用户数据到localStorage
        try {
            // 检查是否已存在用户
            const existingUsers = JSON.parse(localStorage.getItem('ai24x_users') || '[]');
            const userExists = existingUsers.some(user => user.email === userData.email);
            
            if (userExists) {
                alert('该邮箱已被注册，请使用其他邮箱或直接登录');
                resetSubmitButton();
                return false;
            }
            
            // 添加新用户
            existingUsers.push(userData);
            localStorage.setItem('ai24x_users', JSON.stringify(existingUsers));
            
            // 保存当前用户登录状态
            localStorage.setItem('ai24x_logged_in', 'true');
            localStorage.setItem('ai24x_username', userData.username);
            localStorage.setItem('ai24x_email', userData.email);
            localStorage.setItem('ai24x_user_id', userData.id);
            
            // 显示成功消息
            if (successMessage) {
                successMessage.textContent = '注册成功！正在跳转到用户中心...';
                successMessage.style.color = '#2ed573';
                successMessage.style.display = 'block';
            }
            
            // 3秒后跳转到用户中心
            setTimeout(function() {
                window.location.href = '/user-center';
            }, 3000);
            
        } catch (error) {
            console.error('注册失败:', error);
            alert('注册失败，请稍后重试');
            resetSubmitButton();
        }
        
        return false;
    }
    
    /**
     * 重置提交按钮状态
     */
    function resetSubmitButton() {
        if (submitButton) {
            submitButton.innerHTML = '<i class="fas fa-user-plus"></i> 注册';
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
     * 显示成功消息
     */
    function showSuccessMessage() {
        if (successMessage) {
            successMessage.textContent = '注册成功！正在跳转到用户中心...';
            successMessage.style.color = '#2ed573';
            successMessage.style.display = 'block';
        }
    }
});