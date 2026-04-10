/**
 * 分享链接系统API - 新版（使用数据库持久化）
 * 提供分享链接生成、管理和统计功能
 */

const crypto = require('crypto');
const db = require('./share-db');

// 用户会话管理（临时实现）
const userSessions = new Map();

// 生成短ID
function generateShortId(length = 8) {
    return crypto.randomBytes(Math.ceil(length / 2))
        .toString('hex')
        .slice(0, length);
}

// 用户认证检查
function authenticateUser(sessionToken) {
    if (!sessionToken) return null;
    return userSessions.get(sessionToken) || null;
}

// 生成分享链接（带用户认证）
function generateShareLink(userId, toolId, customMessage = '', sessionToken = null) {
    const shareId = generateShortId();
    const createdAt = new Date().toISOString();
    
    // 验证用户身份
    let authenticatedUserId = userId;
    if (sessionToken) {
        const user = authenticateUser(sessionToken);
        if (user) {
            authenticatedUserId = user.id;
        }
    }
    
    const shareLink = {
        id: shareId,
        userId: authenticatedUserId,
        toolId,
        customMessage,
        shortUrl: `/s/${shareId}`,
        fullUrl: `http://localhost:3000/s/${shareId}`,
        createdAt,
        expiresAt: null, // 默认永不过期
        isActive: true,
        clickCount: 0,
        registerCount: 0,
        conversionRate: 0,
        lastClickedAt: null,
        // 新增字段
        userAuthenticated: !!sessionToken,
        rewardPoints: 0,
        shareLevel: 1,
        tags: ['ai-tools'],
        privacy: 'public'
    };
    
    // 保存到数据库
    db.shareLinks.set(shareId, shareLink);
    
    // 记录分享行为（用于奖励）
    if (shareLink.userAuthenticated) {
        const rewardPoints = calculateReward(shareLink, 'share');
        updateUserRewards(shareLink.userId, rewardPoints, '创建分享链接');
    }
    
    return shareLink;
}

// 奖励系统
function calculateReward(shareLink, actionType) {
    let points = 0;
    
    switch (actionType) {
        case 'click':
            points = 1; // 每次点击1分
            break;
        case 'register':
            points = 10; // 每次注册10分
            break;
        case 'conversion':
            points = 20; // 每次转化20分
            break;
        case 'share':
            points = 5; // 每次分享5分
            break;
    }
    
    // 根据分享等级加成
    const levelMultiplier = 1 + (shareLink.shareLevel * 0.1);
    points = Math.floor(points * levelMultiplier);
    
    return points;
}

// 更新用户奖励
function updateUserRewards(userId, points, reason = '分享奖励') {
    try {
        const user = db.userRewards.addPoints(userId, points, reason);
        console.log(`用户 ${userId} 获得 ${points} 奖励积分，总计: ${user.totalPoints}`);
        return user;
    } catch (error) {
        console.error('更新用户奖励失败:', error);
        return null;
    }
}

// 记录点击（带奖励）
function recordClick(shareId, ipAddress, userAgent, referrer) {
    console.log(`[DEBUG] recordClick called: shareId=${shareId}`);
    
    const shareLink = db.shareLinks.get(shareId);
    console.log(`[DEBUG] shareLink from DB:`, shareLink);
    
    if (!shareLink || !shareLink.isActive) {
        console.log(`[DEBUG] 分享链接不存在或未激活: ${shareId}`);
        return null;
    }
    
    const clickRecord = {
        id: generateShortId(16),
        shareId,
        ipAddress,
        userAgent,
        referrer,
        clickedAt: new Date().toISOString(),
        country: detectCountry(ipAddress),
        device: detectDevice(userAgent)
    };
    
    // 保存点击记录
    db.shareClicks.add(shareId, clickRecord);
    
    // 更新分享链接统计
    const clicks = db.shareClicks.getByShareId(shareId);
    const conversions = db.shareConversions.getByShareId(shareId);
    
    const updatedShareLink = {
        ...shareLink,
        clickCount: clicks.length,
        lastClickedAt: clickRecord.clickedAt,
        conversionRate: clicks.length > 0 ? 
            (conversions.length / clicks.length * 100).toFixed(2) : 0
    };
    
    db.shareLinks.set(shareId, updatedShareLink);
    
    // 计算奖励（如果用户已认证）
    if (shareLink.userAuthenticated) {
        const rewardPoints = calculateReward(shareLink, 'click');
        updatedShareLink.rewardPoints += rewardPoints;
        db.shareLinks.set(shareId, updatedShareLink);
        updateUserRewards(shareLink.userId, rewardPoints, '分享链接被点击');
    }
    
    return clickRecord;
}

