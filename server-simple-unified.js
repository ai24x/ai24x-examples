/**
 * AI24X缃戠珯鏈嶅姟 - 绠€鍖栫粺涓€鐗? * 鐗堟湰: 5.0.0
 * 鍒涘缓鏃堕棿: 2026-03-19
 * 鍔熻兘: 闈欐€佹枃浠舵湇鍔?+ 鑷姩淇澶栭儴閾炬帴
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;
const projectDir = __dirname;

// 绠€鍗曠殑HTML淇鍑芥暟
function fixHTML(content) {
    // 1. 绉婚櫎鎵€鏈夊閮–DN閾炬帴
    content = content.replace(/<link[^>]*href=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    content = content.replace(/<script[^>]*src=["']https:\/\/[^"']*["'][^>]*>/gi, '');
    
    // 2. 绉婚櫎涓嶅瓨鍦ㄧ殑CSS鏂囦欢寮曠敤
    content = content.replace(/<link[^>]*href=["']spacing-unified\.css["'][^>]*>/gi, '');
    
    // 3. 娣诲姞鏈湴CSS閾炬帴锛堝鏋滀笉瀛樺湪锛?    if (!content.includes('font-awesome-local.css')) {
        const localCSS = `
    <!-- 100% 鏈湴鍥炬爣 + 瀛椾綋 -->
    <link rel="stylesheet" href="/font-awesome-local.css">
    <link rel="stylesheet" href="/fonts-local.css">`;
        
        // 鎻掑叆鍒?/head>涔嬪墠
        const headEnd = content.indexOf('</head>');
        if (headEnd !== -1) {
            content = content.slice(0, headEnd) + localCSS + content.slice(headEnd);
        }
    }
    
    // 4. 娣诲姞CSP meta鏍囩锛堝鏋滀笉瀛樺湪锛?    if (!content.includes('Content-Security-Policy')) {
        const cspMeta = `
    <!-- 绾湰鍦板畨鍏ㄧ瓥鐣?-->
    <meta http-equiv="Content-Security-Policy" content="
        default-src 'self';
        script-src 'self' 'unsafe-inline';
        style-src 'self' 'unsafe-inline';
        font-src 'self';
        img-src 'self' data:;
    ">`;
        
        // 鎻掑叆鍒?head>涔嬪悗
        const headStart = content.indexOf('<head>');
        if (headStart !== -1) {
            const insertPos = headStart + '<head>'.length;
            content = content.slice(0, insertPos) + cspMeta + content.slice(insertPos);
        }
    }
    
    // 5. 淇鍥炬爣绫诲悕
    content = content.replace(/class="fas fa-/g, 'class="fa fa-');
    content = content.replace(/class='fas fa-/g, "class='fa fa-");
    content = content.replace(/class="fab fa-/g, 'class="fa fa-');
    content = content.replace(/class='fab fa-/g, "class='fa fa-");
    
    return content;
}

// 鍒涘缓HTTP鏈嶅姟鍣?const server = http.createServer((req, res) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
    
    // 璺敱澶勭悊
    let filePath = '';
    
    // 绉婚櫎鏌ヨ鍙傛暟锛堝 ?search=gpt锛?    const urlPath = req.url.split('?')[0];
    
    // 棣栭〉
    if (urlPath === '/' || urlPath === '/index.html') {
        filePath = path.join(projectDir, 'index.html');
    }
    // 宸ュ叿搴?    else if (urlPath === '/tools' || urlPath === '/tools.html' || urlPath === '/tools/') {
        filePath = path.join(projectDir, 'tools-static.html');
    }
    // 鏁欑▼
    else if (urlPath === '/tutorials' || urlPath === '/tutorials.html' || urlPath === '/tutorials/') {
        filePath = path.join(projectDir, 'tutorials', 'index.html');
    }
    // 瀹氬埗椤甸潰
    else if (urlPath === '/custom' || urlPath === '/custom.html') {
        filePath = path.join(projectDir, 'custom.html');
    }
    // 鐧诲綍椤甸潰
    else if (urlPath === '/login' || urlPath === '/login.html') {
        filePath = path.join(projectDir, 'login.html');
    }
    // 娉ㄥ唽椤甸潰
    else if (urlPath === '/signup' || urlPath === '/signup.html') {
        filePath = path.join(projectDir, 'signup.html');
    }
    // 鏈湴CSS鏂囦欢
    else if (urlPath === '/font-awesome-local.css') {
        filePath = path.join(projectDir, 'font-awesome-local.css');
    }
    else if (urlPath === '/fonts-local.css') {
        filePath = path.join(projectDir, 'fonts-local.css');
    }
    // 鍏朵粬CSS鏂囦欢
    else if (urlPath.endsWith('.css')) {
        filePath = path.join(projectDir, urlPath.substring(1));
    }
    // 闈欐€佹枃浠?    else {
        filePath = path.join(projectDir, urlPath);
    }
    
    // 妫€鏌ユ枃浠舵墿灞曞悕
    const ext = path.extname(filePath).toLowerCase();
    
    // 璇诲彇鏂囦欢
    fs.readFile(filePath, 'utf8', (err, data) => {
        if (err) {
            console.error(`鏂囦欢璇诲彇閿欒: ${filePath}`, err);
            res.statusCode = 404;
            res.end('404 - 鏂囦欢鏈壘鍒?);
            return;
        }
        
        // 璁剧疆Content-Type
        const contentType = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.json': 'application/json'
        }[ext] || 'text/plain';
        
        res.setHeader('Content-Type', contentType);
        
        // 濡傛灉鏄疕TML鏂囦欢锛岃繘琛岀畝鍗曚慨澶?        if (ext === '.html') {
            data = fixHTML(data);
        }
        
        // 鍙戦€佸搷搴?        res.end(data);
    });
});

// 鍚姩鏈嶅姟鍣紙鐩戝惉鎵€鏈塈P鍦板潃锛?server.listen(PORT, '0.0.0.0', () => {
    console.log('馃殌 AI24X绠€鍖栫粺涓€缃戠珯鏈嶅姟鍚姩鎴愬姛锛?);
    console.log(`馃搳 鏈湴璁块棶: http://localhost:${PORT}`);
    console.log(`馃寪 缃戠粶璁块棶: http://${getLocalIP()}:${PORT}`);
    console.log(`鈴?鍚姩鏃堕棿: ${new Date().toLocaleString()}`);
    console.log(`馃搧 鏈嶅姟鐩綍: ${projectDir}`);
    console.log('馃帹 鐗规€? 缁熶竴閰嶇疆 + 缇庤鍥炬爣 + 绾湰鍦?);
    console.log('馃敡 鍥炬爣: 鏈湴Font Awesome鏍峰紡');
    console.log('馃敜 瀛椾綋: 鏈湴绯荤粺瀛椾綋');
    console.log('馃攧 鏈嶅姟杩愯涓?..');
});

// 鑾峰彇鏈湴IP鍦板潃
function getLocalIP() {
    const interfaces = require('os').networkInterfaces();
    for (const name of Object.keys(interfaces)) {
        for (const iface of interfaces[name]) {
            if (iface.family === 'IPv4' && !iface.internal) {
                return iface.address;
            }
        }
    }
    return 'localhost';
}

// 浼橀泤鍏抽棴
process.on('SIGINT', () => {
    console.log('\n馃洃 姝ｅ湪鍏抽棴鏈嶅姟鍣?..');
    server.close(() => {
        console.log('鉁?鏈嶅姟鍣ㄥ凡鍏抽棴');
        process.exit(0);
    });
});

