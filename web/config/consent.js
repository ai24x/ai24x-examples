/* AI24X 意见征求模式（Consent Mode v2）— 2026-08-14
 * 配合每页 <head> 后的 Google Ads gtag 使用；用户选择持久化到 localStorage，
 * 已选择用户不再弹窗，未选择用户默认拒绝（广告/分析保持 denied）。 */
(function () {
  if (window.__ai24xConsentLoaded) return;
  window.__ai24xConsentLoaded = true;

  var KEY = 'ai24x_consent_v1';

  function readChoice() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function saveChoice(v) {
    try { localStorage.setItem(KEY, v); } catch (e) {}
  }

  function updateConsent(mode) {
    var ad = mode === 'accepted' ? 'granted' : 'denied';
    if (window.gtag) {
      window.gtag('consent', 'update', {
        ad_storage: ad,
        ad_user_data: ad,
        ad_personalization: ad,
        analytics_storage: ad,
        personalization_storage: ad,
        functionality_storage: 'granted',
        security_storage: 'granted'
      });
    }
  }

  function showBanner() {
    if (document.getElementById('ai24x-consent-banner')) return;
    var zh = (navigator.language || '').toLowerCase().indexOf('zh') === 0;
    var bar = document.createElement('div');
    bar.id = 'ai24x-consent-banner';
    bar.setAttribute('role', 'dialog');
    bar.setAttribute('aria-label', 'Cookie consent');
    bar.innerHTML =
      '<div style="position:fixed;left:16px;right:16px;bottom:16px;z-index:2147483000;max-width:640px;margin:0 auto;box-sizing:border-box;background:#fff;color:#1a1a2e;border:1px solid #d8dce6;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.18);padding:14px 16px;font:13px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">' +
        '<div style="margin:0 0 10px">' + (zh ? '我们使用 Cookie 提供个性化广告并衡量网站效果。您可随时选择接受或拒绝。' : 'We use cookies to personalise ads and measure site performance. You can accept or decline at any time.') + '</div>' +
        '<div style="text-align:right">' +
          '<button type="button" data-act="decline" style="margin:0 8px 0 0;padding:7px 14px;border:1px solid #c9ced9;background:#f4f6fa;color:#333;border-radius:8px;cursor:pointer;font-size:13px">' + (zh ? '拒绝' : 'Decline') + '</button>' +
          '<button type="button" data-act="accept" style="padding:7px 16px;border:1px solid #2f6bff;background:#2f6bff;color:#fff;border-radius:8px;cursor:pointer;font-size:13px">' + (zh ? '接受' : 'Accept') + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(bar);
    bar.addEventListener('click', function (e) {
      var btn = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
      if (!btn) return;
      var act = btn.getAttribute('data-act');
      saveChoice(act);
      updateConsent(act === 'accept' ? 'accepted' : 'declined');
      bar.parentNode.removeChild(bar);
    });
  }

  var choice = readChoice();
  if (choice) {
    updateConsent(choice === 'accepted' ? 'accepted' : 'declined');
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showBanner);
  } else {
    showBanner();
  }
})();
