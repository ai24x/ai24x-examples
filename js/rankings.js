// 实时排行页面JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // 初始化排行榜数据
    initRankings();
    
    // 绑定时间筛选器事件
    bindFilterEvents();
    
    // 更新最后更新时间
    updateLastUpdateTime();
    
    // 模拟实时更新（每5分钟更新一次）
    setInterval(updateRankings, 5 * 60 * 1000);
});

// 初始化排行榜数据
function initRankings() {
    // 综合排行榜数据
    const overallRankings = [
        {
            rank: 1,
            name: "ChatGPT-4",
            category: "对话助手",
            icon: "fas fa-comment-alt",
            trend: "stable",
            score: 98.7,
            change: "→",
            changeType: "stable",
            description: "OpenAI最新旗舰模型，多模态能力强大"
        },
        {
            rank: 2,
            name: "Midjourney v6",
            category: "AI绘画",
            icon: "fas fa-paint-brush",
            trend: "rising",
            score: 95.2,
            change: "↑1",
            changeType: "up",
            description: "最先进的AI绘画工具，艺术创作能力卓越"
        },
        {
            rank: 3,
            name: "GitHub Copilot",
            category: "编程工具",
            icon: "fas fa-code",
            trend: "stable",
            score: 92.8,
            change: "↓1",
            changeType: "down",
            description: "AI编程助手，支持多种编程语言"
        },
        {
            rank: 4,
            name: "Claude 3.5 Sonnet",
            category: "对话助手",
            icon: "fas fa-brain",
            trend: "rising",
            score: 90.5,
            change: "↑2",
            changeType: "up",
            description: "Anthropic最新模型，推理能力强大"
        },
        {
            rank: 5,
            name: "Stable Diffusion 3",
            category: "AI绘画",
            icon: "fas fa-palette",
            trend: "rising",
            score: 88.3,
            change: "↑1",
            changeType: "up",
            description: "开源AI绘画模型，社区活跃"
        },
        {
            rank: 6,
            name: "OpenClaw",
            category: "AI助手",
            icon: "fas fa-crab",
            trend: "rising",
            score: 85.7,
            change: "↑3",
            changeType: "up",
            description: "全能AI助手，支持多种任务"
        },
        {
            rank: 7,
            name: "Notion AI",
            category: "办公工具",
            icon: "fas fa-sticky-note",
            trend: "stable",
            score: 83.2,
            change: "→",
            changeType: "stable",
            description: "智能笔记和文档助手"
        },
        {
            rank: 8,
            name: "ElevenLabs",
            category: "语音合成",
            icon: "fas fa-microphone-alt",
            trend: "rising",
            score: 80.9,
            change: "↑2",
            changeType: "up",
            description: "高质量的AI语音合成工具"
        },
        {
            rank: 9,
            name: "Runway ML",
            category: "视频生成",
            icon: "fas fa-video",
            trend: "rising",
            score: 78.4,
            change: "↑1",
            changeType: "up",
            description: "AI视频生成和编辑平台"
        },
        {
            rank: 10,
            name: "Grammarly",
            category: "写作助手",
            icon: "fas fa-spell-check",
            trend: "stable",
            score: 76.1,
            change: "↓2",
            changeType: "down",
            description: "AI写作和语法检查工具"
        }
    ];

    // 分类排行榜数据
    const categoryRankings = {
        painting: [
            { rank: 1, name: "Midjourney v6", score: 95.2 },
            { rank: 2, name: "Stable Diffusion 3", score: 88.3 },
            { rank: 3, name: "DALL-E 3", score: 82.5 },
            { rank: 4, name: "Leonardo AI", score: 78.9 },
            { rank: 5, name: "Adobe Firefly", score: 75.4 }
        ],
        chat: [
            { rank: 1, name: "ChatGPT-4", score: 98.7 },
            { rank: 2, name: "Claude 3.5 Sonnet", score: 90.5 },
            { rank: 3, name: "Gemini Pro", score: 85.2 },
            { rank: 4, name: "DeepSeek", score: 82.8 },
            { rank: 5, name: "文心一言", score: 79.3 }
        ],
        coding: [
            { rank: 1, name: "GitHub Copilot", score: 92.8 },
            { rank: 2, name: "Cursor", score: 86.4 },
            { rank: 3, name: "Codeium", score: 83.7 },
            { rank: 4, name: "Tabnine", score: 80.2 },
            { rank: 5, name: "Amazon CodeWhisperer", score: 77.5 }
        ],
        video: [
            { rank: 1, name: "Runway ML", score: 78.4 },
            { rank: 2, name: "Pika Labs", score: 75.8 },
            { rank: 3, name: "Sora", score: 73.2 },
            { rank: 4, name: "Luma Dream Machine", score: 70.5 },
            { rank: 5, name: "Kaiber", score: 68.9 }
        ],
        writing: [
            { rank: 1, name: "Grammarly", score: 76.1 },
            { rank: 2, name: "Jasper AI", score: 72.8 },
            { rank: 3, name: "Copy.ai", score: 69.5 },
            { rank: 4, name: "Writesonic", score: 66.3 },
            { rank: 5, name: "Rytr", score: 63.7 }
        ],
        music: [
            { rank: 1, name: "Suno AI", score: 74.2 },
            { rank: 2, name: "AIVA", score: 71.5 },
            { rank: 3, name: "Amper Music", score: 68.9 },
            { rank: 4, name: "Boomy", score: 65.4 },
            { rank: 5, name: "Soundraw", score: 62.8 }
        ]
    };

    // 渲染综合排行榜
    renderOverallRanking(overallRankings);
    
    // 渲染分类排行榜
    renderCategoryRankings(categoryRankings);
}

