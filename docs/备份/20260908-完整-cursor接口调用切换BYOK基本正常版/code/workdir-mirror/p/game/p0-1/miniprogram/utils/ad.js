// utils/ad.js — 激励视频封装：原型默认走「模拟广告」；配置 MOCK_AD_UNIT 后自动切真实广告
// TODO(上线前): 微信公众平台开通流量主，替换下方占位 adUnitId
const MOCK_AD_UNIT = ''; // 例如 'adunit-xxxxxxxxxxxxxxxx'

function showRewardedVideo(options) {
  const opts = options || {};
  const adUnitId = opts.adUnitId || MOCK_AD_UNIT;
  const onReward = opts.onReward || function () {};
  const onFail = opts.onFail || function () {};

  if (!adUnitId) {
    // 模拟激励视频：1.5s 后发放奖励
    wx.showLoading({ title: '模拟广告播放中…', mask: true });
    setTimeout(function () {
      wx.hideLoading();
      onReward();
    }, 1500);
    return;
  }

  // 真实激励视频路径（真机 + 已开通流量主时生效）
  const ad = wx.createRewardedVideoAd({ adUnitId: adUnitId });
  ad.onClose(function (res) {
    if (res && res.isEnded) onReward();
    else onFail();
  });
  ad.show().catch(function () {
    ad.load().then(function () { return ad.show(); }).catch(onFail);
  });
}

module.exports = { showRewardedVideo: showRewardedVideo };