/**
 * 裂变系统API
 * 提供邀请码生成、推荐关系管理、裂变奖励等功能
 */

const db = require('./fission-db');
const crypto = require('crypto');

// 生成邀请码
function generateInvitationCode(userId, options = {}) {
    const {
        maxUses = 10,
        expiresInDays = 30,
        customCode = null
    } = options;
    
    let expiresAt = null;
    if (expiresInDays > 0) {
        const date = new Date();
        date.setDate(date.getDate() + expiresInDays);
        expiresAt = date.toISOString();
    }
    
    const invitation = db.invitationCodes.create(
        userId, 
        customCode, 
        maxUses, 
        expiresAt
    );
    
    // 记录用户活动
    db.userLevels.addExperience(userId, 10, '生成邀请码');
    
    return invitation;
}

// 使用邀请码注册
function useInvitationCode(code, newUserId) {
    const result = db.invitationCodes.use(code, newUserId);
    
    if (!result.success) {
        return result;
    }
    
    const { invitation, inviterId } = result;
    
    // 创建推荐关系
    const relation = db.referralRelations.create(
        inviterId,
        newUserId,
        code,
        'direct'
    );
    
    // 给邀请者奖励
    const inviterReward = calculateInvitationReward(invitation, 'direct');
    db.fissionRewards.award(
        inviterId,
        inviterReward.points,
        `邀请新用户 ${newUserId}`,
        relation.id
    );
    
    // 更新邀请码奖励点数
    invitation.rewardPoints += inviterReward.points;
    db.invitationCodes.data[code] = invitation;
    db.invitationCodes.save();
    
    // 给邀请者加经验
    db.userLevels.addExperience(inviterId, 20, '成功邀请新用户');
    
    // 检查二级推荐（如果新用户也有邀请者）
    checkSecondaryReferral(newUserId, inviterId);
    
    return {
        success: true,
        invitation,
        relation,
        reward: inviterReward,
        message: `成功使用邀请码，邀请者获得 ${inviterReward.points} 积分`
    };
}

// 检查二级推荐
function checkSecondaryReferral(newUserId, directInviterId) {
    // 查找新用户的直接邀请者（如果有）
    const newUserRelations = db.referralRelations.getByNewUser(newUserId);
    const directRelation = newUserRelations.find(rel => rel.relationship === 'direct');
    
    if (!directRelation) return null;
    
    const secondaryInviterId = directRelation.inviterId;
    
    // 避免循环推荐
    if (secondaryInviterId === directInviterId) return null;
    
    // 创建二级推荐关系
    const secondaryRelation = db.referralRelations.create(
        secondaryInviterId,
        newUserId,
        directRelation.invitationCode,
        'indirect'
    );
    
    // 给二级邀请者奖励（较少）
    const secondaryReward = calculateInvitationReward(null, 'indirect');
    db.fissionRewards.award(
        secondaryInviterId,
        secondaryReward.points,
        `二级推荐用户 ${newUserId}`,
        secondaryRelation.id
    );
    
    // 给二级邀请者加经验
    db.userLevels.addExperience(secondaryInviterId, 5, '二级推荐奖励');
    
    return {
        secondaryInviterId,
        relation: secondaryRelation,
        reward: secondaryReward
    };
}

// 计算邀请奖励
function calculateInvitationReward(invitation, level) {
    let basePoints = 0;
    let multiplier = 1.0;
    
    if (level === 'direct') {
        basePoints = 50; // 直接邀请基础奖励
        
        // 根据邀请码等级加成
        if (invitation) {
            multiplier = 1 + (invitation.level * 0.1);
        }
    } else if (level === 'indirect') {
        basePoints = 10; // 二级邀请基础奖励
    }
    
    // 随机波动 ±10%
    const randomFactor = 0.9 + Math.random() * 0.2;
    const points = Math.floor(basePoints * multiplier * randomFactor);
    
    return {
        points,
        basePoints,
        multiplier: multiplier.toFixed(2),
        level
    };
}

