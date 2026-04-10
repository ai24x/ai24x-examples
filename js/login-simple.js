/**
 * AI24X 简单登录脚本
 * 版本: 1.0.0
 * 功能: 最基本的登录功能，确保可用
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('登录脚本加载成功');
    
    // 获取表单元素
    const loginForm = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('togglePassword');
    
    if (!loginForm) {
        console.error('找不到登录表单');
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
    
    // 表单提交
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        console.log('登录表单提交');
        
        // 获取输入值
        const email = emailInput ? emailInput.value.trim() : '';
        const password = passwordInput ? passwordInput.value : '';
        
        // 简单验证
        if (!email) {
            alert('请输入邮箱地址');
            return;
        }
        
        if (!password) {
            alert('请输入密码');
            return;
        }
        
        // 显示加载状态
        const submitBtn = loginForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 登录中...';
            submitBtn.disabled = true;
            
            // 模拟网络延迟
            setTimeout(() => {
                // 检查用户是否存在
                const users = JSON.parse(localStorage.getItem('ai24x_users') || '[]');
                const user = users.find(u => u.email === email && u.password === btoa(password));
                
                if (user) {
                    // 登录成功
                    localStorage.setItem('ai24x_logged_in', 'true');
                    localStorage.setItem('ai24x_username', user.username);
                    localStorage.setItem('ai24x_email', user.email);
                    localStorage.setItem('ai24x_user_id', user.id);
                    
                    alert('登录成功！正在跳转到用户中心...');
                    window.location.href = '/user-center';
                } else {
                    // 登录失败
                    alert('邮箱或密码错误，请重试');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            }, 1000);
        }
    });
    
    // 检查URL参数
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('registered') === 'true') {
        const welcomeMsg = document.getElementById('welcomeMessage');
        if (welcomeMsg) {
            welcomeMsg.style.display = 'block';
            welcomeMsg.textContent = '注册成功！请使用您的账户登录。';
        }
    }
    
    console.log('登录脚本初始化完成');
});