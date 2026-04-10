/**
 * AI24X 动态工具页面 JavaScript
 * 版本: 1.0.0
 * 日期: 2026-03-23
 */

class ToolsDynamicManager {
    constructor() {
        this.toolsData = [];
        this.filteredTools = [];
        this.currentPage = 1;
        this.itemsPerPage = 12;
        this.currentCategory = 'all';
        this.currentSort = 'name-asc';
        this.searchQuery = '';
        
        // DOM 元素
        this.elements = {
            toolsGrid: document.getElementById('toolsGrid'),
            searchInput: document.getElementById('searchInput'),
            toolsCount: document.getElementById('toolsCount'),
            filterTags: document.querySelectorAll('.filter-tag'),
            sortButtons: document.querySelectorAll('.sort-btn'),
            pagination: document.getElementById('pagination'),
            loading: document.getElementById('loading'),
            noResults: document.getElementById('noResults')
        };
        
        this.init();
    }
    
    /**
     * 初始化
     */
    async init() {
        console.log('🚀 AI24X 动态工具系统启动...');
        
        // 加载数据
        await this.loadToolsData();
        
        // 绑定事件
        this.bindEvents();
        
        // 初始渲染
        this.renderTools();
        
        console.log('✅ 动态工具系统初始化完成');
    }
    
