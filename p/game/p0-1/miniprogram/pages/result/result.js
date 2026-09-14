// pages/result/result.js — 结算页：战绩 + 挑战卡分享
const game = require('../../utils/game');
const store = require('../../utils/store');
const app = getApp();

const RANK_EMOJI = {
  '青铜': '🥉',
  '白银': '🥈',
  '黄金': '🥇',
  '铂金': '💎',
  '钻石': '💠',
  '星耀': '🌟',
  '王者': '👑'
};

Page({
  data: {
    score: 0,
    maxCombo: 0,
    right: 0,
    wrong: 0,
    total: 0,
    daily: false,
    doubled: false,
    isNewBest: false,
    rankName: '青铜',
    rankEmoji: '🥉',
    title: '时间到！',
    beatPct: 40
  },

  onLoad(options) {
    const opts = options || {};
    const round = app.globalData.lastRound || {};
    const score = parseInt(opts.score || round.score || 0, 10) || 0;
    const maxCombo = parseInt(opts.combo || round.combo || 0, 10) || 0;
    const right = parseInt(opts.right || round.right || 0, 10) || 0;
    const wrong = parseInt(opts.wrong || round.wrong || 0, 10) || 0;
    const total = parseInt(opts.total || round.total || 0, 10) || 0;
    const daily = opts.daily === '1' || !!round.daily;
    const doubled = opts.doubled === '1' || !!round.doubled;
    const isNewBest = opts.newBest === '1' || !!app.globalData.newBest;
    const rank = game.rankOf(score);

    this.setData({
      score: score,
      maxCombo: maxCombo,
      right: right,
      wrong: wrong,
      total: total,
      daily: daily,
      doubled: doubled,
      isNewBest: isNewBest,
      rankName: rank.name,
      rankEmoji: RANK_EMOJI[rank.name] || '🎮',
      title: score >= 4000 ? '太强了！' : '时间到！',
      beatPct: game.beatPct(score)
    });
  },

  again() {
    const parts = [];
    if (this.data.doubled) parts.push('double=1');
    if (this.data.daily) {
      parts.push('daily=1');
      parts.push('date=' + ((app.globalData.lastRound && app.globalData.lastRound.dailyDate) || store.todayStr()));
    }
    wx.redirectTo({
      url: '/pages/play/play' + (parts.length ? '?' + parts.join('&') : '')
    });
  },

  home() {
    wx.reLaunch({ url: '/pages/index/index' });
  },

  onShareAppMessage() {
    return {
      title: '我击败了 ' + this.data.beatPct + '% 好友，敢来一局吗？',
      path: '/pages/index/index?from=share'
    };
  }
});