/**
 * AI24X页面生成器
 * 高效生成中文页面，避免卡顿
 */

const fs = require('fs');
const path = require('path');

class PageGenerator {
    constructor() {
        this.templatesDir = path.join(__dirname, '../templates');
        this.componentsDir = path.join(this.templatesDir, 'components');
        this.outputDir = path.join(__dirname, '..');
    }

    // 读取模板文件
    readTemplate(templateName) {
        const templatePath = path.join(this.templatesDir, templateName);
        return fs.readFileSync(templatePath, 'utf8');
    }

    // 读取组件
    readComponent(componentName) {
        const componentPath = path.join(this.componentsDir, componentName);
        return fs.readFileSync(componentPath, 'utf8');
    }

    // 简单模板替换
    renderTemplate(template, data) {
        let result = template;
        
        // 替换变量
        for (const [key, value] of Object.entries(data)) {
            const placeholder = `{{${key}}}`;
            result = result.replace(new RegExp(placeholder, 'g'), value || '');
        }
        
        // 处理条件语句
        result = this.processConditionals(result, data);
        
        return result;
    }

    // 处理简单条件语句
    processConditionals(template, data) {
        let result = template;
        
        // 处理 {{#if var}}...{{/if}}
        const ifRegex = /\{\{#if (\w+)\}\}(.*?)\{\{\/if\}\}/gs;
        result = result.replace(ifRegex, (match, varName, content) => {
            return data[varName] ? content : '';
        });
        
        return result;
    }

    // 生成页面
    generatePage(pageConfig) {
        console.log(`开始生成页面: ${pageConfig.page_title}`);
        
        // 读取基础模板
        const baseTemplate = this.readTemplate('base-template.html');
        
        // 读取组件
        const header = this.readComponent('header.html');
        const footer = this.readComponent('footer.html');
        
        // 准备数据
        const templateData = {
            page_title: pageConfig.page_title,
            page_class: pageConfig.page_class || '',
            main_class: pageConfig.main_class || 'page-container',
            extra_css: pageConfig.extra_css || '',
            header: this.renderTemplate(header, pageConfig.active || {}),
            footer: footer,
            content: pageConfig.content,
            page_scripts: pageConfig.page_scripts || ''
        };
        
        // 渲染页面
        const pageHtml = this.renderTemplate(baseTemplate, templateData);
        
        // 保存页面
        const outputPath = path.join(this.outputDir, pageConfig.output_file);
        fs.writeFileSync(outputPath, pageHtml, 'utf8');
        
        console.log(`✅ 页面生成成功: ${outputPath}`);
        console.log(`📏 文件大小: ${(pageHtml.length / 1024).toFixed(2)} KB`);
        
        return outputPath;
    }

    // 快速生成常用页面
    generateCustomPage() {
        const content = `
        <div class="custom-container">
            <div class="custom-header">
                <h1>定制开发服务</h1>
                <p>为您量身打造AI解决方案，提升业务效率和创新能力</p>
            </div>
            
            <div class="services-grid">
                <div class="service-card">
                    <div class="service-icon">
                        <i class="fas fa-robot"></i>
                    </div>
                    <h3>AI助手定制</h3>
                    <p>基于您的业务需求，开发专属AI助手，提升工作效率</p>
                </div>
                
                <div class="service-card">
                    <div class="service-icon">
                        <i class="fas fa-code"></i>
                    </div>
                    <h3>系统集成</h3>
                    <p>将AI能力集成到现有系统，实现智能化升级</p>
                </div>
                
                <div class="service-card">
                    <div class="service-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <h3>数据分析</h3>
                    <p>利用AI进行数据分析和预测，支持业务决策</p>
                </div>
            </div>
            
            <div class="contact-form">
                <h2>立即咨询</h2>
                <form id="customForm">
                    <div class="form-group">
                        <input type="text" placeholder="您的姓名" required>
                    </div>
                    <div class="form-group">
                        <input type="email" placeholder="邮箱地址" required>
                    </div>
                    <div class="form-group">
                        <textarea placeholder="项目需求描述" rows="4" required></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary">提交咨询</button>
                </form>
            </div>
        </div>
        `;

        const extraCss = `
        <style>
            .custom-container {
                max-width: 1200px;
                margin: 40px auto;
                padding: 0 20px;
            }
            
            .custom-header {
                text-align: center;
                margin-bottom: 50px;
            }
            
            .custom-header h1 {
                font-size: 2.8rem;
                background: linear-gradient(90deg, #00d4ff, #0099ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 20px;
            }
            
            .custom-header p {
                color: #a0aec0;
                font-size: 1.2rem;
                max-width: 800px;
                margin: 0 auto;
            }
            
            .services-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 30px;
                margin: 40px 0;
            }
            
            .service-card {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(0, 212, 255, 0.1);
                border-radius: 16px;
                padding: 30px;
                transition: all 0.3s ease;
            }
            
            .service-card:hover {
                transform: translateY(-5px);
                border-color: #00d4ff;
                box-shadow: 0 10px 30px rgba(0, 212, 255, 0.1);
            }
            
            .service-icon {
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, #00d4ff, #0099ff);
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 20px;
                font-size: 24px;
                color: white;
            }
            
            .service-card h3 {
                font-size: 1.4rem;
                color: white;
                margin-bottom: 15px;
            }
            
            .service-card p {
                color: #a0aec0;
                line-height: 1.6;
            }
            
            .contact-form {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(0, 212, 255, 0.1);
                border-radius: 16px;
                padding: 40px;
                margin-top: 50px;
            }
            
            .contact-form h2 {
                font-size: 2rem;
                color: white;
                margin-bottom: 30px;
                text-align: center;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            .form-group input,
            .form-group textarea {
                width: 100%;
                padding: 15px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 10px;
                color: white;
                font-size: 1rem;
            }
            
            .form-group input:focus,
            .form-group textarea:focus {
                outline: none;
                border-color: #00d4ff;
                background: rgba(255, 255, 255, 0.08);
            }
            
            @media (max-width: 768px) {
                .custom-header h1 {
                    font-size: 2rem;
                }
                
                .services-grid {
                    grid-template-columns: 1fr;
                }
                
                .contact-form {
                    padding: 25px;
                }
            }
        </style>
        `;

        const pageScripts = `
        <script>
            document.getElementById('customForm')?.addEventListener('submit', function(e) {
                e.preventDefault();
                alert('咨询已提交！我们将尽快与您联系。');
                this.reset();
            });
        </script>
        `;

        return this.generatePage({
            page_title: '定制开发',
            page_class: 'custom-page',
            main_class: 'custom-main',
            extra_css: extraCss,
            output_file: 'custom.html',
            content: content,
            page_scripts: pageScripts,
            active: {
                active_custom: 'active'
            }
        });
    }

    // 更新现有页面头部
    updatePageHeader(pagePath, activePage) {
        console.log(`更新页面头部: ${pagePath}`);
        
        try {
            let pageContent = fs.readFileSync(pagePath, 'utf8');
            
            // 读取新头部
            const newHeader = this.readComponent('header.html');
            const renderedHeader = this.renderTemplate(newHeader, { [activePage]: 'active' });
            
            // 替换头部（简单实现，实际需要更精确的替换）
            // 这里简化处理，实际项目需要更稳健的HTML解析
            const headerRegex = /<header[\s\S]*?<\/header>/;
            if (headerRegex.test(pageContent)) {
                pageContent = pageContent.replace(headerRegex, renderedHeader);
                fs.writeFileSync(pagePath, pageContent, 'utf8');
                console.log(`✅ 页面头部更新成功: ${pagePath}`);
            } else {
                console.log(`⚠️  未找到头部，可能需要手动更新: ${pagePath}`);
            }
        } catch (error) {
            console.error(`❌ 更新页面失败: ${error.message}`);
        }
    }
}

// 使用示例
if (require.main === module) {
    const generator = new PageGenerator();
    
    // 生成custom页面
    generator.generateCustomPage();
    
    // 更新其他页面头部
    const pagesToUpdate = [
        { path: 'login.html', active: 'active_login' },
        { path: 'signup.html', active: 'active_signup' },
        { path: 'tools-index.html', active: 'active_tools' },
        { path: 'tutorials/index.html', active: 'active_tutorials' }
    ];
    
    pagesToUpdate.forEach(page => {
        const fullPath = path.join(generator.outputDir, page.path);
        if (fs.existsSync(fullPath)) {
            generator.updatePageHeader(fullPath, page.active);
        }
    });
    
    console.log('🎉 所有页面生成和更新完成！');
}

module.exports = PageGenerator;