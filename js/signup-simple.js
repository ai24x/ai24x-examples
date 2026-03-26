/**
 * AI24X 简单注册脚本
 * 版本: 1.0.0
 * 功能: 最基本的注册功能，确保可用
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('注册脚本加载成功');
    
    // 获取表单元素
    const signupForm = document.getElementById('signupForm');
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const toggleConfirmPasswordBtn = document.getElementById('toggleConfirmPassword');
    
    if (!signupForm) {
        console.error('找不到注册表单');
        return;
    }
    
    // 密码显示/隐藏切换
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
    
    if (toggleConfirmPasswordBtn && confirmPasswordInput) {
        toggleConfirmPasswordBtn.addEventListener('click', function() {
            const icon = this.querySelector('i');
            if (confirmPasswordInput.type === 'password') {
                confirmPasswordInput.type = 'text';
                icon.className = 'fas fa-eye-slash';
            } else {
                confirmPasswordInput.type = 'password';
                icon.className = 'fas fa-eye';
            }
        });
    }
    
    // 表单提交
    signupForm.addEventListener('submit', function(e) {
        e.preventDefault();
        console.log('注册表单提交');
        
        // 获取输入值
        const username = usernameInput ? usernameInput.value.trim() : '';
        const email = emailInput ? emailInput.value.trim() : '';
        const password = passwordInput ? passwordInput.value : '';
        const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : '';
        
        // 简单验证
        if (!username) {
            alert('请输入用户名');
            return;
        }
        
        if (username.length < 3) {
            alert('用户名至少需要3个字符');
            return;
        }
        
        if (!email) {
            alert('请输入邮箱地址');
            return;
        }
        
        // 简单邮箱验证
        if (!email.includes('@') || !email.includes('.')) {
            alert('请输入有效的邮箱地址');
            return;
        }
        
        if (!password) {
            alert('请输入密码');
            return;
        }
        
        if (password.length < 6) {
            alert('密码至少需要6个字符');
            return;
        }
        
        if (password !== confirmPassword) {
            alert('两次输入的密码不一致');
            return;
        }
        
        // 显示加载状态
        const submitBtn = signupForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 注册中...';
            submitBtn.disabled = true;
            
            // 模拟网络延迟
            setTimeout(() => {
                try {
                    // 检查是否已存在用户
                    const existingUsers = JSON.parse(localStorage.getItem('ai24x_users') || '[]');
                    const userExists = existingUsers.some(user => user.email === email);
                    
                    if (userExists) {
                        alert('该邮箱已被注册，请使用其他邮箱或直接登录');
                        submitBtn.innerHTML = originalText;
                        submitBtn.disabled = false;
                        return;
                    }
                    
                    // 创建新用户
                    const newUser = {
                        id: Date.now().toString(),
                        username: username,
                        email: email,
                        password: btoa(password), // 简单编码
                        timestamp: new Date().toISOString(),
                        toolsUsed: 0,
                        tutorialsCompleted: 0,
                        points: 100,
                        level: '普通会员'
                    };
                    
                    // 保存用户
                    existingUsers.push(newUser);
                    localStorage.setItem('ai24x_users', JSON.stringify(existingUsers));
                    
                    // 自动登录
                    localStorage.setItem('ai24x_logged_in', 'true');
                    localStorage.setItem('ai24x_username', newUser.username);
                    localStorage.setItem('ai24x_email', newUser.email);
                    localStorage.setItem('ai24x_user_id', newUser.id);
                    
                    alert('注册成功！正在跳转到用户中心...');
                    window.location.href = '/user-center';
                    
                } catch (error) {
                    console.error('注册失败:', error);
                    alert('注册失败，请稍后重试');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            }, 1000);
        }
    });
    
    console.log('注册脚本初始化完成');
});