// 获取用户邀请码列表
function getUserInvitationCodes(userId) {
    const codes = db.invitationCodes.getUserCodes(userId);
    
    return codes.map(code => {
        const stats = db.invitationCodes.getStats(code.code);
        return {
            ...code,
            stats
        };
    });
}

// 获取用户推荐网络
function getUserReferralNetwork(userId, depth = 2) {
    const network = {
        userId,
        directReferees: [],
        indirectReferees: [],
        networkStats: db.referralRelations.getNetworkStats(userId),
        invitationChain: db.referralRelations.getInvitationChain(userId, depth)
    };
    
    // 获取直接推荐
    const directRelations = db.referralRelations.getByInviter(userId);
    network.directReferees = directRelations.map(relation => {
        const userRewards = db.fissionRewards.getUserRewards(relation.newUserId, 5);
        return {
            newUserId: relation.newUserId,
            relationId: relation.id,
            createdAt: relation.createdAt,
            rewardStatus: relation.rewardStatus,
            rewardPoints: relation.rewardPoints,
            recentRewards: userRewards
        };
    });
    
    // 获取间接推荐（二级）
    directRelations.forEach(directRel => {
        const indirectRelations = db.referralRelations.getByInviter(directRel.newUserId);
        indirectRelations.forEach(indirectRel => {
            network.indirectReferees.push({
                newUserId: indirectRel.newUserId,
                directReferee: directRel.newUserId,
                relationId: indirectRel.id,
                createdAt: indirectRel.createdAt,
                rewardStatus: indirectRel.rewardStatus
            });
        });
    });
    
    return network;
}

// 获取用户裂变奖励
function getUserFissionRewards(userId) {
    const rewards = db.fissionRewards.getUserRewards(userId);
    const totalPoints = db.fissionRewards.getTotalPoints(userId);
    const userLevel = db.userLevels.getUser(userId);
    
    return {
        userId,
        totalPoints,
        level: userLevel.level,
        title: userLevel.title,
        rewards: rewards.slice(0, 20), // 最近20条记录
        rewardCount: rewards.length,
        averageReward: rewards.length > 0 ? 
            Math.floor(totalPoints / rewards.length) : 0
    };
}

// 获取裂变排行榜
function getFissionLeaderboard(limit = 20) {
    const pointsLeaderboard = db.fissionRewards.getLeaderboard(limit);
    const levelLeaderboard = db.userLevels.getLeaderboard(limit);
    
    // 合并数据
    const leaderboard = pointsLeaderboard.map(item => {
        const userLevel = db.userLevels.getUser(item.userId);
        return {
            userId: item.userId,
            points: item.points,
            level: userLevel.level,
            title: userLevel.title,
            rank: null // 稍后计算
        };
    });
    
    // 计算排名
    leaderboard.sort((a, b) => {
        // 先按积分排序，再按等级排序
        if (b.points !== a.points) return b.points - a.points;
        return b.level - a.level;
    });
    
    leaderboard.forEach((item, index) => {
        item.rank = index + 1;
    });
    
    return {
        pointsLeaderboard: leaderboard.slice(0, limit),
        levelLeaderboard: levelLeaderboard,
        updatedAt: new Date().toISOString()
    };
}

// 获取邀请码统计
function getInvitationCodeStats(code) {
    return db.invitationCodes.getStats(code);
}

// 停用邀请码
function deactivateInvitationCode(code, userId) {
    const invitation = db.invitationCodes.get(code);
    
    if (!invitation || invitation.userId !== userId) {
        return { success: false, error: '无权操作此邀请码' };
    }
    
    const success = db.invitationCodes.deactivate(code);
    
    if (success) {
        db.userLevels.addExperience(userId, 5, '管理邀请码');
        return { success: true, message: '邀请码已停用' };
    }
    
    return { success: false, error: '停用失败' };
}