// 渲染综合排行榜
function renderOverallRanking(rankings) {
    const container = document.getElementById('overallRanking');
    if (!container) return;
    
    container.innerHTML = '';
    
    rankings.forEach(item => {
        const rankingItem = document.createElement('div');
        rankingItem.className = `ranking-item ${item.rank <= 3 ? 'top-3' : ''}`;
        
        rankingItem.innerHTML = `
            <div class="rank-col ${item.rank <= 3 ? `top-${item.rank}` : ''}">
                ${item.rank}
            </div>
            <div class="tool-col">
                <div class="tool-icon">
                    <i class="${item.icon}"></i>
                </div>
                <div class="tool-info">
                    <div class="tool-name">${item.name}</div>
                    <div class="tool-category">${item.category}</div>
                </div>
            </div>
            <div class="trend-col ${item.trend}">
                <i class="fas fa-${item.trend === 'rising' ? 'arrow-up' : item.trend === 'falling' ? 'arrow-down' : 'minus'}"></i>
                ${item.trend === 'rising' ? '上升' : item.trend === 'falling' ? '下降' : '稳定'}
            </div>
            <div class="score-col">${item.score}</div>
            <div class="change-col ${item.changeType}">
                ${item.change}
            </div>
        `;
        
        // 添加点击事件
        rankingItem.addEventListener('click', () => {
            showToolDetail(item);
        });
        
        container.appendChild(rankingItem);
    });
}

// 渲染分类排行榜
function renderCategoryRankings(categories) {
    // 渲染绘画工具榜
    renderCategoryList('paintingRanking', categories.painting);
    
    // 渲染对话助手榜
    renderCategoryList('chatRanking', categories.chat);
    
    // 渲染编程工具榜
    renderCategoryList('codingRanking', categories.coding);
    
    // 渲染视频工具榜
    renderCategoryList('videoRanking', categories.video);
    
    // 渲染写作工具榜
    renderCategoryList('writingRanking', categories.writing);
    
    // 渲染音乐工具榜
    renderCategoryList('musicRanking', categories.music);
}

// 渲染单个分类列表
function renderCategoryList(containerId, items) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = '';
    
    items.forEach(item => {
        const categoryItem = document.createElement('div');
        categoryItem.className = `category-item ${item.rank <= 3 ? 'top-3' : ''}`;
        
        categoryItem.innerHTML = `
            <div class="category-rank ${item.rank <= 3 ? 'top-3' : ''}">
                ${item.rank}
            </div>
            <div class="category-tool">
                <div class="category-tool-name">${item.name}</div>
                <div class="category-tool-score">热度: ${item.score}</div>
            </div>
        `;
        
        container.appendChild(categoryItem);
    });
}

