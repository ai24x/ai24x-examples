/**
 * 国际化中间件
 * 自动处理页面翻译和语言切换
 */

const { getTranslation, getCurrentLanguage, setCurrentLanguage } = require('./translations');
const fs = require('fs');
const path = require('path');

// 支持的页面列表
const SUPPORTED_PAGES = [
    'index.html',
    'tools-index.html',
    'share.html',
    'signup.html',
    'login.html'
];

// 页面翻译缓存
const translationCache = new Map();

// 国际化中间件
function i18nMiddleware(req, res, next) {
    // 跳过API请求、静态文件和特定路径
    if (req.path.startsWith('/api/') || 
        req.path.startsWith('/static/') ||
        req.path.match(/\.(css|js|jpg|jpeg|png|gif|webp|svg|woff|woff2|ttf|eot|ico)$/) ||
        req.path === '/health' ||
        req.path === '/status') {
        return next();
    }
    
    // 获取语言偏好
    const lang = getLanguageFromRequest(req);
    
    // 设置响应头
    res.setHeader('Content-Language', lang);
    
    // 对于HTML页面，进行翻译处理
    if (req.path.endsWith('.html') || req.path === '/') {
        return handleHtmlTranslation(req, res, lang);
    }
    
    next();
}

// 从请求中获取语言
function getLanguageFromRequest(req) {
    // 1. 检查URL参数
    if (req.query.lang && ['zh', 'en'].includes(req.query.lang)) {
        console.log(`[i18n] 从URL参数获取语言: ${req.query.lang}`);
        return req.query.lang;
    }
    
    // 2. 检查Cookie
    if (req.cookies && req.cookies.ai24x_lang) {
        const cookieLang = req.cookies.ai24x_lang;
        if (['zh', 'en'].includes(cookieLang)) {
            console.log(`[i18n] 从Cookie获取语言: ${cookieLang}`);
            return cookieLang;
        }
    }
    
    // 3. 检查Accept-Language头
    const acceptLanguage = req.headers['accept-language'];
    if (acceptLanguage) {
        const preferredLang = acceptLanguage.split(',')[0].split('-')[0];
        if (preferredLang === 'zh' || preferredLang === 'en') {
            console.log(`[i18n] 从浏览器头获取语言: ${preferredLang}`);
            return preferredLang;
        }
    }
    
    // 4. 使用默认语言
    console.log(`[i18n] 使用默认语言: zh`);
    return 'zh';
}

// 处理HTML页面翻译
function handleHtmlTranslation(req, res, lang) {
    const filePath = getFilePath(req);
    
    if (!filePath || !fs.existsSync(filePath)) {
        return res.status(404).send('页面不存在');
    }
    
    // 读取文件内容
    fs.readFile(filePath, 'utf8', (err, htmlContent) => {
        if (err) {
            console.error('读取HTML文件失败:', err);
            return res.status(500).send('服务器错误');
        }
        
        // 翻译HTML内容
        const translatedHtml = translateHtml(htmlContent, lang);
        
        // 添加语言切换脚本
        const finalHtml = addLanguageSwitcher(translatedHtml, lang, req.path);
        
        // 发送响应
        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        res.send(finalHtml);
    });
}

// 获取文件路径
function getFilePath(req) {
    let filePath = req.path;
    
    if (filePath === '/') {
        filePath = '/index.html';
    }
    
    // 移除开头的斜杠
    if (filePath.startsWith('/')) {
        filePath = filePath.substring(1);
    }
    
    // 构建完整路径
    return path.join(__dirname, '..', filePath);
}

// 翻译HTML内容
function translateHtml(html, lang) {
    // 缓存检查
    const cacheKey = `${html.substring(0, 100)}_${lang}`;
    if (translationCache.has(cacheKey)) {
        return translationCache.get(cacheKey);
    }
    
    let translatedHtml = html;
    
    // 替换翻译占位符 {{i18n.key}}
    const translationRegex = /\{\{i18n\.([^}]+)\}\}/g;
    translatedHtml = translatedHtml.replace(translationRegex, (match, key) => {
        const translation = getTranslation(key, lang);
        return translation || match;
    });
    
    // 替换data-i18n属性
    const dataI18nRegex = /data-i18n="([^"]+)"/g;
    translatedHtml = translatedHtml.replace(dataI18nRegex, (match, key) => {
        const translation = getTranslation(key, lang);
        return `data-i18n="${key}" title="${translation || key}"`;
    });
    
    // 更新html标签的语言属性（替换现有的lang属性）
    translatedHtml = translatedHtml.replace(
        /<html([^>]*)>/,
        (match, attributes) => {
            // 移除现有的lang属性
            const cleanedAttributes = attributes.replace(/\s+lang=["'][^"']*["']/, '');
            // 添加新的lang属性
            return `<html${cleanedAttributes} lang="${lang}">`;
        }
    );
    
    // 缓存结果
    translationCache.set(cacheKey, translatedHtml);
    
    return translatedHtml;
}

// 添加语言切换器（仅当页面没有语言切换器时添加）
function addLanguageSwitcher(html, currentLang, currentPath) {
    // 检查页面是否已经有语言切换器
    if (html.includes('language-switcher') || html.includes('lang-btn') || html.includes('langToggle')) {
        console.log(`[i18n] 页面已有语言切换器，跳过添加额外切换器`);
        return html;
    }
    
    // 对于没有语言切换器的页面，添加一个简单的切换器
    const languageSwitcher = `
        <!-- 简单语言切换器 -->
        <div class="simple-language-switcher" style="
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(0, 0, 0, 0.8);
            border-radius: 20px;
            padding: 8px;
            display: flex;
            gap: 5px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 212, 255, 0.3);
        ">
            <a href="?lang=zh" style="
                color: ${currentLang === 'zh' ? '#00d4ff' : '#b0b0b0'};
                text-decoration: none;
                padding: 5px 10px;
                border-radius: 15px;
                background: ${currentLang === 'zh' ? 'rgba(0, 212, 255, 0.1)' : 'transparent'};
                font-size: 12px;
            ">中文</a>
            <a href="?lang=en" style="
                color: ${currentLang === 'en' ? '#00d4ff' : '#b0b0b0'};
                text-decoration: none;
                padding: 5px 10px;
                border-radius: 15px;
                background: ${currentLang === 'en' ? 'rgba(0, 212, 255, 0.1)' : 'transparent'};
                font-size: 12px;
            ">EN</a>
        </div>
    `;
    
    // 在body结束前插入语言切换器
    return html.replace('</body>', languageSwitcher + '</body>');
}

// 批量翻译工具
function batchTranslateFiles(lang) {
    console.log(`开始批量翻译文件到 ${lang}...`);
    
    SUPPORTED_PAGES.forEach(page => {
        const filePath = path.join(__dirname, '..', page);
        
        if (fs.existsSync(filePath)) {
            try {
                const content = fs.readFileSync(filePath, 'utf8');
                const translated = translateHtml(content, lang);
                
                // 保存翻译后的文件
                const translatedPath = filePath.replace('.html', `.${lang}.html`);
                fs.writeFileSync(translatedPath, translated, 'utf8');
                
                console.log(`✓ 已翻译: ${page} -> ${page.replace('.html', `.${lang}.html`)}`);
            } catch (error) {
                console.error(`✗ 翻译失败 ${page}:`, error.message);
            }
        }
    });
    
    console.log('批量翻译完成！');
}

// 导出中间件和工具函数
module.exports = {
    i18nMiddleware,
    getLanguageFromRequest,
    translateHtml,
    batchTranslateFiles,
    SUPPORTED_PAGES
};