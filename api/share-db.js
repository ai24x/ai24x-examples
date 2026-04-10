/**
 * 分享系统数据库模块
 * 提供分享链接、点击记录、转化记录的持久化存储
 */

const fs = require('fs');
const path = require('path');

// 数据库文件路径
const DB_DIR = path.join(__dirname, '../data');
const DB_FILES = {
    SHARE_LINKS: path.join(DB_DIR, 'share-links.json'),
    SHARE_CLICKS: path.join(DB_DIR, 'share-clicks.json'),
    SHARE_CONVERSIONS: path.join(DB_DIR, 'share-conversions.json'),
    USER_REWARDS: path.join(DB_DIR, 'user-rewards.json')
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

// 分享链接数据库操作
class ShareLinksDB {
    constructor() {
        this.data = readDb('SHARE_LINKS');
    }
    
    save() {
        return writeDb('SHARE_LINKS', this.data);
    }
    
    get(shareId) {
        return this.data[shareId] || null;
    }
    
    set(shareId, shareLink) {
        this.data[shareId] = shareLink;
        this.save();
        return shareLink;
    }
    
    delete(shareId) {
        if (this.data[shareId]) {
            delete this.data[shareId];
            this.save();
            return true;
        }
        return false;
    }
    
    getAll() {
        return Object.values(this.data);
    }
    
    getByUserId(userId) {
        return Object.values(this.data).filter(link => link.userId === userId);
    }
    
    updateStats(shareId, updates) {
        const shareLink = this.get(shareId);
        if (!shareLink) return false;
        
        Object.assign(shareLink, updates);
        this.set(shareId, shareLink);
        return true;
    }
}

// 点击记录数据库操作
class ShareClicksDB {
    constructor() {
        this.data = readDb('SHARE_CLICKS');
    }
    
    save() {
        return writeDb('SHARE_CLICKS', this.data);
    }
    
    add(shareId, clickRecord) {
        if (!this.data[shareId]) {
            this.data[shareId] = [];
        }
        this.data[shareId].push(clickRecord);
        this.save();
        return clickRecord;
    }
    
    getByShareId(shareId) {
        return this.data[shareId] || [];
    }
    
    getCountByShareId(shareId) {
        return this.getByShareId(shareId).length;
    }
    
    getTodayClicks(shareId) {
        const today = new Date().toISOString().split('T')[0];
        return this.getByShareId(shareId).filter(click => 
            click.clickedAt.startsWith(today)
        );
    }
    
    getRecentClicks(shareId, limit = 100) {
        const clicks = this.getByShareId(shareId);
        return clicks.slice(-limit).reverse();
    }
}

// 转化记录数据库操作
class ShareConversionsDB {
    constructor() {
        this.data = readDb('SHARE_CONVERSIONS');
    }
    
    save() {
        return writeDb('SHARE_CONVERSIONS', this.data);
    }
    
    add(shareId, conversionRecord) {
        if (!this.data[shareId]) {
            this.data[shareId] = [];
        }
        this.data[shareId].push(conversionRecord);
        this.save();
        return conversionRecord;
    }
    
    getByShareId(shareId) {
        return this.data[shareId] || [];
    }
    
    getCountByShareId(shareId) {
        return this.getByShareId(shareId).length;
    }
    
    getTodayConversions(shareId) {
        const today = new Date().toISOString().split('T')[0];
        return this.getByShareId(shareId).filter(conv => 
            conv.convertedAt.startsWith(today)
        );
    }
}

// 用户奖励数据库操作
class UserRewardsDB {
    constructor() {
        this.data = readDb('USER_REWARDS');
    }
    
    save() {
        return writeDb('USER_REWARDS', this.data);
    }
    
    getUser(userId) {
        if (!this.data[userId]) {
            this.data[userId] = {
                userId,
                totalPoints: 0,
                availablePoints: 0,
                usedPoints: 0,
                rewardHistory: [],
                level: 1,
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString()
            };
        }
        return this.data[userId];
    }
    
    addPoints(userId, points, reason) {
        const user = this.getUser(userId);
        user.totalPoints += points;
        user.availablePoints += points;
        user.updatedAt = new Date().toISOString();
        
        user.rewardHistory.push({
            points,
            reason,
            type: 'earn',
            timestamp: new Date().toISOString()
        });
        
        this.save();
        return user;
    }
    
    usePoints(userId, points, reason) {
        const user = this.getUser(userId);
        if (user.availablePoints < points) {
            throw new Error('积分不足');
        }
        
        user.availablePoints -= points;
        user.usedPoints += points;
        user.updatedAt = new Date().toISOString();
        
        user.rewardHistory.push({
            points: -points,
            reason,
            type: 'use',
            timestamp: new Date().toISOString()
        });
        
        this.save();
        return user;
    }
    
    getHistory(userId, limit = 50) {
        const user = this.getUser(userId);
        return user.rewardHistory.slice(-limit).reverse();
    }
    
    updateLevel(userId, newLevel) {
        const user = this.getUser(userId);
        user.level = newLevel;
        user.updatedAt = new Date().toISOString();
        this.save();
        return user;
    }
}

// 导出数据库实例
module.exports = {
    ShareLinksDB,
    ShareClicksDB,
    ShareConversionsDB,
    UserRewardsDB,
    
    // 单例实例
    shareLinks: new ShareLinksDB(),
    shareClicks: new ShareClicksDB(),
    shareConversions: new ShareConversionsDB(),
    userRewards: new UserRewardsDB(),
    
    // 工具函数
    ensureDbDir,
    readDb,
    writeDb
};