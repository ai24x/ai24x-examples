from __future__ import annotations

from pathlib import Path


REGISTER_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>注册 · AI24X</title>
  <link rel="stylesheet" href="css/base.css?v=20260421a" />
  <link id="theme-css" rel="stylesheet" href="css/themes/theme-blue.css?v=20260421a" data-base="css/themes/" />
  <style>
    .auth-fieldset-preview {
      border: 0;
      margin: 0;
      padding: 0;
      min-width: 0;
      opacity: 0.93;
    }
    .auth-fieldset-preview:disabled .auth-tabs button {
      cursor: not-allowed;
    }
  </style>
</head>
<body data-page="register" class="theme-blue">
  <header class="site-header" id="site-header"></header>
  <main class="page-main">
    <section class="section">
      <div class="container" style="max-width:480px">
        <h1 data-i18n="auth.register.title"></h1>
        <p class="sub" data-i18n="auth.register.sub"></p>
        <p class="callout mt-2" data-i18n-html="auth.register.modeBanner"></p>
        <div
          class="callout mt-2"
          data-i18n-html="auth.closed.banner"
          role="status"
          aria-live="polite"
        ><strong>温馨提示</strong>：主站<strong>暂未开放</strong>注册与登录，表单不可提交。推荐首发应用 <a href="https://a.ai24x.com/?mode=register&amp;ch=phone" target="_blank" rel="noopener">AI 行情官｜灯塔版</a>。</div>
        <form class="card mt-2" id="form-register">
          <fieldset class="auth-fieldset-preview" disabled>
          <div class="auth-tabs" role="tablist" aria-label="register method">
            <button type="button" id="reg-tab-phone" class="is-active" role="tab" aria-selected="true" data-i18n="auth.tab.phone"></button>
            <button type="button" id="reg-tab-email" role="tab" aria-selected="false" data-i18n="auth.tab.email"></button>
          </div>
          <div id="reg-grp-phone">
            <div class="form-group">
              <label data-i18n="auth.login.phone"></label>
              <input id="reg-phone" name="phone" type="tel" class="input" autocomplete="tel" inputmode="tel" placeholder="" data-i18n-placeholder="auth.login.phonePh" />
            </div>
            <div class="form-group form-group-otp-inline">
              <label data-i18n="auth.register.code"></label>
              <div class="form-otp-row">
                <input id="reg-sms-code" name="sms_code" type="text" inputmode="numeric" maxlength="6" pattern="[0-9]*" class="input" autocomplete="one-time-code" placeholder="" data-i18n-placeholder="auth.register.codePh" />
                <button type="button" class="btn btn-otp-send" id="reg-btn-send-sms" data-i18n="auth.register.sendCode"></button>
              </div>
            </div>
          </div>
          <div class="form-group auth-field-hidden" id="reg-grp-email">
            <label data-i18n="auth.register.email"></label>
            <input id="reg-email" name="email" type="email" class="input" autocomplete="email" placeholder="" data-i18n-placeholder="auth.register.email" />
          </div>
          <div class="form-group">
            <label data-i18n="auth.register.password"></label>
            <input name="password" type="password" class="input" required autocomplete="new-password" data-i18n-placeholder="auth.register.password" />
          </div>
          <button type="submit" class="btn btn-primary" data-i18n="auth.register.submit"></button>
          <div id="reg-msg"></div>
          </fieldset>
        </form>
        <p class="sub small mt-2" data-i18n="auth.closed.registerSmsHint">短信验证码将在主站开放后启用。</p>
        <p class="mt-2 sub" data-i18n-html="auth.closed.footerRegister"><a href="login.html">登录</a> · <a href="register.html">注册</a></p>
      </div>
    </section>
  </main>
  <footer class="site-footer" id="site-footer"></footer>
  <script src="config/locales.js?v=20260420c"></script>
  <script src="js/api.js?v=20260420e"></script>
  <script src="js/i18n.js?v=20260420c"></script>
  <script src="js/shell.js?v=20260420c"></script>
  <script src="js/app.js?v=20260420c"></script>
  <script>
    function regAuthMode() {
      return document.getElementById("reg-tab-email").classList.contains("is-active") ? "email" : "phone";
    }
    function bindRegisterTabs() {
      var tabPhone = document.getElementById("reg-tab-phone");
      var tabEmail = document.getElementById("reg-tab-email");
      var grpPhone = document.getElementById("reg-grp-phone");
      var grpEmail = document.getElementById("reg-grp-email");
      var inpPhone = document.getElementById("reg-phone");
      var inpEmail = document.getElementById("reg-email");
      var inpSms = document.getElementById("reg-sms-code");
      if (!tabPhone || !tabEmail) return;
      function setMode(mode) {
        var isPhone = mode === "phone";
        tabPhone.classList.toggle("is-active", isPhone);
        tabEmail.classList.toggle("is-active", !isPhone);
        tabPhone.setAttribute("aria-selected", isPhone ? "true" : "false");
        tabEmail.setAttribute("aria-selected", !isPhone ? "true" : "false");
        grpPhone.classList.toggle("auth-field-hidden", !isPhone);
        grpEmail.classList.toggle("auth-field-hidden", isPhone);
        inpPhone.required = isPhone;
        inpEmail.required = !isPhone;
        if (inpSms) {
          inpSms.required = isPhone;
          if (!isPhone) inpSms.value = "";
        }
        if (window.AI24X_I18N) AI24X_I18N.apply(document.getElementById("form-register") || document.body);
      }
      tabPhone.addEventListener("click", function () { setMode("phone"); });
      tabEmail.addEventListener("click", function () { setMode("email"); });
      setMode("phone");
    }

    var regSmsTimer = null;
    var regSmsSec = 0;
    function regSmsHeaders() {
      var h = {};
      try {
        var k = localStorage.getItem("ai24x_sms_internal_key");
        if (k) h["X-SMS-Internal-Key"] = k;
      } catch (err) {}
      return h;
    }
    function setRegSmsButtonCountdown(sec) {
      var btn = document.getElementById("reg-btn-send-sms");
      if (!btn) return;
      regSmsSec = sec;
      if (regSmsTimer) clearInterval(regSmsTimer);
      if (sec <= 0) {
        btn.disabled = false;
        if (window.AI24X_I18N) btn.textContent = AI24X_I18N.t("auth.register.sendCode");
        return;
      }
      btn.disabled = true;
      btn.textContent = sec + "s";
      regSmsTimer = setInterval(function () {
        regSmsSec -= 1;
        if (regSmsSec <= 0) {
          clearInterval(regSmsTimer);
          regSmsTimer = null;
          btn.disabled = false;
          btn.textContent = window.AI24X_I18N ? AI24X_I18N.t("auth.register.sendCode") : "获取验证码";
        } else btn.textContent = regSmsSec + "s";
      }, 1000);
    }

    document.getElementById("reg-btn-send-sms").addEventListener("click", function () {
      var box = document.getElementById("reg-msg");
      var fs = document.querySelector("#form-register fieldset");
      if (fs && fs.disabled) {
        if (box) {
          box.textContent = "";
          var d = document.createElement("div");
          d.className = "alert alert-error";
          var msg0 = window.AI24X_I18N ? AI24X_I18N.t("auth.closed.registerBlocked") : "";
          if (!msg0 || msg0 === "auth.closed.registerBlocked") msg0 = "暂未开放。";
          d.textContent = msg0;
          box.appendChild(d);
        }
        return;
      }
      var phone = (document.getElementById("reg-phone").value || "").trim().replace(/\\s/g, "");
      if (!/^1\\d{10}$/.test(phone)) {
        box.innerHTML =
          '<div class="alert alert-error">' +
          (window.AI24X_I18N ? AI24X_I18N.t("auth.register.needPhone") : "请先填写 11 位手机号") +
          "</div>";
        return;
      }
      box.innerHTML = "";
      var btn = document.getElementById("reg-btn-send-sms");
      btn.disabled = true;
      AI24X_API.authSmsSend({ mobile: phone, purpose: "register" }, regSmsHeaders())
        .then(function (r) {
          if (r && r.ok) {
            box.innerHTML =
              '<div class="alert alert-success">' +
              (window.AI24X_I18N ? AI24X_I18N.t("auth.register.codeSent") : "验证码已发送") +
              "</div>";
            setRegSmsButtonCountdown(60);
          } else {
            btn.disabled = false;
            var msg = (r && r.message) || "发送失败";
            if (r && r.cooldown_s != null) setRegSmsButtonCountdown(Math.ceil(Number(r.cooldown_s)));
            box.innerHTML = '<div class="alert alert-error">' + msg + "</div>";
          }
        })
        .catch(function (err) {
          btn.disabled = false;
          box.innerHTML = '<div class="alert alert-error">' + (err.message || "Error") + "</div>";
        });
    });

    document.getElementById("form-register").addEventListener("submit", function (e) {
      e.preventDefault();
      var box = document.getElementById("reg-msg");
      if (!box) return;
      box.textContent = "";
      var d = document.createElement("div");
      d.className = "alert alert-error";
      var msg1 = window.AI24X_I18N ? AI24X_I18N.t("auth.closed.registerBlocked") : "";
      if (!msg1 || msg1 === "auth.closed.registerBlocked") msg1 = "暂未开放。";
      d.textContent = msg1;
      box.appendChild(d);
    });

    document.addEventListener("DOMContentLoaded", function () {
      try { bindRegisterTabs(); } catch (e) {}
    });
  </script>
</body>
</html>
"""


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "web"
    target = root / "register.html"
    target.write_text(REGISTER_HTML, encoding="utf-8", newline="\n")
    print("wrote", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