// 批量生成邀请码
function batchGenerateInvitationCodes(userId, count = 5, options = {}) {
    const codes = [];
    
    for (let i = 0; i < count; i++) {
        const code = generateInvitationCode(userId, options);
        codes.push(code);
    }
    
    // 批量生成额外经验
    db.userLevels.addExperience(userId, count * 3, `批量生成 ${count} 个邀请码`);
    
    return {
        success: true,
        count,
        codes,
        message: `成功生成 ${count} 个邀请码`
    };
}

// 获取系统统计
function getSystemStats() {
    const invitationCodes = Object.values(db.invitationCodes.data);
    const referralRelations = Object.values(db.referralRelations.data);
    const fissionRewards = Object.values(db.fissionRewards.data);
    const userLevels = Object.values(db.userLevels.data);
    
    // 计算活跃邀请码
    const activeCodes = invitationCodes.filter(code => code.isActive).length;
    
    // 计算总邀请人数
    const totalInvitations = referralRelations.filter(rel => 
        rel.relationship === 'direct'
    ).length;
    
    // 计算总奖励积分
    const totalRewardPoints = fissionRewards.reduce(
        (sum, reward) => sum + reward.points, 0
    );
    
    // 计算平均等级
    const avgLevel = userLevels.length > 0 ?
        userLevels.reduce((sum, user) => sum + user.level, 0) / userLevels.length : 0;
    
    return {
        totalUsers: userLevels.length,
        totalInvitationCodes: invitationCodes.length,
        activeInvitationCodes: activeCodes,
        totalInvitations,
        totalRewardPoints,
        averageLevel: avgLevel.toFixed(1),
        topInviter: getTopInviter(),
        recentActivity: getRecentActivity(10),
        updatedAt: new Date().toISOString()
    };
}

// 获取顶级邀请者
function getTopInviter() {
    const relations = Object.values(db.referralRelations.data);
    const inviterCount = {};
    
    relations.forEach(rel => {
        if (rel.relationship === 'direct') {
            inviterCount[rel.inviterId] = (inviterCount[rel.inviterId] || 0) + 1;
        }
    });
    
    const top = Object.entries(inviterCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 1);
    
    if (top.length === 0) return null;
    
    const [userId, count] = top[0];
    const userLevel = db.userLevels.getUser(userId);
    
    return {
        userId,
        invitationCount: count,
        level: userLevel.level,
        title: userLevel.title
    };
}

// 获取最近活动
function getRecentActivity(limit = 10) {
    const allActivities = [];
    
    // 收集邀请码创建活动
    Object.values(db.invitationCodes.data).forEach(code => {
        allActivities.push({
            type: 'invitation_created',
            userId: code.userId,
            data: { code: code.code },
            timestamp: code.createdAt
        });
    });
    
    // 收集邀请活动
    Object.values(db.referralRelations.data).forEach(rel => {
        allActivities.push({
            type: 'invitation_used',
            userId: rel.inviterId,
            data: { 
                newUserId: rel.newUserId,
                relationId: rel.id 
            },
            timestamp: rel.createdAt
        });
    });
    
    // 收集奖励活动
    Object.values(db.fissionRewards.data).forEach(reward => {
        allActivities.push({
            type: 'reward_awarded',
            userId: reward.userId,
            data: { 
                points: reward.points,
                reason: reward.reason 
            },
            timestamp: reward.awardedAt
        });
    });
    
    // 按时间排序并限制数量
    return allActivities
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .slice(0, limit);
}

// 导出API函数
module.exports = {
    generateInvitationCode,
    useInvitationCode,
    getUserInvitationCodes,
    getUserReferralNetwork,
    getUserFissionRewards,
    getFissionLeaderboard,
    getInvitationCodeStats,
    deactivateInvitationCode,
    batchGenerateInvitationCodes,
    getSystemStats,
    
    // 测试数据
    getTestData: () => ({
        systemStats: getSystemStats(),
        dbStats: {
            invitationCodes: Object.keys(db.invitationCodes.data).length,
            referralRelations: Object.keys(db.referralRelations.data).length,
            fissionRewards: Object.keys(db.fissionRewards.data).length,
            userLevels: Object.keys(db.userLevels.data).length
        }
    })
};