/**
 * 裂变系统数据库模块
 * 提供邀请码、推荐关系、裂变奖励的持久化存储
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// 数据库文件路径
const DB_DIR = path.join(__dirname, '../data');
const DB_FILES = {
    INVITATION_CODES: path.join(DB_DIR, 'invitation-codes.json'),
    REFERRAL_RELATIONS: path.join(DB_DIR, 'referral-relations.json'),
    FISSION_REWARDS: path.join(DB_DIR, 'fission-rewards.json'),
    USER_LEVELS: path.join(DB_DIR, 'user-levels.json')
};

// 确保数据库目录存在
function ensureDbDir() {
    if (!fs.existsSync(DB_DIR)) {
        fs.mkdirSync(DB_DIR, { recursive: true });
    }
    
    // 初始化数据库文件
    Object.values(DB_FILES).forEach(file => {
        if (!fs.existsSync(file)) {
            fs.writeFileSync(file, JSON.stringify({}, null, 2));
        }
    });
}

// 读取数据库
function readDb(dbName) {
    ensureDbDir();
    try {
        const data = fs.readFileSync(DB_FILES[dbName], 'utf8');
        return JSON.parse(data);
    } catch (error) {
        console.error(`读取数据库 ${dbName} 失败:`, error);
        return {};
    }
}

// 写入数据库
function writeDb(dbName, data) {
    ensureDbDir();
    try {
        fs.writeFileSync(DB_FILES[dbName], JSON.stringify(data, null, 2));
        return true;
    } catch (error) {
        console.error(`写入数据库 ${dbName} 失败:`, error);
        return false;
    }
}

// 生成邀请码
function generateInvitationCode(length = 8) {
    return crypto.randomBytes(Math.ceil(length / 2))
        .toString('hex')
        .slice(0, length)
        .toUpperCase();
}

// 邀请码数据库操作
class InvitationCodesDB {
    constructor() {
        this.data = readDb('INVITATION_CODES');
    }
    
    save() {
        return writeDb('INVITATION_CODES', this.data);
    }
    
    create(userId, code = null, maxUses = 10, expiresAt = null) {
        const invitationCode = code || generateInvitationCode();
        
        const invitation = {
            code: invitationCode,
            userId,
            createdAt: new Date().toISOString(),
            expiresAt,
            maxUses,
            usedCount: 0,
            isActive: true,
            rewardPoints: 0,
            level: 1
        };
        
        this.data[invitationCode] = invitation;
        this.save();
        return invitation;
    }
    
    get(code) {
        return this.data[code] || null;
    }
    
    use(code, newUserId) {
        const invitation = this.get(code);
        if (!invitation || !invitation.isActive) {
            return { success: false, error: '邀请码无效或已失效' };
        }
        
        // 检查是否过期
        if (invitation.expiresAt && new Date(invitation.expiresAt) < new Date()) {
            invitation.isActive = false;
            this.save();
            return { success: false, error: '邀请码已过期' };
        }
        
        // 检查使用次数限制
        if (invitation.usedCount >= invitation.maxUses) {
            invitation.isActive = false;
            this.save();
            return { success: false, error: '邀请码使用次数已达上限' };
        }
        
        // 更新使用次数
        invitation.usedCount++;
        if (invitation.usedCount >= invitation.maxUses) {
            invitation.isActive = false;
        }
        
        this.data[code] = invitation;
        this.save();
        
        return { 
            success: true, 
            invitation,
            inviterId: invitation.userId,
            newUserId 
        };
    }
    
    getUserCodes(userId) {
        return Object.values(this.data).filter(inv => inv.userId === userId);
    }
    
    deactivate(code) {
        const invitation = this.get(code);
        if (invitation) {
            invitation.isActive = false;
            this.data[code] = invitation;
            this.save();
            return true;
        }
        return false;
    }
    
    getStats(code) {
        const invitation = this.get(code);
        if (!invitation) return null;
        
        const relations = new ReferralRelationsDB();
        const referrals = relations.getByInvitationCode(code);
        
        return {
            code,
            totalUses: invitation.usedCount,
            maxUses: invitation.maxUses,
            usageRate: ((invitation.usedCount / invitation.maxUses) * 100).toFixed(1),
            isActive: invitation.isActive,
            createdAt: invitation.createdAt,
            expiresAt: invitation.expiresAt,
            referrals: referrals.length,
            rewardPoints: invitation.rewardPoints
        };
    }
}

// 推荐关系数据库操作
class ReferralRelationsDB {
    constructor() {
        this.data = readDb('REFERRAL_RELATIONS');
    }
    
    save() {
        return writeDb('REFERRAL_RELATIONS', this.data);
    }
    
    create(inviterId, newUserId, invitationCode, relationship = 'direct') {
        const relationId = crypto.randomBytes(8).toString('hex');
        
        const relation = {
            id: relationId,
            inviterId,
            newUserId,
            invitationCode,
            relationship, // direct, indirect
            createdAt: new Date().toISOString(),
            level: relationship === 'direct' ? 1 : 2,
            rewardStatus: 'pending',
            rewardPoints: 0
        };
        
        this.data[relationId] = relation;
        this.save();
        return relation;
    }
    
    get(relationId) {
        return this.data[relationId] || null;
    }
    
    getByInviter(inviterId) {
        return Object.values(this.data).filter(rel => rel.inviterId === inviterId);
    }
    
    getByNewUser(newUserId) {
        return Object.values(this.data).filter(rel => rel.newUserId === newUserId);
    }
    
    getByInvitationCode(code) {
        return Object.values(this.data).filter(rel => rel.invitationCode === code);
    }
    
    getInvitationChain(userId, maxDepth = 3) {
        const chain = [];
        let currentUserId = userId;
        let depth = 0;
        
        while (depth < maxDepth) {
            const relation = Object.values(this.data).find(
                rel => rel.newUserId === currentUserId
            );
            
            if (!relation) break;
            
            chain.push({
                level: depth + 1,
                inviterId: relation.inviterId,
                relationId: relation.id,
                createdAt: relation.createdAt
            });
            
            currentUserId = relation.inviterId;
            depth++;
        }
        
        return chain;
    }
    
    getNetworkStats(userId) {
        const directReferees = this.getByInviter(userId);
        const totalReferees = directReferees.length;
        
        // 计算间接推荐（二级）
        let indirectReferees = 0;
        directReferees.forEach(ref => {
            const secondLevel = this.getByInviter(ref.newUserId);
            indirectReferees += secondLevel.length;
        });
        
        const totalNetwork = totalReferees + indirectReferees;
        
        return {
            userId,
            directReferees: totalReferees,
            indirectReferees,
            totalNetwork,
            networkValue: calculateNetworkValue(totalReferees, indirectReferees),
            conversionRate: calculateConversionRate(userId, this.data)
        };
    }
    
    updateRewardStatus(relationId, status, points = 0) {
        const relation = this.get(relationId);
        if (!relation) return false;
        
        relation.rewardStatus = status;
        relation.rewardPoints = points;
        relation.updatedAt = new Date().toISOString();
        
        this.data[relationId] = relation;
        this.save();
        return true;
    }
}

// 裂变奖励数据库操作
class FissionRewardsDB {
    constructor() {
        this.data = readDb('FISSION_REWARDS');
    }
    
    save() {
        return writeDb('FISSION_REWARDS', this.data);
    }
    
    award(userId, points, reason, relationId = null) {
        const rewardId = crypto.randomBytes(8).toString('hex');
        
        const reward = {
            id: rewardId,
            userId,
            points,
            reason,
            relationId,
            awardedAt: new Date().toISOString(),
            status: 'awarded',
            type: 'fission'
        };
        
        this.data[rewardId] = reward;
        this.save();
        return reward;
    }
    
    getUserRewards(userId, limit = 50) {
        const userRewards = Object.values(this.data).filter(
            reward => reward.userId === userId
        );
        
        return userRewards
            .sort((a, b) => new Date(b.awardedAt) - new Date(a.awardedAt))
            .slice(0, limit);
    }
    
    getTotalPoints(userId) {
        const userRewards = this.getUserRewards(userId);
        return userRewards.reduce((total, reward) => total + reward.points, 0);
    }
    
    getLeaderboard(limit = 20) {
        const userPoints = {};
        
        Object.values(this.data).forEach(reward => {
            if (reward.status === 'awarded') {
                userPoints[reward.userId] = (userPoints[reward.userId] || 0) + reward.points;
            }
        });
        
        return Object.entries(userPoints)
            .map(([userId, points]) => ({ userId, points }))
            .sort((a, b) => b.points - a.points)
            .slice(0, limit);
    }
}

// 用户等级数据库操作
class UserLevelsDB {
    constructor() {
        this.data = readDb('USER_LEVELS');
    }
    
    save() {
        return writeDb('USER_LEVELS', this.data);
    }
    
    getUser(userId) {
        if (!this.data[userId]) {
            this.data[userId] = {
                userId,
                level: 1,
                experience: 0,
                nextLevelExp: 100,
                title: '新手',
                benefits: ['基础奖励'],
                joinedAt: new Date().toISOString(),
                lastActive: new Date().toISOString()
            };
        }
        return this.data[userId];
    }
    
    addExperience(userId, exp, reason) {
        const user = this.getUser(userId);
        user.experience += exp;
        user.lastActive = new Date().toISOString();
        
        // 检查是否升级
        while (user.experience >= user.nextLevelExp) {
            user.level++;
            user.experience -= user.nextLevelExp;
            user.nextLevelExp = Math.floor(user.nextLevelExp * 1.5);
            user.title = getLevelTitle(user.level);
            user.benefits = getLevelBenefits(user.level);
            
            console.log(`用户 ${userId} 升级到 ${user.level} 级，称号: ${user.title}`);
        }
        
        this.data[userId] = user;
        this.save();
        
        return {
            user,
            expAdded: exp,
            reason,
            levelUp: user.experience < exp // 如果升级了，这个条件为true
        };
    }
    
    getLeaderboard(limit = 20) {
        return Object.values(this.data)
            .sort((a, b) => {
                // 先按等级排序，再按经验排序
                if (b.level !== a.level) return b.level - a.level;
                return b.experience - a.experience;
            })
            .slice(0, limit)
            .map(user => ({
                userId: user.userId,
                level: user.level,
                experience: user.experience,
                title: user.title
            }));
    }
}

// 辅助函数：计算网络价值
function calculateNetworkValue(direct, indirect) {
    // 直接推荐价值更高
    const directValue = direct * 10;
    const indirectValue = indirect * 3;
    return directValue + indirectValue;
}

// 辅助函数：计算转化率
function calculateConversionRate(userId, relationsData) {
    const userRelations = Object.values(relationsData).filter(
        rel => rel.inviterId === userId
    );
    
    if (userRelations.length === 0) return 0;
    
    const activeRelations = userRelations.filter(
        rel => rel.rewardStatus === 'awarded'
    );
    
    return ((activeRelations.length / userRelations.length) * 100).toFixed(1);
}

// 辅助函数：获取等级称号
function getLevelTitle(level) {
    if (level >= 10) return '裂变大师';
    if (level >= 7) return '裂变专家';
    if (level >= 5) return '裂变高手';
    if (level >= 3) return '裂变达人';
    return '新手';
}

// 辅助函数：获取等级权益
function getLevelBenefits(level) {
    const benefits = ['基础奖励'];
    
    if (level >= 2) benefits.push('二级裂变奖励');
    if (level >= 3) benefits.push('专属邀请码样式');
    if (level >= 5) benefits.push('高级数据分析');
    if (level >= 7) benefits.push('专属客服');
    if (level >= 10) benefits.push('平台分红权益');
    
    return benefits;
}

// 导出数据库实例
module.exports = {
    InvitationCodesDB,
    ReferralRelationsDB,
    FissionRewardsDB,
    UserLevelsDB,
    
    // 单例实例
    invitationCodes: new InvitationCodesDB(),
    referralRelations: new ReferralRelationsDB(),
    fissionRewards: new FissionRewardsDB(),
    userLevels: new UserLevelsDB(),
    
    // 工具函数
    generateInvitationCode,
    ensureDbDir,
    readDb,
    writeDb
};