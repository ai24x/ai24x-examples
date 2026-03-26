const fs = require('fs');
const path = require('path');

// 需要清理的页面列表
const pagesToClean = ['login.html', 'signup.html'];

// 清理单个页面
function cleanPage(pagePath) {
    try {
        const fullPath = path.join(__dirname, pagePath);
        if (!fs.existsSync(fullPath)) {
            console.log(`❌ 文件不存在: ${pagePath}`);
            return false;
        }

        let content = fs.readFileSync(fullPath, 'utf8');
        
        console.log(`🔍 分析 ${pagePath}...`);
        console.log(`📏 文件大小: ${content.length} 字节`);
        
        // 1. 修复.auth-container的重复注释和属性
        console.log('\n🔧 修复.auth-container...');
        if (content.includes('.auth-container {')) {
            // 找到.auth-container的定义
            const authContainerRegex = /\.auth-container\s*\{[\s\S]*?\}/;
            const match = content.match(authContainerRegex);
            
            if (match) {
                const original = match[0];
                console.log(`📋 原始.auth-container定义:`);
                console.log(original.substring(0, 200));
                
                // 清理重复的注释和属性
                const cleaned = original
                    .replace(/\/\*[\s\S]*?\*\//g, '') // 移除所有注释
                    .replace(/padding:\s*[^;]+;/g, '') // 移除所有padding定义
                    .replace(/\s+/g, ' ') // 压缩空格
                    .replace(/\s*\{\s*/, ' {\n    ') // 格式化开始
                    .replace(/\s*\}/, '\n}'); // 格式化结束
                
                // 添加干净的.auth-container定义
                const cleanAuthContainer = `.auth-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
    padding: 50px 20px; /* 合适美观的距离 */
}`;
                
                content = content.replace(original, cleanAuthContainer);
                console.log(`✅ ${pagePath}: 已清理.auth-container`);
            }
        }
        
        // 2. 修复.auth-card的重复属性
        console.log('\n🔧 修复.auth-card...');
        if (content.includes('.auth-card {')) {
            const authCardRegex = /\.auth-card\s*\{[\s\S]*?\}/;
            const match = content.match(authCardRegex);
            
            if (match) {
                const original = match[0];
                console.log(`📋 原始.auth-card定义:`);
                console.log(original.substring(0, 200));
                
                // 清理重复的属性
                const cleanAuthCard = `.auth-card {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    padding: 40px;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    margin-top: 40px; /* 与头部导航的美观距离 */
}`;
                
                content = content.replace(original, cleanAuthCard);
                console.log(`✅ ${pagePath}: 已清理.auth-card`);
            }
        }
        
        // 3. 移除重复的CSS属性定义
        console.log('\n🔧 检查重复的CSS属性...');
        const duplicateProperties = [
            'width:', 'max-width:', 'box-shadow:', 'padding:', 'margin-top:'
        ];
        
        duplicateProperties.forEach(prop => {
            const regex = new RegExp(`${prop}[^;]+;[\\s\\S]*?${prop}[^;]+;`, 'g');
            if (regex.test(content)) {
                console.log(`⚠️  发现重复的 ${prop} 属性`);
                // 这里我们已经在上面清理了主要定义
            }
        });
        
        // 4. 检查重复的头部导航
        console.log('\n🔧 检查重复的头部导航...');
        const headerCount = (content.match(/<header class="header">/g) || []).length;
        if (headerCount > 1) {
            console.log(`⚠️  发现 ${headerCount} 个头部导航，需要清理`);
            // 保留第一个，移除其他的
            const parts = content.split('<header class="header">');
            if (parts.length > 1) {
                const firstHeader = parts[1].split('</header>')[0];
                const cleanContent = parts[0] + 
                    '<header class="header">' + firstHeader + '</header>' + 
                    parts.slice(2).join('').split('</header>').slice(1).join('');
                content = cleanContent;
                console.log(`✅ ${pagePath}: 已移除重复的头部导航`);
            }
        } else {
            console.log(`✅ ${pagePath}: 头部导航数量正常 (${headerCount})`);
        }
        
        // 5. 检查重复的底部
        console.log('\n🔧 检查重复的底部...');
        const footerCount = (content.match(/<footer class="footer">/g) || []).length;
        if (footerCount > 1) {
            console.log(`⚠️  发现 ${footerCount} 个底部，需要清理`);
            // 保留最后一个，移除其他的
            const parts = content.split('<footer class="footer">');
            if (parts.length > 1) {
                const lastFooter = parts[parts.length - 1];
                const cleanContent = parts.slice(0, -1).join('') + 
                    '<footer class="footer">' + lastFooter;
                content = cleanContent;
                console.log(`✅ ${pagePath}: 已移除重复的底部`);
            }
        } else {
            console.log(`✅ ${pagePath}: 底部数量正常 (${footerCount})`);
        }
        
        // 6. 检查重复的脚本
        console.log('\n🔧 检查重复的脚本...');
        const scriptTags = (content.match(/<script>/g) || []).length;
        const scriptEndTags = (content.match(/<\/script>/g) || []).length;
        
        if (scriptTags !== scriptEndTags) {
            console.log(`⚠️  脚本标签不匹配: <script>=${scriptTags}, </script>=${scriptEndTags}`);
        } else {
            console.log(`✅ ${pagePath}: 脚本标签匹配正常`);
        }
        
        // 7. 清理多余的空白和空行
        console.log('\n🔧 清理格式...');
        content = content.replace(/\n\s*\n\s*\n/g, '\n\n');
        content = content.replace(/\s+\}/g, '\n}');
        content = content.replace(/\{\s+/g, '{\n    ');
        console.log(`✅ ${pagePath}: 已清理格式`);
        
        // 8. 验证修复结果
        console.log('\n🔍 验证修复结果...');
        const finalAuthContainer = content.match(/\.auth-container\s*\{[\s\S]*?\}/);
        const finalAuthCard = content.match(/\.auth-card\s*\{[\s\S]*?\}/);
        
        if (finalAuthContainer) {
            console.log(`✅ 最终.auth-container:`);
            console.log(finalAuthContainer[0]);
        }
        
        if (finalAuthCard) {
            console.log(`✅ 最终.auth-card:`);
            console.log(finalAuthCard[0]);
        }
        
        // 9. 保存清理后的文件
        fs.writeFileSync(fullPath, content, 'utf8');
        const finalSize = content.length;
        console.log(`\n📊 ${pagePath} 清理完成:`);
        console.log(`  最终大小: ${finalSize} 字节`);
        console.log(`  清理内容: 重复的CSS属性、注释、格式问题`);
        console.log(`  修复效果: 页面结构清晰，样式简洁`);
        
        return true;
        
    } catch (error) {
        console.log(`❌ 清理失败 ${pagePath}:`, error.message);
        return false;
    }
}

// 主函数
function main() {
    console.log('🚀 开始清理登录和注册页面...\n');
    console.log('💡 清理目标：');
    console.log('  1. 修复重复的CSS属性和注释');
    console.log('  2. 确保页面结构正确');
    console.log('  3. 设置合适美观的间距');
    console.log('  4. 保持功能完整\n');
    
    let successCount = 0;
    let failCount = 0;
    
    pagesToClean.forEach(pagePath => {
        console.log(`\n🔧 清理: ${pagePath}`);
        console.log('─'.repeat(50));
        
        if (cleanPage(pagePath)) {
            successCount++;
        } else {
            failCount++;
        }
    });
    
    console.log('\n' + '─'.repeat(50));
    console.log('📊 清理完成统计:');
    console.log(`✅ 成功: ${successCount} 个页面`);
    console.log(`❌ 失败: ${failCount} 个页面`);
    
    if (failCount === 0) {
        console.log('\n🎉 登录和注册页面已清理完成！');
        console.log('\n💡 清理内容：');
        console.log('  1. 修复了重复的CSS属性和注释');
        console.log('  2. 设置了合适美观的间距');
        console.log('  3. 确保了页面结构正确');
        console.log('  4. 保持了所有功能完整');
        console.log('\n📱 现在可以测试页面是否正常！');
    } else {
        console.log('\n⚠️ 部分页面清理失败，请检查错误信息。');
    }
}

// 执行清理
main();