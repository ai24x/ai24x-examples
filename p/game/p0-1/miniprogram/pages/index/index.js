// pages/index/index.js — 首页
const game = require('../../utils/game');
const store = require('../../utils/store');
const ad = require('../../utils/ad');

Page({
  data: {
    doubleOn: false,
    best: 0,
    cum: 0,
    games: 0,
    tier: { name: '青铜' },
    friends: []
  },

  onShow() {
    this.refresh();
  },

  refresh() {
    const best = store.getBest();
    const cum = store.getCum();
    const games = store.getGames();
    const tier = game.rankOf(cum);
    // 原型：好友榜为本地模拟数据（待中台联调后换真实关系链）
    const friends = [
      { name: '💪 大力出奇迹', score: best > 0 ? Math.round(best * 1.18) : 8600 },
      { name: '⚡ 手速小王子', score: best > 0 ? Math.round(best * 1.05) : 7200 },
      { name: '🎮 隔壁老王', score: best > 0 ? Math.round(best * 0.92) : 4800 },
      { name: '🌟 萌新小鹿', score: best > 0 ? Math.round(best * 0.71) : 3100 },
      { name: '😼 高冷猫爷', score: best > 0 ? Math.round(best * 0.55) : 1900 }
    ];
    this.setData({ best: best, cum: cum, games: games, tier: tier, friends: friends });
  },

  onDoubleChange(e) {
    this.setData({ doubleOn: e.detail.value });
  },

  tapStart() {
    const self = this;
    if (this.data.doubleOn) {
      ad.showRewardedVideo({
        onReward: function () { self.goPlay({ doubled: true }); },
        onFail: function () { self.goPlay({ doubled: false }); }
      });
    } else {
      this.goPlay({ doubled: false });
    }
  },

  tapDaily() {
    const self = this;
    const today = store.todayStr();
    const done = store.getDailyDone();
    const note = done && done.date === today ? '（今日已挑战，可再试一局）' : '';
    wx.showModal({
      title: '今日挑战',
      content: '同种子固定序列，全服比分榜单挑战' + note,
      confirmText: '开战',
      success: function (res) {
        if (res.confirm) self.goPlay({ daily: true, date: today });
      }
    });
  },

  goPlay(opts) {
    const parts = [];
    if (opts.daily) {
      parts.push('daily=1');
      parts.push('date=' + opts.date);
    }
    if (opts.doubled) parts.push('double=1');
    wx.navigateTo({
      url: '/pages/play/play' + (parts.length ? '?' + parts.join('&') : '')
    });
  },

  onShareAppMessage() {
    return {
      title: '我击败了 ' + game.beatPct(store.getBest()) + '% 好友，敢来一局吗？',
      path: '/pages/index/index?from=share'
    };
  }
});