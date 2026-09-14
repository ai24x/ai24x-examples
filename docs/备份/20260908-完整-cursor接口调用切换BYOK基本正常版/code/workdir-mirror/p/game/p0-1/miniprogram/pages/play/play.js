// pages/play/play.js — 游戏页：45s 反口令循环
const game = require('../../utils/game');
const store = require('../../utils/store');
const ad = require('../../utils/ad');
const app = getApp();

Page({
  data: {
    daily: false,
    doubled: false,
    running: false,
    score: 0,
    combo: 0,
    maxCombo: 0,
    right: 0,
    wrong: 0,
    total: 0,
    timeLeft: game.DURATION,
    timePct: 100,
    promptMain: '',
    promptSub: '',
    promptColor: '#ffffff',
    hint: '',
    padType: 'colors',
    buttons: [],
    fxTick: 0,
    fxText: '',
    fxCls: '',
    lifeUsed: false,
    showEnd: false,
    endTitle: '',
    endRank: ''
  },

  onLoad(options) {
    const daily = options.daily === '1';
    const doubled = options.double === '1';
    this._date = options.date || store.todayStr();
    this._rng = daily
      ? game.mulberry32(game.seedForDate(this._date))
      : game.mulberry32(Date.now() & 0xffffffff);
    this.setData({ daily: daily, doubled: doubled });
    this.resetRound();
    this.startRound();
  },

  onUnload() { this.stopAll(); },
  onHide() { this.pauseRound(); },
  onShow() {
    if (this._paused) this.resumeRound();
  },

  // ---------- 回合控制 ----------
  resetRound() {
    this.stopAll();
    this._current = null;
    this._endAt = 0;
    this._paused = false;
    this.setData({
      running: false,
      score: 0,
      combo: 0,
      maxCombo: 0,
      right: 0,
      wrong: 0,
      total: 0,
      timeLeft: game.DURATION,
      timePct: 100,
      promptMain: '',
      promptSub: '',
      promptColor: '#ffffff',
      hint: '',
      buttons: [],
      fxTick: 0,
      lifeUsed: false,
      showEnd: false,
      endTitle: '',
      endRank: ''
    });
  },

  startRound() {
    this._endAt = Date.now() + game.DURATION * 1000;
    this.setData({ running: true, showEnd: false, lifeUsed: false });
    this.startTicker();
    this.spawn();
  },

  restart() {
    // 再来一局：每日挑战回到当日固定序列起点
    this._rng = this.data.daily
      ? game.mulberry32(game.seedForDate(this._date))
      : game.mulberry32(Date.now() & 0xffffffff);
    this.resetRound();
    this.startRound();
  },

  // ---------- 计时 ----------
  startTicker() {
    this.stopTicker();
    this._ticker = setInterval(() => this.tick(), 100);
  },
  stopTicker() {
    if (this._ticker) { clearInterval(this._ticker); this._ticker = null; }
  },
  stopAll() {
    this.stopTicker();
    if (this._nextTimer) { clearTimeout(this._nextTimer); this._nextTimer = null; }
    if (this._fxTimer) { clearTimeout(this._fxTimer); this._fxTimer = null; }
  },

  tick() {
    if (!this.data.running) return;
    const remain = (this._endAt - Date.now()) / 1000;
    if (remain <= 0) {
      this.setData({ timeLeft: 0, timePct: 0 });
      this.onTimeUp();
      return;
    }
    this.setData({
      timeLeft: Math.ceil(remain),
      timePct: Math.max(0, Math.min(100, (remain / game.DURATION) * 100))
    });
  },

  pauseRound() {
    if (!this.data.running || this.data.showEnd) return;
    this._paused = true;
    this._pausedRemain = Math.max(0, (this._endAt - Date.now()) / 1000);
    this.stopAll();
  },
  resumeRound() {
    if (!this._paused) return;
    this._paused = false;
    this._endAt = Date.now() + this._pausedRemain * 1000;
    this.startTicker();
  },

  // ---------- 指令与作答 ----------
  spawn() {
    if (!this.data.running) return;
    const task = game.buildPrompt(this._rng);
    this._current = task;
    this.setData({
      promptMain: task.main,
      promptSub: task.sub,
      promptColor: task.mainColor,
      hint: task.hint,
      padType: task.pad,
      buttons: task.buttons
    });
  },

  onTap(e) {
    if (!this.data.running) return;
    this.answer(e.currentTarget.dataset.key);
  },

  answer(key) {
    const task = this._current;
    if (!task) return;
    const right = key === task.correct;
    let patch = { total: this.data.total + 1 };

    if (right) {
      const combo = this.data.combo + 1;
      const gain = game.gainFor(combo, this.data.doubled);
      patch = Object.assign(patch, {
        combo: combo,
        right: this.data.right + 1,
        maxCombo: Math.max(this.data.maxCombo, combo),
        score: this.data.score + gain
      });
      this.fx('+' + gain, 'ok');
      if (wx.vibrateShort) wx.vibrateShort({ type: 'light' });
    } else {
      patch = Object.assign(patch, { combo: 0, wrong: this.data.wrong + 1 });
      this.fx('错!', 'err');
      if (wx.vibrateShort) wx.vibrateShort({ type: 'heavy' });
    }

    this.setData(patch);

    // 难度递增：连击越高指令越快
    const intervalMs = game.intervalFor(patch.combo || 0);
    if (this._nextTimer) clearTimeout(this._nextTimer);
    this._nextTimer = setTimeout(() => this.spawn(), intervalMs);
  },

  fx(text, cls) {
    this.setData({ fxText: text, fxCls: cls, fxTick: this.data.fxTick + 1 });
    if (this._fxTimer) clearTimeout(this._fxTimer);
    this._fxTimer = setTimeout(() => {
      if (this.data.fxTick) this.setData({ fxTick: 0 });
    }, 500);
  },

  // ---------- 结束 / 续命 ----------
  onTimeUp() {
    this.stopAll();
    this.setData({ running: false });
    if (!this.data.lifeUsed) {
      this.showEnd();
    } else {
      this.finishRound();
    }
  },

  showEnd() {
    const rank = game.rankOf(this.data.score);
    this.setData({
      showEnd: true,
      endTitle: this.data.score >= 4000 ? '太强了！' : '时间到！',
      endRank: rank.name
    });
  },

  tapLife() {
    if (this.data.lifeUsed) return;
    const self = this;
    ad.showRewardedVideo({
      onReward: function () {
        const remain = Math.min(
          game.DURATION,
          (self._endAt - Date.now()) / 1000 + game.LIFE_BONUS
        );
        self._endAt = Date.now() + remain * 1000;
        self.setData({ lifeUsed: true, showEnd: false, running: true });
        self.startTicker();
        if (self._nextTimer) { clearTimeout(self._nextTimer); self._nextTimer = null; }
        self.spawn();
        wx.showToast({ title: '续命 +15s', icon: 'none' });
      },
      onFail: function () {
        wx.showToast({ title: '广告未完成，未续命', icon: 'none' });
      }
    });
  },

  goResult() {
    this.finishRound();
  },

  finishRound() {
    this.stopAll();
    this.setData({ running: false, showEnd: false });
    const round = {
      score: this.data.score,
      combo: this.data.maxCombo,
      right: this.data.right,
      wrong: this.data.wrong,
      total: this.data.total,
      daily: this.data.daily,
      dailyDate: this.data.daily ? this._date : '',
      doubled: this.data.doubled
    };
    const saved = store.saveRound(round);
    app.globalData.lastRound = round;
    app.globalData.newBest = saved.isNewBest;
    wx.redirectTo({
      url:
        '/pages/result/result?' +
        'score=' + round.score +
        '&combo=' + round.combo +
        '&right=' + round.right +
        '&wrong=' + round.wrong +
        '&total=' + round.total +
        '&daily=' + (round.daily ? 1 : 0) +
        '&doubled=' + (round.doubled ? 1 : 0) +
        '&newBest=' + (saved.isNewBest ? 1 : 0)
    });
  },

  onShareAppMessage() {
    return {
      title: '反口令挑战中，我已 ' + this.data.score + ' 分，敢来吗？',
      path: '/pages/index/index?from=share'
    };
  }
});