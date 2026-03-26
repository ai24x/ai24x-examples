/**
 * 分享链接系统API
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
        shareLevel: 1
    };
    
    // 保存到数据库
    db.shareLinks.set(shareId, shareLink);
    
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
    const shareLink = db.shareLinks.get(shareId);
    if (!shareLink || !shareLink.isActive) {
        return null;
    }
    
    const clickRecord = {
        id: generateShortId(16),
        shareId,
        ipAddress,
        userAgent,
        referrer,
        clickedAt: new Date().toISOString()
    };
    
    // 更新分享链接统计
    shareLink.clickCount++;
    shareLink.lastClickedAt = clickRecord.clickedAt;
    
    // 计算转化率
    const conversions = shareConversionsDB.get(shareId) || [];
    shareLink.conversionRate = shareLink.clickCount > 0 ? 
        (conversions.length / shareLink.clickCount * 100).toFixed(2) : 0;
    
    // 计算奖励（如果用户已认证）
    if (shareLink.userAuthenticated) {
        const rewardPoints = calculateReward(shareLink, 'click');
        shareLink.rewardPoints += rewardPoints;
        updateUserRewards(shareLink.userId, rewardPoints);
    }
    
    shareLinksDB.set(shareId, shareLink);
    
    // 记录点击
    const clicks = shareClicksDB.get(shareId) || [];
    clicks.push(clickRecord);
    shareClicksDB.set(shareId, clicks);
    
    return clickRecord;
}

// 记录转化
function recordConversion(shareId, userId) {
    const shareLink = shareLinksDB.get(shareId);
    if (!shareLink) {
        return null;
    }
    
    const conversionRecord = {
        id: generateShortId(16),
        shareId,
        userId,
        convertedAt: new Date().toISOString()
    };
    
    // 更新分享链接统计
    shareLink.registerCount++;
    shareLinksDB.set(shareId, shareLink);
    
    // 记录转化
    const conversions = shareConversionsDB.get(shareId) || [];
    conversions.push(conversionRecord);
    shareConversionsDB.set(shareId, conversions);
    
    return conversionRecord;
}

// 获取分享链接信息
function getShareLink(shareId) {
    return shareLinksDB.get(shareId) || null;
}

// 获取分享统计
function getShareStats(shareId) {
    const shareLink = shareLinksDB.get(shareId);
    if (!shareLink) {
        return null;
    }
    
    const clicks = shareClicksDB.get(shareId) || [];
    const conversions = shareConversionsDB.get(shareId) || [];
    
    // 计算转化率
    const conversionRate = shareLink.clickCount > 0 
        ? (shareLink.registerCount / shareLink.clickCount * 100).toFixed(2)
        : 0;
    
    // 按时间分组统计
    const today = new Date().toISOString().split('T')[0];
    const clicksToday = clicks.filter(click => 
        click.clickedAt.startsWith(today)
    ).length;
    
    const conversionsToday = conversions.filter(conv => 
        conv.convertedAt.startsWith(today)
    ).length;
    
    return {
        shareId,
        totalClicks: shareLink.clickCount,
        totalRegistrations: shareLink.registerCount,
        conversionRate: `${conversionRate}%`,
        clicksToday,
        conversionsToday,
        lastClicked: shareLink.lastClickedAt,
        createdAt: shareLink.createdAt
    };
}

// 获取用户的所有分享链接
function getUserShares(userId) {
    const userShares = [];
    for (const [shareId, shareLink] of shareLinksDB) {
        if (shareLink.userId === userId) {
            const stats = getShareStats(shareId);
            userShares.push({
                ...shareLink,
                stats
            });
        }
    }
    return userShares;
}

// 删除分享链接
function deleteShareLink(shareId, userId) {
    const shareLink = shareLinksDB.get(shareId);
    if (!shareLink || shareLink.userId !== userId) {
        return false;
    }
    
    shareLinksDB.delete(shareId);
    shareClicksDB.delete(shareId);
    shareConversionsDB.delete(shareId);
    
    return true;
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
    
    // 测试数据
    getTestData: () => ({
        shareLinks: Array.from(shareLinksDB.values()),
        totalShares: shareLinksDB.size
    })
};