/**
 * 国际化翻译文件
 * 支持中英文切换
 */

const translations = {
    // 通用文本
    common: {
        zh: {
            // 导航
            home: "首页",
            tools: "AI工具库",
            share: "分享",
            login: "登录",
            signup: "注册",
            profile: "个人中心",
            logout: "退出登录",
            
            // 按钮
            learnMore: "了解更多",
            getStarted: "开始使用",
            tryNow: "立即体验",
            viewAll: "查看全部",
            download: "下载",
            shareNow: "立即分享",
            copyLink: "复制链接",
            
            // 表单
            email: "邮箱地址",
            password: "密码",
            confirmPassword: "确认密码",
            username: "用户名",
            phone: "手机号",
            submit: "提交",
            cancel: "取消",
            save: "保存",
            delete: "删除",
            edit: "编辑",
            
            // 消息
            loading: "加载中...",
            success: "操作成功",
            error: "操作失败",
            warning: "警告",
            info: "提示",
            confirm: "确认",
            
            // 时间
            justNow: "刚刚",
            minutesAgo: "分钟前",
            hoursAgo: "小时前",
            daysAgo: "天前",
            
            // 首页内容
            heroTitle: "AI24X - 您的AI工具平台",
            heroSubtitle: "发现、使用和分享最好的AI工具",
            heroDescription: "我们汇集了最先进的AI工具，帮助您提高工作效率，创造更多价值。",
            featuredTools: "精选工具",
            trendingNow: "热门趋势",
            newArrivals: "最新上架",
            topRated: "最高评分",
            mostShared: "最多分享",
            toolCategories: "工具分类",
            productivity: "生产力",
            creativity: "创造力",
            analysis: "分析",
            automation: "自动化",
            education: "教育",
            entertainment: "娱乐",
            seeAllCategories: "查看全部分类",
            howItWorks: "如何使用",
            step1Title: "发现工具",
            step1Desc: "浏览我们精心挑选的AI工具库",
            step2Title: "注册账户",
            step2Desc: "创建账户以保存收藏和获取个性化推荐",
            step3Title: "分享收益",
            step3Desc: "分享工具链接，获得奖励积分",
            joinCommunity: "加入社区",
            communityDesc: "与数千名AI爱好者一起探索人工智能的无限可能",
            startExploring: "开始探索",
            alreadyHaveAccount: "已有账户？",
            loginHere: "立即登录",
            trustedBy: "受信任于",
            usersWorldwide: "全球用户",
            toolsAvailable: "可用工具",
            positiveReviews: "积极评价",
            successStories: "成功案例",
            testimonial1: "AI24X彻底改变了我的工作流程！",
            testimonial1Author: "张伟，产品经理",
            testimonial2: "在这里找到了最适合我的AI写作助手",
            testimonial2Author: "李娜，内容创作者",
            testimonial3: "分享功能让我额外获得了不少收入",
            testimonial3Author: "王明，自由职业者",
            footerAbout: "关于我们",
            footerContact: "联系我们",
            footerPrivacy: "隐私政策",
            footerTerms: "服务条款",
            footerBlog: "博客",
            footerHelp: "帮助中心",
            footerNewsletter: "订阅新闻",
            newsletterPlaceholder: "输入您的邮箱",
            subscribe: "订阅",
            copyright: "© 2026 AI24X. 保留所有权利。",
            madeWith: "用心制作",
            hoursAgo: "小时前",
            daysAgo: "天前",
            today: "今天",
            yesterday: "昨天",
            thisWeek: "本周",
            thisMonth: "本月"
        },
        en: {
            // Navigation
            home: "Home",
            tools: "AI Tools",
            share: "Share",
            login: "Login",
            signup: "Sign Up",
            profile: "Profile",
            logout: "Logout",
            
            // Buttons
            learnMore: "Learn More",
            getStarted: "Get Started",
            tryNow: "Try Now",
            viewAll: "View All",
            download: "Download",
            shareNow: "Share Now",
            copyLink: "Copy Link",
            
            // Forms
            email: "Email Address",
            password: "Password",
            confirmPassword: "Confirm Password",
            username: "Username",
            phone: "Phone Number",
            submit: "Submit",
            cancel: "Cancel",
            save: "Save",
            delete: "Delete",
            edit: "Edit",
            
            // Messages
            loading: "Loading...",
            success: "Success",
            error: "Error",
            warning: "Warning",
            info: "Info",
            confirm: "Confirm",
            
            // Time
            justNow: "Just now",
            minutesAgo: "minutes ago",
            hoursAgo: "hours ago",
            daysAgo: "days ago",
            today: "Today",
            yesterday: "Yesterday",
            thisWeek: "This week",
            thisMonth: "This month"
        }
    },
    
    // 首页内容
    home: {
        zh: {
            heroTitle: "探索人工智能的未来",
            heroSubtitle: "AI24X为您提供最先进的AI工具和解决方案",
            featuresTitle: "核心功能",
            feature1Title: "智能AI工具库",
            feature1Desc: "超过100个精心筛选的AI工具，涵盖各个领域",
            feature2Title: "个性化推荐",
            feature2Desc: "根据您的需求智能推荐最适合的AI工具",
            feature3Title: "社区分享",
            feature3Desc: "与全球AI爱好者交流经验和发现",
            ctaTitle: "立即加入AI24X社区",
            ctaSubtitle: "免费注册，发现无限可能"
        },
        en: {
            heroTitle: "Explore the Future of AI",
            heroSubtitle: "AI24X provides cutting-edge AI tools and solutions",
            featuresTitle: "Core Features",
            feature1Title: "Smart AI Tool Library",
            feature1Desc: "Over 100 carefully selected AI tools across various domains",
            feature2Title: "Personalized Recommendations",
            feature2Desc: "Intelligently recommends the most suitable AI tools for your needs",
            feature3Title: "Community Sharing",
            feature3Desc: "Exchange experiences and discoveries with AI enthusiasts worldwide",
            ctaTitle: "Join the AI24X Community Now",
            ctaSubtitle: "Free registration, discover unlimited possibilities"
        }
    },
    
    // 工具库页面
    tools: {
        zh: {
            pageTitle: "AI工具库",
            searchPlaceholder: "搜索AI工具...",
            filterAll: "全部",
            filterFree: "免费",
            filterPaid: "付费",
            filterNew: "最新",
            filterPopular: "热门",
            sortDefault: "默认排序",
            sortName: "按名称",
            sortRating: "按评分",
            sortPopular: "按热度",
            toolCardTry: "立即体验",
            toolCardDetails: "查看详情",
            noResults: "没有找到相关工具",
            loadingTools: "正在加载工具..."
        },
        en: {
            pageTitle: "AI Tools Library",
            searchPlaceholder: "Search AI tools...",
            filterAll: "All",
            filterFree: "Free",
            filterPaid: "Paid",
            filterNew: "New",
            filterPopular: "Popular",
            sortDefault: "Default",
            sortName: "By Name",
            sortRating: "By Rating",
            sortPopular: "By Popularity",
            toolCardTry: "Try Now",
            toolCardDetails: "View Details",
            noResults: "No tools found",
            loadingTools: "Loading tools..."
        }
    },
    
    // 分享页面
    share: {
        zh: {
            pageTitle: "分享AI工具",
            shareMessage: "我发现这个AI工具非常实用，推荐给你！",
            clickCount: "点击次数",
            registerCount: "注册人数",
            conversionRate: "转化率",
            sharerRank: "分享者排名",
            copySuccess: "链接已复制到剪贴板",
            shareWechat: "分享到微信",
            shareQQ: "分享到QQ",
            shareWeibo: "分享到微博",
            registerCTA: "立即注册AI24X，发现更多AI工具",
            registerDesc: "加入AI24X社区，获取独家AI工具推荐，参与工具评测，与AI爱好者交流经验。",
            freeRegister: "免费注册",
            footerNote: "本链接由AI24X分享系统生成，点击统计将帮助改进推荐算法"
        },
        en: {
            pageTitle: "Share AI Tool",
            shareMessage: "I found this AI tool very useful, recommending it to you!",
            clickCount: "Click Count",
            registerCount: "Registrations",
            conversionRate: "Conversion Rate",
            sharerRank: "Sharer Rank",
            copySuccess: "Link copied to clipboard",
            shareWechat: "Share to WeChat",
            shareQQ: "Share to QQ",
            shareWeibo: "Share to Weibo",
            registerCTA: "Register for AI24X now, discover more AI tools",
            registerDesc: "Join the AI24X community, get exclusive AI tool recommendations, participate in tool reviews, and exchange experiences with AI enthusiasts.",
            freeRegister: "Free Registration",
            footerNote: "This link is generated by the AI24X sharing system, click statistics will help improve recommendation algorithms"
        }
    },
    
    // 注册/登录页面
    auth: {
        zh: {
            loginTitle: "登录AI24X",
            signupTitle: "注册AI24X账户",
            emailRequired: "请输入邮箱地址",
            passwordRequired: "请输入密码",
            passwordMinLength: "密码至少6个字符",
            passwordsNotMatch: "两次输入的密码不一致",
            rememberMe: "记住我",
            forgotPassword: "忘记密码？",
            noAccount: "还没有账户？",
            haveAccount: "已有账户？",
            createAccount: "创建账户",
            loginNow: "立即登录",
            orLoginWith: "或使用以下方式登录",
            privacyAgreement: "注册即表示您同意我们的",
            termsOfService: "服务条款",
            and: "和",
            privacyPolicy: "隐私政策",
            loginSuccess: "登录成功",
            signupSuccess: "注册成功，欢迎加入AI24X！"
        },
        en: {
            loginTitle: "Login to AI24X",
            signupTitle: "Create AI24X Account",
            emailRequired: "Please enter email address",
            passwordRequired: "Please enter password",
            passwordMinLength: "Password must be at least 6 characters",
            passwordsNotMatch: "Passwords do not match",
            rememberMe: "Remember me",
            forgotPassword: "Forgot password?",
            noAccount: "Don't have an account?",
            haveAccount: "Already have an account?",
            createAccount: "Create Account",
            loginNow: "Login Now",
            orLoginWith: "Or login with",
            privacyAgreement: "By registering, you agree to our",
            termsOfService: "Terms of Service",
            and: "and",
            privacyPolicy: "Privacy Policy",
            loginSuccess: "Login successful",
            signupSuccess: "Registration successful, welcome to AI24X!"
        }
    },
    
    // 裂变系统
    fission: {
        zh: {
            inviteCode: "邀请码",
            generateInvite: "生成邀请码",
            myInvites: "我的邀请码",
            inviteStats: "邀请统计",
            totalInvites: "总邀请数",
            successfulInvites: "成功邀请",
            conversionRate: "转化率",
            totalRewards: "总奖励",
            availablePoints: "可用积分",
            level: "等级",
            nextLevel: "下一等级",
            pointsNeeded: "还需积分",
            leaderboard: "排行榜",
            rank: "排名",
            user: "用户",
            points: "积分",
            invites: "邀请",
            rewards: "奖励",
            copyInviteLink: "复制邀请链接",
            inviteFriends: "邀请好友",
            earnRewards: "赚取奖励",
            rewardDesc: "邀请好友注册，双方都能获得奖励积分"
        },
        en: {
            inviteCode: "Invite Code",
            generateInvite: "Generate Invite Code",
            myInvites: "My Invite Codes",
            inviteStats: "Invite Statistics",
            totalInvites: "Total Invites",
            successfulInvites: "Successful Invites",
            conversionRate: "Conversion Rate",
            totalRewards: "Total Rewards",
            availablePoints: "Available Points",
            level: "Level",
            nextLevel: "Next Level",
            pointsNeeded: "Points Needed",
            leaderboard: "Leaderboard",
            rank: "Rank",
            user: "User",
            points: "Points",
            invites: "Invites",
            rewards: "Rewards",
            copyInviteLink: "Copy Invite Link",
            inviteFriends: "Invite Friends",
            earnRewards: "Earn Rewards",
            rewardDesc: "Invite friends to register, both parties can earn reward points"
        }
    }
};

// 导出翻译函数
function getTranslation(key, lang = 'zh') {
    const keys = key.split('.');
    let current = translations;
    
    for (const k of keys) {
        if (current && current[k]) {
            current = current[k];
        } else {
            return key; // 如果找不到翻译，返回原键名
        }
    }
    
    return current[lang] || current['zh'] || key;
}

// 内存存储语言偏好（服务器端）
const languagePreferences = new Map();

// 导出当前语言设置
function getCurrentLanguage() {
    // 服务器端使用内存存储，浏览器端使用localStorage
    // 这里返回默认语言，实际语言由中间件从请求中获取
    return 'zh';
}

function setCurrentLanguage(lang) {
    // 服务器端记录日志，实际设置由中间件处理
    console.log(`[i18n] 设置语言偏好: ${lang}`);
    return lang;
}

// 导出
module.exports = {
    translations,
    getTranslation,
    getCurrentLanguage,
    setCurrentLanguage
};