// 记录转化
function recordConversion(shareId, userId) {
    const shareLink = db.shareLinks.get(shareId);
    if (!shareLink) {
        return null;
    }
    
    const conversionRecord = {
        id: generateShortId(16),
        shareId,
        userId,
        convertedAt: new Date().toISOString(),
        conversionType: 'registration'
    };
    
    // 保存转化记录
    db.shareConversions.add(shareId, conversionRecord);
    
    // 更新分享链接统计
    const clicks = db.shareClicks.getByShareId(shareId);
    const conversions = db.shareConversions.getByShareId(shareId);
    
    const updatedShareLink = {
        ...shareLink,
        registerCount: conversions.length,
        conversionRate: clicks.length > 0 ? 
            (conversions.length / clicks.length * 100).toFixed(2) : 0
    };
    
    db.shareLinks.set(shareId, updatedShareLink);
    
    // 计算奖励（如果用户已认证）
    if (shareLink.userAuthenticated) {
        const rewardPoints = calculateReward(shareLink, 'conversion');
        updatedShareLink.rewardPoints += rewardPoints;
        db.shareLinks.set(shareId, updatedShareLink);
        updateUserRewards(shareLink.userId, rewardPoints, '分享链接带来注册');
    }
    
    return conversionRecord;
}

// 获取分享链接信息
function getShareLink(shareId) {
    return db.shareLinks.get(shareId);
}

// 获取分享统计
function getShareStats(shareId) {
    const shareLink = db.shareLinks.get(shareId);
    if (!shareLink) {
        return null;
    }
    
    const clicks = db.shareClicks.getByShareId(shareId);
    const conversions = db.shareConversions.getByShareId(shareId);
    
    // 计算转化率
    const conversionRate = clicks.length > 0 
        ? (conversions.length / clicks.length * 100).toFixed(2)
        : 0;
    
    // 按时间分组统计
    const today = new Date().toISOString().split('T')[0];
    const clicksToday = db.shareClicks.getTodayClicks(shareId).length;
    const conversionsToday = db.shareConversions.getTodayConversions(shareId).length;
    
    // 最近7天趋势
    const last7Days = getLast7DaysTrend(shareId);
    
    return {
        shareId,
        totalClicks: clicks.length,
        totalRegistrations: conversions.length,
        conversionRate: `${conversionRate}%`,
        clicksToday,
        conversionsToday,
        lastClicked: shareLink.lastClickedAt,
        createdAt: shareLink.createdAt,
        rewardPoints: shareLink.rewardPoints,
        shareLevel: shareLink.shareLevel,
        last7DaysTrend: last7Days,
        topReferrers: getTopReferrers(shareId, 5),
        deviceBreakdown: getDeviceBreakdown(shareId)
    };
}

// 获取用户的所有分享链接
function getUserShares(userId) {
    const userShares = db.shareLinks.getByUserId(userId);
    
    return userShares.map(shareLink => {
        const stats = getShareStats(shareLink.id);
        return {
            ...shareLink,
            stats
        };
    });
}

// 删除分享链接
function deleteShareLink(shareId, userId) {
    const shareLink = db.shareLinks.get(shareId);
    if (!shareLink || shareLink.userId !== userId) {
        return false;
    }
    
    // 从所有数据库中删除
    db.shareLinks.delete(shareId);
    
    // 注意：我们保留点击和转化记录用于数据分析
    // 但标记分享链接为已删除
    
    return true;
}

