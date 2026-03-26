/**
 * 语言切换器组件
 * 提供中英文切换功能
 */

const { getTranslation, getCurrentLanguage, setCurrentLanguage } = require('./translations');

class LanguageSwitcher {
    constructor(options = {}) {
        this.options = {
            container: options.container || document.body,
            position: options.position || 'top-right', // top-right, top-left, bottom-right, bottom-left
            showFlags: options.showFlags !== false,
            showText: options.showText !== false,
            defaultLang: options.defaultLang || 'zh',
            storageKey: options.storageKey || 'ai24x_lang',
            onChange: options.onChange || null
        };
        
        this.currentLang = getCurrentLanguage() || this.options.defaultLang;
        this.init();
    }
    
    init() {
        this.createSwitcher();
        this.applyLanguage();
        this.bindEvents();
    }
    
    createSwitcher() {
        // 创建语言切换器容器
        this.container = document.createElement('div');
        this.container.className = 'language-switcher';
        this.container.style.cssText = `
            position: fixed;
            z-index: 1000;
            ${this.getPositionStyles()};
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            padding: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.3s ease;
            border: 1px solid rgba(108, 99, 255, 0.2);
        `;
        
        // 创建语言选项
        this.createLanguageOptions();
        
        // 添加到页面
        this.options.container.appendChild(this.container);
    }
    
    getPositionStyles() {
        const positions = {
            'top-right': 'top: 20px; right: 20px;',
            'top-left': 'top: 20px; left: 20px;',
            'bottom-right': 'bottom: 20px; right: 20px;',
            'bottom-left': 'bottom: 20px; left: 20px;'
        };
        return positions[this.options.position] || positions['top-right'];
    }
    
    createLanguageOptions() {
        const languages = [
            { code: 'zh', name: '中文', flag: '🇨🇳' },
            { code: 'en', name: 'English', flag: '🇺🇸' }
        ];
        
        languages.forEach(lang => {
            const button = document.createElement('button');
            button.className = `lang-btn ${lang.code === this.currentLang ? 'active' : ''}`;
            button.dataset.lang = lang.code;
            button.style.cssText = `
                background: ${lang.code === this.currentLang ? 'linear-gradient(135deg, #6c63ff, #ff6b9d)' : 'transparent'};
                color: ${lang.code === this.currentLang ? 'white' : '#333'};
                border: 1px solid ${lang.code === this.currentLang ? 'transparent' : '#ddd'};
                border-radius: 15px;
                padding: 8px 15px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.3s ease;
                outline: none;
            `;
            
            if (this.options.showFlags) {
                const flagSpan = document.createElement('span');
                flagSpan.textContent = lang.flag;
                flagSpan.style.fontSize = '16px';
                button.appendChild(flagSpan);
            }
            
            if (this.options.showText) {
                const textSpan = document.createElement('span');
                textSpan.textContent = lang.name;
                button.appendChild(textSpan);
            } else if (!this.options.showFlags) {
                // 如果既不显示国旗也不显示文字，显示代码
                const codeSpan = document.createElement('span');
                codeSpan.textContent = lang.code.toUpperCase();
                button.appendChild(codeSpan);
            }
            
            button.addEventListener('mouseenter', () => {
                if (lang.code !== this.currentLang) {
                    button.style.background = 'rgba(108, 99, 255, 0.1)';
                    button.style.transform = 'translateY(-2px)';
                }
            });
            
            button.addEventListener('mouseleave', () => {
                if (lang.code !== this.currentLang) {
                    button.style.background = 'transparent';
                    button.style.transform = 'translateY(0)';
                }
            });
            
            button.addEventListener('click', () => this.switchLanguage(lang.code));
            
            this.container.appendChild(button);
        });
    }
    