    /**
     * 加载工具数据
     */
    async loadToolsData() {
        try {
            this.showLoading();
            
            // 从 data/tools-dynamic.json 加载数据
            const response = await fetch('/data/tools-dynamic.json');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.toolsData = data.tools || [];
            
            console.log(`📊 加载了 ${this.toolsData.length} 个工具数据`);
            
        } catch (error) {
            console.error('❌ 加载工具数据失败:', error);
            
            // 使用示例数据作为后备
            this.toolsData = this.getSampleData();
            console.log('⚠️ 使用示例数据作为后备');
            
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * 获取示例数据（后备方案）
     */
    getSampleData() {
        return [
            {
                id: 1,
                name: "ChatGPT",
                description: "OpenAI开发的先进对话AI，支持自然语言对话、代码编写、创意写作等",
                category: "对话AI",
                icon: "fas fa-comments",
                features: ["自然语言对话", "代码编写", "创意写作", "翻译服务"],
                price: "免费/付费",
                url: "https://chat.openai.com",
                demoUrl: "https://chat.openai.com/chat",
                tags: ["对话", "写作", "编程", "AI助手"]
            },
            {
                id: 2,
                name: "Midjourney",
                description: "AI图像生成工具，通过文本描述创建高质量的艺术作品和图像",
                category: "图像生成",
                icon: "fas fa-paint-brush",
                features: ["文本到图像", "艺术风格", "高分辨率", "社区分享"],
                price: "订阅制",
                url: "https://www.midjourney.com",
                demoUrl: "https://www.midjourney.com/showcase",
                tags: ["图像生成", "艺术", "设计", "创意"]
            },
            {
                id: 3,
                name: "GitHub Copilot",
                description: "AI编程助手，在代码编辑器中提供智能代码补全和建议",
                category: "编程工具",
                icon: "fas fa-code",
                features: ["代码补全", "多语言支持", "IDE集成", "智能建议"],
                price: "订阅制",
                url: "https://github.com/features/copilot",
                demoUrl: "https://github.com/features/copilot#try",
                tags: ["编程", "开发", "代码", "IDE"]
            }
        ];
    }
    
    /**
     * 绑定事件
     */
    bindEvents() {
        // 搜索输入
        this.elements.searchInput.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.currentPage = 1;
            this.renderTools();
        });
        
        // 筛选标签
        this.elements.filterTags.forEach(tag => {
            tag.addEventListener('click', (e) => {
                const category = e.target.dataset.category;
                this.setCategory(category);
            });
        });
        
        // 排序按钮
        this.elements.sortButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const sortType = e.target.dataset.sort;
                this.setSort(sortType);
            });
        });
        
        // 分页按钮（事件委托）
        this.elements.pagination.addEventListener('click', (e) => {
            const btn = e.target.closest('.page-btn');
            if (!btn || btn.classList.contains('disabled')) return;
            
            const action = btn.dataset.action;
            this.handlePagination(action);
        });
    }
    
    /**
     * 设置分类筛选
     */
    setCategory(category) {
        this.currentCategory = category;
        this.currentPage = 1;
        
        // 更新标签状态
        this.elements.filterTags.forEach(tag => {
            if (tag.dataset.category === category) {
                tag.classList.add('active');
            } else {
                tag.classList.remove('active');
            }
        });
        
        this.renderTools();
    }
    
    /**
     * 设置排序方式
     */
    setSort(sortType) {
        this.currentSort = sortType;
        
        // 更新按钮状态
        this.elements.sortButtons.forEach(btn => {
            if (btn.dataset.sort === sortType) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        this.renderTools();
    }
    
    /**
     * 处理分页
     */
    handlePagination(action) {
        const totalPages = Math.ceil(this.filteredTools.length / this.itemsPerPage);
        
        switch (action) {
            case 'prev':
                if (this.currentPage > 1) this.currentPage--;
                break;
            case 'next':
                if (this.currentPage < totalPages) this.currentPage++;
                break;
            default:
                const page = parseInt(action);
                if (page >= 1 && page <= totalPages) {
                    this.currentPage = page;
                }
        }
        
        this.renderTools();
        this.scrollToTop();
    }
    
    /**
     * 滚动到顶部
     */
    scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    }
    
    /**
     * 筛选和排序工具
     */
    filterAndSortTools() {
        let filtered = [...this.toolsData];
        
        // 搜索筛选
        if (this.searchQuery) {
            filtered = filtered.filter(tool => {
                return tool.name.toLowerCase().includes(this.searchQuery) ||
                       tool.description.toLowerCase().includes(this.searchQuery) ||
                       tool.category.toLowerCase().includes(this.searchQuery) ||
                       (tool.tags && tool.tags.some(tag => tag.toLowerCase().includes(this.searchQuery)));
            });
        }
        
        // 分类筛选
        if (this.currentCategory !== 'all') {
            filtered = filtered.filter(tool => tool.category === this.currentCategory);
        }
        
        // 排序
        filtered.sort((a, b) => {
            switch (this.currentSort) {
                case 'name-asc':
                    return a.name.localeCompare(b.name);
                case 'name-desc':
                    return b.name.localeCompare(a.name);
                case 'category-asc':
                    return a.category.localeCompare(b.category);
                case 'category-desc':
                    return b.category.localeCompare(a.category);
                default:
                    return 0;
            }
        });
        
        this.filteredTools = filtered;
    }
    
    /**
     * 渲染工具卡片
     */
    renderTools() {
        this.filterAndSortTools();
        
        const totalTools = this.filteredTools.length;
        const totalPages = Math.ceil(totalTools / this.itemsPerPage);
        
        // 更新工具数量显示
        this.elements.toolsCount.innerHTML = `找到 <strong>${totalTools}</strong> 个AI工具`;
        
        // 显示/隐藏无结果状态
        if (totalTools === 0) {
            this.elements.noResults.style.display = 'block';
            this.elements.toolsGrid.innerHTML = '';
            this.elements.pagination.innerHTML = '';
            return;
        } else {
            this.elements.noResults.style.display = 'none';
        }
        
        // 计算分页
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = Math.min(startIndex + this.itemsPerPage, totalTools);
        const pageTools = this.filteredTools.slice(startIndex, endIndex);
        
        // 生成工具卡片HTML
        let toolsHTML = '';
        pageTools.forEach(tool => {
            toolsHTML += this.createToolCardHTML(tool);
        });
        
        this.elements.toolsGrid.innerHTML = toolsHTML;
        
        // 渲染分页
        this.renderPagination(totalPages);
        
        // 绑定工具卡片事件
        this.bindToolCardEvents();
    }
    
    /**
     * 创建工具卡片HTML
     */
    createToolCardHTML(tool) {
        const featuresHTML = tool.features ? tool.features.map(feature => 
            `<li class="feature-item"><i class="fas fa-check"></i> ${feature}</li>`
        ).join('') : '';
        
        const tagsHTML = tool.tags ? tool.tags.map(tag => 
            `<span class="tool-tag">${tag}</span>`
        ).join('') : '';
        
        return `
            <div class="tool-card" data-id="${tool.id}">
                <div class="tool-header">
                    <div class="tool-icon">
                        <i class="${tool.icon || 'fas fa-cube'}"></i>
                    </div>
                    <div>
                        <h3 class="tool-title">${tool.name}</h3>
                        <span class="tool-category">${tool.category}</span>
                    </div>
                </div>
                
                <p class="tool-description">${tool.description}</p>
                
                ${featuresHTML ? `
                <div class="tool-features">
                    <ul class="feature-list">
                        ${featuresHTML}
                    </ul>
                </div>
                ` : ''}
                
                ${tagsHTML ? `
                <div class="tool-tags">
                    ${tagsHTML}
                </div>
                ` : ''}
                
                <div class="tool-footer">
                    <div class="tool-price">${tool.price || '免费'}</div>
                    <div class="tool-actions">
                        ${tool.demoUrl ? `
                        <a href="${tool.demoUrl}" class="btn-demo" target="_blank" rel="noopener">
                            <i class="fas fa-play-circle"></i> 演示
                        </a>
                        ` : ''}
                        <a href="${tool.url}" class="btn-visit" target="_blank" rel="noopener">
                            <i class="fas fa-external-link-alt"></i> 访问
                        </a>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * 渲染分页
     */
    renderPagination(totalPages) {
        if (totalPages <= 1) {
            this.elements.pagination.innerHTML = '';
            return;
        }
        
        let paginationHTML = '';
        
        // 上一页按钮
        const prevDisabled = this.currentPage === 1 ? 'disabled' : '';
        paginationHTML += `
            <button class="page-btn ${prevDisabled}" data-action="prev">
                <i class="fas fa-chevron-left"></i>
            </button>
        `;
        
        // 页码按钮
        const maxVisiblePages = 5;
        let startPage = Math.max(1, this.currentPage - Math.floor(maxVisiblePages / 2));
        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
        
        if (endPage - startPage + 1 < maxVisiblePages) {
            startPage = Math.max(1, endPage - maxVisiblePages + 1);
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === this.currentPage ? 'active' : '';
            paginationHTML += `
                <button class="page-btn ${activeClass}" data-action="${i}">
                    ${i}
                </button>
            `;
        }
        
        // 下一页按钮
        const nextDisabled = this.currentPage === totalPages ? 'disabled' : '';
        paginationHTML += `
            <button class="page-btn ${nextDisabled}" data-action="next">
                <i class="fas fa-chevron-right"></i>
            </button>
        `;
        
        // 页面信息
        const startItem = (this.currentPage - 1) * this.itemsPerPage + 1;
        const endItem = Math.min(this.currentPage * this.itemsPerPage, this.filteredTools.length);
        
        paginationHTML += `
            <div class="page-info">
                显示 ${startItem}-${endItem} / ${this.filteredTools.length}
            </div>
        `;
        
        this.elements.pagination.innerHTML = paginationHTML;
    }
    
    /**
     * 绑定工具卡片事件
     */
    bindToolCardEvents() {
        const toolCards = document.querySelectorAll('.tool-card');
        
        toolCards.forEach(card => {
            // 点击卡片（除了按钮区域）
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.btn-visit') && !e.target.closest('.btn-demo')) {
                    const toolId = card.dataset.id;
                    this.showToolDetail(toolId);
                }
            });
            
            // 悬停效果
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-5px)';
            });
            
            card.addEventListener('mouseleave', () => {
                card.style.transform = 'translateY(0)';
            });
        });
    }
    
    /**
     * 显示工具详情（待实现）
     */
    showToolDetail(toolId) {
        console.log('显示工具详情:', toolId);
        // 这里可以扩展显示模态框或跳转到详情页
        // alert(`查看工具详情: ${toolId}`);
    }
    
    /**
     * 显示加载状态
     */
    showLoading() {
        if (this.elements.loading) {
            this.elements.loading.style.display = 'block';
        }
    }
    
    /**
     * 隐藏加载状态
     */
    hideLoading() {
        if (this.elements.loading) {
            this.elements.loading.style.display = 'none';
        }
    }
    
    /**
     * 获取所有分类
     */
    getAllCategories() {
        const categories = new Set();
        this.toolsData.forEach(tool => {
            categories.add(tool.category);
        });
        return Array.from(categories);
    }
    
    /**
     * 导出数据（用于调试）
     */
    exportData() {
        return {
            totalTools: this.toolsData.length,
            filteredTools: this.filteredTools.length,
            currentPage: this.currentPage,
            currentCategory: this.currentCategory,
            currentSort: this.currentSort,
            searchQuery: this.searchQuery
        };
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.toolsManager = new ToolsDynamicManager();
    
    // 全局导出用于调试
    window.getToolsData = () => window.toolsManager.exportData();
    
    console.log('🎯 AI24X 动态工具页面已就绪');
});

// 添加键盘快捷键支持
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + F 聚焦搜索框
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }
    
    // Esc 清空搜索框
    if (e.key === 'Escape') {
        const searchInput = document.getElementById('searchInput');
        if (searchInput && searchInput.value) {
            searchInput.value = '';
            searchInput.dispatchEvent(new Event('input'));
        }
    }
});