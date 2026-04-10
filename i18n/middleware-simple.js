// 简化版国际化中间件 - 无缓存，轻量级
const fs = require('fs');
const path = require('path');

// 需要翻译的页面
const TRANSLATED_PAGES = [
    'index.html',
    'tools-index.html',
    'rankings-index.html',
    'signup.html',
    'login.html',
    'share.html'
];

// 简化翻译数据
const TRANSLATIONS = {
    zh: {
        'AI24X - 发现AI未来，就在AI24X': 'AI24X - 发现AI未来，就在AI24X',
        '首页': '首页',
        'AI工具库': 'AI工具库',
        '分类': '分类',
        '热门排行': '热门排行',
        '个性推荐': '个性推荐',
        '教程': '教程',
        '登录': '登录',
        '注册': '注册',
        '发现AI未来，就在AI24X': '发现AI未来，就在AI24X',
        '探索最前沿的AI工具': '探索最前沿的AI工具',
        '立即开始': '立即开始'
    },
    en: {
        'AI24X - 发现AI未来，就在AI24X': 'AI24X - Discover AI Future',
        '首页': 'Home',
        'AI工具库': 'AI Tools',
        '分类': 'Categories',
        '热门排行': 'Rankings',
        '个性推荐': 'Recommendations',
        '教程': 'Tutorials',
        '登录': 'Login',
        '注册': 'Sign Up',
        '发现AI未来，就在AI24X': 'Discover AI Future at AI24X',
        '探索最前沿的AI工具': 'Explore Cutting-edge AI Tools',
        '立即开始': 'Get Started'
    }
};

// 获取语言偏好
function getLanguageFromRequest(req) {
    // 1. 检查查询参数
    if (req.query.lang && (req.query.lang === 'zh' || req.query.lang === 'en')) {
        return req.query.lang;
    }
    
    // 2. 检查Cookie
    if (req.cookies && req.cookies.lang && (req.cookies.lang === 'zh' || req.cookies.lang === 'en')) {
        return req.cookies.lang;
    }
    
    // 3. 检查Accept-Language头
    if (req.headers['accept-language']) {
        const acceptLang = req.headers['accept-language'].toLowerCase();
        if (acceptLang.includes('zh')) {
            return 'zh';
        } else if (acceptLang.includes('en')) {
            return 'en';
        }
    }
    
    // 4. 默认中文
    return 'zh';
}

// 翻译HTML内容（简化版，无缓存）
function translateHtml(html, lang) {
    let translatedHtml = html;
    
    // 翻译文本内容
    Object.entries(TRANSLATIONS[lang] || TRANSLATIONS.zh).forEach(([key, translation]) => {
        const regex = new RegExp(key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
        translatedHtml = translatedHtml.replace(regex, translation);
    });
    
    // 更新html标签的语言属性
    translatedHtml = translatedHtml.replace(
        /<html([^>]*)>/,
        (match, attributes) => {
            // 移除现有的lang属性
            const cleanedAttributes = attributes.replace(/\s+lang=["'][^"']*["']/, '');
            // 添加新的lang属性
            return `<html${cleanedAttributes} lang="${lang}">`;
        }
    );
    
    return translatedHtml;
}

// 获取文件路径
function getFilePath(req) {
    let filePath = req.path;
    
    // 处理根路径
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

// 简化国际化中间件
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
    res.set('Content-Language', lang);
    
    // 获取原始文件路径
    const filePath = getFilePath(req);
    
    // 检查文件是否存在且是需要翻译的页面
    if (!fs.existsSync(filePath) || !TRANSLATED_PAGES.includes(path.basename(filePath))) {
        return next();
    }
    
    // 读取文件内容
    const originalHtml = fs.readFileSync(filePath, 'utf8');
    
    // 翻译HTML内容
    const translatedHtml = translateHtml(originalHtml, lang);
    
    // 发送翻译后的内容
    res.send(translatedHtml);
}

module.exports = { i18nMiddleware };