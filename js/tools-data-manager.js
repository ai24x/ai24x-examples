/**
 * AI工具数据管理器
 * 负责加载、管理和搜索AI工具数据
 */

class ToolsDataManager {
    constructor() {
        this.tools = [];
        this.categories = [];
        this.tags = [];
        this.filteredTools = [];
        this.currentCategory = null;
        this.currentSearch = '';
        this.currentSort = 'popularity';
        
        // 初始化
        this.init();
    }
    
    async init() {
        try {
            await this.loadData();
            console.log('AI工具数据加载成功:', this.tools.length, '个工具');
        } catch (error) {
            console.error('加载AI工具数据失败:', error);
            // 使用默认数据
            this.useDefaultData();
        }
    }
    
    async loadData() {
        try {
            const response = await fetch('/data/ai-tools-data.json');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.tools = data.tools || [];
            this.categories = data.categories || [];
            this.tags = data.tags || [];
            
            // 初始化筛选结果
            this.filteredTools = [...this.tools];
            
        } catch (error) {
            console.error('加载JSON数据失败:', error);
            throw error;
        }
    }
    
    useDefaultData() {
        // 简单默认数据
        this.tools = [
            {
                id: 'chatgpt',
                name: 'ChatGPT',
                description: 'OpenAI开发的对话式AI助手',
                category: 'text',
                rating: 4.8,
                icon: 'fas fa-comment-alt'
            },
            {
                id: 'midjourney',
                name: 'Midjourney',
                description: 'AI图像生成工具',
                category: 'image',
                rating: 4.7,
                icon: 'fas fa-paint-brush'
            }
        ];
        this.filteredTools = [...this.tools];
    }
    
    // 搜索工具
    searchTools(query) {
        this.currentSearch = query.toLowerCase().trim();
        this.applyFilters();
        return this.filteredTools;
    }
    
    // 按分类筛选
    filterByCategory(categoryId) {
        this.currentCategory = categoryId;
        this.applyFilters();
        return this.filteredTools;
    }
    
    // 按标签筛选
    filterByTag(tag) {
        this.currentSearch = tag;
        this.applyFilters();
        return this.filteredTools;
    }
    
    // 应用所有筛选条件
    applyFilters() {
        let filtered = [...this.tools];
        
        // 按分类筛选
        if (this.currentCategory) {
            filtered = filtered.filter(tool => 
                tool.category === this.currentCategory || 
                (tool.categories && tool.categories.includes(this.currentCategory))
            );
        }
        
        // 按搜索词筛选
        if (this.currentSearch) {
            const searchTerm = this.currentSearch.toLowerCase();
            filtered = filtered.filter(tool => {
                // 搜索名称
                if (tool.name.toLowerCase().includes(searchTerm)) return true;
                
                // 搜索描述
                if (tool.description && tool.description.toLowerCase().includes(searchTerm)) return true;
                
                // 搜索标签
                if (tool.tags) {
                    const tagMatch = tool.tags.some(tag => 
                        tag.toLowerCase().includes(searchTerm)
                    );
                    if (tagMatch) return true;
                }
                
                // 搜索分类
                if (tool.categories) {
                    const categoryMatch = tool.categories.some(cat => 
                        cat.toLowerCase().includes(searchTerm)
                    );
                    if (categoryMatch) return true;
                }
                
                return false;
            });
        }
        
        // 排序
        filtered = this.sortTools(filtered, this.currentSort);
        
        this.filteredTools = filtered;
        return filtered;
    }
    
    // 排序工具
    sortTools(tools, sortBy) {
        this.currentSort = sortBy;
        
        const sorted = [...tools];
        
        switch (sortBy) {
            case 'name':
                sorted.sort((a, b) => a.name.localeCompare(b.name));
                break;
                
            case 'rating':
                sorted.sort((a, b) => (b.rating || 0) - (a.rating || 0));
                break;
                
            case 'popularity':
                sorted.sort((a, b) => (b.popularity || 0) - (a.popularity || 0));
                break;
                
            case 'updated':
                sorted.sort((a, b) => {
                    const dateA = new Date(a.updated || '2000-01-01');
                    const dateB = new Date(b.updated || '2000-01-01');
                    return dateB - dateA;
                });
                break;
                
            default:
                // 默认按流行度排序
                sorted.sort((a, b) => (b.popularity || 0) - (a.popularity || 0));
        }
        
        return sorted;
    }
    
    // 获取工具详情
    getToolById(id) {
        return this.tools.find(tool => tool.id === id);
    }
    
    // 获取分类详情
    getCategoryById(id) {
        return this.categories.find(cat => cat.id === id);
    }
    
    // 获取所有分类
    getAllCategories() {
        return this.categories;
    }
    
    // 获取所有标签
    getAllTags() {
        return this.tags;
    }
    
    // 获取热门工具
    getPopularTools(limit = 6) {
        return this.tools
            .sort((a, b) => (b.popularity || 0) - (a.popularity || 0))
            .slice(0, limit);
    }
    
    // 获取最新工具
    getRecentTools(limit = 6) {
        return this.tools
            .sort((a, b) => {
                const dateA = new Date(a.updated || '2000-01-01');
                const dateB = new Date(b.updated || '2000-01-01');
                return dateB - dateA;
            })
            .slice(0, limit);
    }
    
    // 获取工具统计
    getStats() {
        return {
            totalTools: this.tools.length,
            totalCategories: this.categories.length,
            totalTags: this.tags.length,
            averageRating: this.tools.length > 0 
                ? (this.tools.reduce((sum, tool) => sum + (tool.rating || 0), 0) / this.tools.length).toFixed(1)
                : 0
        };
    }
    
    // 重置筛选
    resetFilters() {
        this.currentCategory = null;
        this.currentSearch = '';
        this.currentSort = 'popularity';
        this.filteredTools = [...this.tools];
        return this.filteredTools;
    }
}

// 创建全局实例
window.toolsDataManager = new ToolsDataManager();

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToolsDataManager;
}