// 辅助函数：检测国家
function detectCountry(ipAddress) {
    // 简化实现，实际应该使用IP地理定位服务
    if (ipAddress.startsWith('192.168.') || ipAddress === '127.0.0.1') {
        return 'CN';
    }
    return 'Unknown';
}

// 辅助函数：检测设备
function detectDevice(userAgent) {
    if (userAgent.includes('Mobile')) {
        return 'mobile';
    } else if (userAgent.includes('Tablet')) {
        return 'tablet';
    } else {
        return 'desktop';
    }
}

// 获取最近7天趋势
function getLast7DaysTrend(shareId) {
    const clicks = db.shareClicks.getByShareId(shareId);
    const conversions = db.shareConversions.getByShareId(shareId);
    
    const trend = {};
    const today = new Date();
    
    for (let i = 6; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);
        const dateStr = date.toISOString().split('T')[0];
        
        const dayClicks = clicks.filter(click => 
            click.clickedAt.startsWith(dateStr)
        ).length;
        
        const dayConversions = conversions.filter(conv => 
            conv.convertedAt.startsWith(dateStr)
        ).length;
        
        trend[dateStr] = {
            clicks: dayClicks,
            conversions: dayConversions,
            conversionRate: dayClicks > 0 ? 
                ((dayConversions / dayClicks) * 100).toFixed(2) : 0
        };
    }
    
    return trend;
}

// 获取Top推荐来源
function getTopReferrers(shareId, limit = 5) {
    const clicks = db.shareClicks.getByShareId(shareId);
    
    const referrerCount = {};
    clicks.forEach(click => {
        const referrer = click.referrer || 'direct';
        referrerCount[referrer] = (referrerCount[referrer] || 0) + 1;
    });
    
    return Object.entries(referrerCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, limit)
        .map(([referrer, count]) => ({ referrer, count }));
}

// 获取设备分布
function getDeviceBreakdown(shareId) {
    const clicks = db.shareClicks.getByShareId(shareId);
    
    const deviceCount = {
        mobile: 0,
        tablet: 0,
        desktop: 0,
        unknown: 0
    };
    
    clicks.forEach(click => {
        const device = click.device || 'unknown';
        deviceCount[device] = (deviceCount[device] || 0) + 1;
    });
    
    const total = clicks.length;
    if (total === 0) return deviceCount;
    
    return {
        mobile: deviceCount.mobile,
        tablet: deviceCount.tablet,
        desktop: deviceCount.desktop,
        unknown: deviceCount.unknown,
        mobilePercent: ((deviceCount.mobile / total) * 100).toFixed(1),
        desktopPercent: ((deviceCount.desktop / total) * 100).toFixed(1)
    };
}

// 获取用户奖励信息
function getUserRewards(userId) {
    try {
        const user = db.userRewards.getUser(userId);
        const history = db.userRewards.getHistory(userId, 20);
        
        return {
            userId,
            totalPoints: user.totalPoints,
            availablePoints: user.availablePoints,
            usedPoints: user.usedPoints,
            level: user.level,
            createdAt: user.createdAt,
            updatedAt: user.updatedAt,
            recentHistory: history
        };
    } catch (error) {
        console.error('获取用户奖励失败:', error);
        return null;
    }
}

// 导出API函数
module.exports = {
    generateShareLink,
    recordClick,
    recordConversion,
    getShareLink,
    getShareStats,
    getUserShares,
    deleteShareLink,
    getUserRewards,
    
    // 测试数据
    getTestData: () => ({
        totalShares: db.shareLinks.getAll().length,
        totalClicks: Object.values(db.shareClicks.data).reduce((sum, clicks) => sum + clicks.length, 0),
        totalConversions: Object.values(db.shareConversions.data).reduce((sum, convs) => sum + convs.length, 0),
        dbStats: {
            shareLinks: db.shareLinks.getAll().length,
            usersWithRewards: Object.keys(db.userRewards.data).length
        }
    })
};