    switchLanguage(lang) {
        if (lang === this.currentLang) return;
        
        this.currentLang = lang;
        setCurrentLanguage(lang);
        
        // 更新按钮状态
        this.updateButtonStates();
        
        // 应用新语言
        this.applyLanguage();
        
        // 触发回调
        if (typeof this.options.onChange === 'function') {
            this.options.onChange(lang);
        }
        
        // 显示切换提示
        this.showNotification(lang);
    }
    
    updateButtonStates() {
        const buttons = this.container.querySelectorAll('.lang-btn');
        buttons.forEach(button => {
            const lang = button.dataset.lang;
            const isActive = lang === this.currentLang;
            
            button.className = `lang-btn ${isActive ? 'active' : ''}`;
            button.style.background = isActive ? 'linear-gradient(135deg, #6c63ff, #ff6b9d)' : 'transparent';
            button.style.color = isActive ? 'white' : '#333';
            button.style.border = isActive ? '1px solid transparent' : '1px solid #ddd';
            button.style.transform = isActive ? 'translateY(-2px)' : 'translateY(0)';
        });
    }
    
    applyLanguage() {
        // 获取所有需要翻译的元素
        const translatableElements = document.querySelectorAll('[data-i18n]');
        
        translatableElements.forEach(element => {
            const key = element.getAttribute('data-i18n');
            const translation = getTranslation(key, this.currentLang);
            
            if (translation) {
                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                    element.placeholder = translation;
                } else if (element.hasAttribute('data-i18n-html')) {
                    element.innerHTML = translation;
                } else {
                    element.textContent = translation;
                }
            }
        });
        
        // 更新页面标题
        this.updatePageTitle();
        
        // 更新HTML lang属性
        document.documentElement.lang = this.currentLang;
    }
    
    updatePageTitle() {
        const titleKey = document.querySelector('title')?.getAttribute('data-i18n');
        if (titleKey) {
            const translation = getTranslation(titleKey, this.currentLang);
            if (translation) {
                document.title = translation;
            }
        }
    }
    
    showNotification(lang) {
        // 移除现有的通知
        const existingNotification = document.querySelector('.lang-notification');
        if (existingNotification) {
            existingNotification.remove();
        }
        
        // 创建新通知
        const notification = document.createElement('div');
        notification.className = 'lang-notification';
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: linear-gradient(135deg, #6c63ff, #ff6b9d);
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(108, 99, 255, 0.3);
            z-index: 1001;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideIn 0.3s ease;
        `;
        
        const langName = lang === 'zh' ? '中文' : 'English';
        const flag = lang === 'zh' ? '🇨🇳' : '🇺🇸';
        
        notification.innerHTML = `
            <span style="font-size: 18px;">${flag}</span>
            <span>已切换到 ${langName}</span>
        `;
        
        document.body.appendChild(notification);
        
        // 3秒后自动消失
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
        
        // 添加CSS动画
        this.addNotificationStyles();
    }
    
    addNotificationStyles() {
        if (!document.querySelector('#lang-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'lang-notification-styles';
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
                
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    bindEvents() {
        // 监听storage变化（多标签页同步）
        window.addEventListener('storage', (e) => {
            if (e.key === this.options.storageKey && e.newValue !== this.currentLang) {
                this.currentLang = e.newValue;
                this.updateButtonStates();
                this.applyLanguage();
            }
        });
    }
    
    // 公共方法
    getCurrentLanguage() {
        return this.currentLang;
    }
    
    setLanguage(lang) {
        this.switchLanguage(lang);
    }
    
    translate(key) {
        return getTranslation(key, this.currentLang);
    }
    
    // 销毁方法
    destroy() {
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
    }
}

// 自动初始化函数
function initLanguageSwitcher(options = {}) {
    // 等待DOM加载完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.ai24xLanguageSwitcher = new LanguageSwitcher(options);
        });
    } else {
        window.ai24xLanguageSwitcher = new LanguageSwitcher(options);
    }
}

// 导出
module.exports = {
    LanguageSwitcher,
    initLanguageSwitcher,
    getTranslation,
    getCurrentLanguage,
    setCurrentLanguage
};