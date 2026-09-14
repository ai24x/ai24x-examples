// app.js — P0-1「别听它的」微信小程序原型
const store = require('./utils/store');

App({
  globalData: {
    version: '0.1.0',
    lastRound: null,   // 上一局完整结果（结算页兜底）
    newBest: false     // 本局是否刷新最高分
  },
  onLaunch() {
    store.ensure();
  }
});