// 绑定时间筛选器事件
function bindFilterEvents() {
    const filterButtons = document.querySelectorAll('.filter-btn');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 移除所有按钮的active类
            filterButtons.forEach(btn => btn.classList.remove('active'));
            
            // 给当前点击的按钮添加active类
            this.classList.add('active');
            
            // 根据筛选条件更新排行榜
            const period = this.dataset.period;
            updateRankingsByPeriod(period);
        });
    });
}

// 根据时间段更新排行榜
function updateRankingsByPeriod(period) {
    // 这里可以添加根据时间段筛选数据的逻辑
    // 目前只是模拟更新
    console.log(`更新 ${period} 排行榜数据`);
    
    // 模拟数据更新
    const overallRanking = document.querySelectorAll('.ranking-item');
    overallRanking.forEach((item, index) => {
        // 随机更新一些数据
        if (Math.random() > 0.7) {
            const scoreElement = item.querySelector('.score-col');
            if (scoreElement) {
                const currentScore = parseFloat(scoreElement.textContent);
                const newScore = currentScore + (Math.random() * 2 - 1);
                scoreElement.textContent = newScore.toFixed(1);
            }
        }
    });
}

// 显示工具详情
function showToolDetail(tool) {
    // 这里可以添加显示工具详情的逻辑
    // 例如打开模态框或跳转到详情页
    console.log('显示工具详情:', tool);
    
    // 简单提示
    alert(`查看 ${tool.name} 详情\n\n${tool.description}\n\n热度指数: ${tool.score}`);
}

// 更新最后更新时间
function updateLastUpdateTime() {
    const updateElement = document.getElementById('lastUpdateTime');
    if (!updateElement) return;
    
    const now = new Date();
    const timeString = now.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    updateElement.textContent = timeString;
}

// 更新排行榜数据
function updateRankings() {
    console.log('自动更新排行榜数据...');
    
    // 更新最后更新时间
    updateLastUpdateTime();
    
    // 模拟数据更新
    const overallRanking = document.querySelectorAll('.ranking-item');
    overallRanking.forEach((item, index) => {
        // 随机更新一些数据
        if (Math.random() > 0.5) {
            const scoreElement = item.querySelector('.score-col');
            if (scoreElement) {
                const currentScore = parseFloat(scoreElement.textContent);
                const change = (Math.random() * 0.5 - 0.25); // -0.25到+0.25的随机变化
                const newScore = Math.max(0, Math.min(100, currentScore + change));
                scoreElement.textContent = newScore.toFixed(1);
                
                // 更新趋势
                const trendElement = item.querySelector('.trend-col');
                if (trendElement) {
                    if (change > 0.1) {
                        trendElement.className = 'trend-col rising';
                        trendElement.innerHTML = '<i class="fas fa-arrow-up"></i> 上升';
                    } else if (change < -0.1) {
                        trendElement.className = 'trend-col falling';
                        trendElement.innerHTML = '<i class="fas fa-arrow-down"></i> 下降';
                    } else {
                        trendElement.className = 'trend-col stable';
                        trendElement.innerHTML = '<i class="fas fa-minus"></i> 稳定';
                    }
                }
            }
        }
    });
    
    // 添加更新动画
    const rankingContainer = document.querySelector('.rankings-container');
    if (rankingContainer) {
        rankingContainer.style.opacity = '0.8';
        setTimeout(() => {
            rankingContainer.style.opacity = '1';
        }, 300);
    }
}

// 页面访问统计
function updatePageStats() {
    // 模拟今日访问量
    const todayVisitsElement = document.getElementById('todayVisits');
    if (todayVisitsElement) {
        const baseVisits = 1234;
        const randomIncrement = Math.floor(Math.random() * 50);
        todayVisitsElement.textContent = (baseVisits + randomIncrement).toLocaleString();
    }
    
    // 模拟总工具数
    const totalToolsElement = document.getElementById('totalTools');
    if (totalToolsElement) {
        totalToolsElement.textContent = '156';
    }
}

// 初始化页面统计
updatePageStats();