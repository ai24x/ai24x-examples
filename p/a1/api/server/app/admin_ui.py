from __future__ import annotations

import json

_COMMON_CSS = """
      :root {
        --bg: #0c0e12;
        --panel: #12161d;
        --panel2: #181d26;
        --border: #252b36;
        --text: #e8eaed;
        --muted: #8b949e;
        --pri: #60a5fa;
        --ok: #34d399;
        --warn: #fbbf24;
        --bad: #fb7185;
      }
      * { box-sizing: border-box; }
      html, body { margin: 0; height: 100%; }
      body { font-family: system-ui, "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); }
      h1 { font-size: 18px; margin: 0 0 10px; font-weight: 700; }
      label { font-size: 12px; color: var(--muted); display: block; margin-bottom: 6px; }
      input, select, textarea { background: var(--panel2); border: 1px solid var(--border); color: var(--text); padding: 8px 10px; border-radius: 10px; }
      button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 10px; cursor: pointer; }
      button:hover { border-color: var(--pri); }
      button:active { transform: translateY(0.5px); }
      button[disabled] { opacity: 0.55; cursor: not-allowed; }
      /* Admin UI: slightly color "load/save" actions without changing HTML */
      button[id^="btnLoad"] { background: rgba(96,165,250,0.06); border-color: rgba(96,165,250,0.28); }
      button[id^="btnLoad"]:hover { background: rgba(96,165,250,0.10); border-color: rgba(96,165,250,0.45); }
      button[id^="btnSave"] { background: rgba(52,211,153,0.10); border-color: rgba(52,211,153,0.38); }
      button[id^="btnSave"]:hover { background: rgba(52,211,153,0.16); border-color: rgba(52,211,153,0.55); }
      .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid var(--border); background: var(--panel2); }
      .pill.ok { color: var(--ok); }
      .pill.bad { color: var(--bad); }
      table { width: 100%; border-collapse: collapse; font-size: 12px; }
      th, td { padding: 10px 8px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
      th { color: var(--muted); font-weight: 600; }
      tr:hover td { background: rgba(255,255,255,0.02); }
      .mono { font-variant-numeric: tabular-nums; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
      .muted { color: var(--muted); }
      .split { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 12px; }
      @media (max-width: 960px) { .split { grid-template-columns: 1fr; } }
      .msg { margin-top: 10px; font-size: 12px; color: var(--muted); min-height: 1.2em; }
      .msg strong { color: var(--text); }
      .danger { color: var(--warn); }
      .small { font-size: 11px; }
      .field-row { display: flex; flex-wrap: wrap; gap: 14px 20px; align-items: flex-end; margin-top: 12px; }
      .field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
      .field .lbl { font-size: 13px; color: var(--text); font-weight: 600; line-height: 1.25; }
      .field .sub { font-size: 11px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
      th .th-cn { display: block; color: var(--text); font-weight: 600; }
      th .th-en { display: block; font-weight: 400; color: var(--muted); font-size: 10px; margin-top: 2px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
      .card-title { font-size: 13px; font-weight: 600; color: var(--text); }
      code.mono { font-size: 11px; background: var(--panel2); border: 1px solid var(--border); padding: 1px 6px; border-radius: 6px; }
      .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-top: 14px; }
      .row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
"""


def admin_login_html(admin_base: str, *, otp_required: bool = False) -> str:
    s = (
        """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>管理后台登录 · AI24X</title>
    <style>"""
        + _COMMON_CSS
        + """
      .login-wrap { min-height: 100%; display: flex; align-items: center; justify-content: center; padding: 24px; }
      .login-card { width: 100%; max-width: 420px; background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 28px 24px; }
      .login-card input { width: 100%; margin-bottom: 14px; }
      .login-card button { width: 100%; margin-top: 4px; }
      .login-card .row2 { display: flex; gap: 8px; align-items: stretch; }
      .login-card .row2 input { margin-bottom: 0; flex: 1; }
      .login-card .row2 button { width: auto; min-width: 120px; margin-top: 0; }
      .err { color: var(--bad); font-size: 13px; margin-top: 10px; min-height: 1.2em; }
    </style>
  </head>
  <body>
    <div class="login-wrap">
      <div class="login-card">
        <h1>管理后台登录</h1>
        <p class="muted small" style="line-height:1.55;margin-bottom:16px;">
          请输入<strong>管理密钥</strong>登录。
          若管理员已开启<strong>短信验证码</strong>校验，请先获取验证码并填写后再登录。
          登录成功后会在本浏览器保持会话一段时间。
        </p>
        <div id="otpBlock" style="display:none;">
          <label for="phone">总管 / 已登记手机</label>
          <div class="row2">
            <input id="phone" type="tel" autocomplete="tel" placeholder="11 位手机号" maxlength="20" />
            <button type="button" id="btnSendOtp">发送验证码</button>
          </div>
          <label for="otp">短信验证码</label>
          <input id="otp" type="text" inputmode="numeric" autocomplete="one-time-code" placeholder="6 位数字" maxlength="16" />
        </div>
        <label for="key">管理密钥</label>
        <input id="key" type="password" autocomplete="current-password" placeholder="粘贴后登录" />
        <button type="button" id="btnLogin">登录并进入工作台</button>
        <div id="err" class="err"></div>
        <p class="muted small" style="margin-top:16px;line-height:1.55;">
          建议仅在可信网络环境下使用管理后台，并妥善保管管理密钥。
        </p>
      </div>
    </div>
    <script>
      var ADMIN_BASE = __ADMIN_BASE_JS__;
      var OTP_REQUIRED = __OTP_REQUIRED__;
      function safeNext(){
        var n = new URLSearchParams(location.search).get('next');
        if(!n || n.indexOf('/') !== 0 || n.indexOf('//') === 0) return ADMIN_BASE;
        return n;
      }
      if(OTP_REQUIRED){
        var ob = document.getElementById('otpBlock');
        if(ob) ob.style.display = 'block';
      }
      document.getElementById('btnSendOtp').addEventListener('click', async function(){
        var err = document.getElementById('err');
        err.textContent = '';
        var phone = (document.getElementById('phone').value || '').trim();
        if(!phone){ err.textContent = '请填写手机号'; return; }
        try{
          var r = await fetch('/api/admin/otp/send', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: phone })
          });
          var j = null;
          try{ j = await r.json(); }catch(e){}
          if(!r.ok){
            err.textContent = (j && j.detail) ? String(j.detail) : ('发送失败 HTTP '+r.status);
            return;
          }
          if(j && j.dev_code){ err.textContent = '验证码：'+j.dev_code; }
          else { err.textContent = '验证码已发送，请查收短信'; }
        }catch(e){
          err.textContent = '网络错误：' + (e && e.message ? e.message : String(e));
        }
      });
      document.getElementById('btnLogin').addEventListener('click', async function(){
        var err = document.getElementById('err');
        err.textContent = '';
        var key = (document.getElementById('key').value || '').trim();
        if(!key){ err.textContent = '请填写管理密钥'; return; }
        if(OTP_REQUIRED){
          var phone = (document.getElementById('phone').value || '').trim();
          var otp = (document.getElementById('otp').value || '').trim();
          if(!phone || !otp){ err.textContent = '请填写手机号与短信验证码'; return; }
        }
        try{
          var payload = { key: key };
          if(OTP_REQUIRED){
            payload.phone = (document.getElementById('phone').value || '').trim();
            payload.otp = (document.getElementById('otp').value || '').trim();
          }
          var r = await fetch('/api/admin/login', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if(!r.ok){
            // Avoid leaking internal error structures (e.g. FastAPI 422 detail with field names).
            var j = null;
            try{ j = await r.json(); }catch(e){}
            var msg = '';
            if(j){
              if(typeof j.detail === 'string') msg = j.detail;
              else if(Array.isArray(j.detail) && j.detail.length){
                // FastAPI validation error shape: [{loc:[...], msg:'...', type:'...'}]
                msg = '参数不完整或格式不正确';
              }else if(typeof j.message === 'string') msg = j.message;
            }
            if(!msg){
              msg = (r.status === 401) ? '凭据无效' :
                    (r.status === 403) ? '没有权限' :
                    (r.status === 429) ? '请求过于频繁，请稍后再试' :
                    (r.status >= 500) ? '服务暂时不可用，请稍后再试' :
                    ('登录失败 HTTP ' + r.status);
            }
            err.textContent = '登录失败：' + msg;
            return;
          }
          location.href = safeNext();
        }catch(e){
          err.textContent = '网络错误：' + (e && e.message ? e.message : String(e));
        }
      });
      document.getElementById('key').addEventListener('keydown', function(ev){
        if(ev.key === 'Enter') document.getElementById('btnLogin').click();
      });
    </script>
  </body>
</html>"""
    )
    return (
        s.replace("__ADMIN_BASE_JS__", json.dumps(admin_base, ensure_ascii=False)).replace(
            "__OTP_REQUIRED__", json.dumps(bool(otp_required))
        )
    )


def admin_app_html(admin_base: str) -> str:
    s = (
        """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI24X 管理后台</title>
    <style>"""
        + _COMMON_CSS
        + """
      .layout { display: flex; min-height: 100vh; align-items: stretch; }
      .sidebar {
        width: 268px; flex-shrink: 0; background: var(--panel); border-right: 1px solid var(--border);
        padding: 16px 12px; display: flex; flex-direction: column; gap: 4px;
      }
      .brand { font-weight: 700; font-size: 15px; letter-spacing: 0.02em; }
      .side-hint { font-size: 11px; color: var(--muted); line-height: 1.5; margin: 6px 0 12px; }
      .nav-group-title {
        font-size: 10px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em;
        margin: 14px 0 6px; padding-left: 8px;
      }
      .nav-item {
        display: block; width: 100%; text-align: left; padding: 10px 12px; border-radius: 10px;
        border: 1px solid transparent; background: transparent; color: var(--text); cursor: pointer; font-size: 13px;
      }
      .nav-item:hover { border-color: var(--border); background: var(--panel2); }
      .nav-item.active { border-color: var(--pri); color: var(--pri); background: rgba(96,165,250,0.08); }
      .nav-item .subt { display: block; font-size: 10px; color: var(--muted); margin-top: 2px; font-weight: 400; }
      .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
      .main-top {
        flex-shrink: 0; padding: 10px 16px; border-bottom: 1px solid var(--border);
        background: var(--panel); position: sticky; top: 0; z-index: 3;
      }
      .main-top .msg { display: inline; margin: 0 0 0 8px; vertical-align: middle; }
      .main-scroll { flex: 1; overflow: auto; padding: 16px 16px 32px; }
      .panel-page { display: none; }
      .panel-page.active { display: block; }
      .panel-page > .card:first-child { margin-top: 0; }
      .rk-up { color: #fb7185; }
      .rk-down { color: #34d399; }
    </style>
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <div class="brand">AI24X 管理后台</div>
        <div class="side-hint">
          左侧按「使用频率 / 业务重要性 / 敏感配置」分区。请在可信网络环境下操作并妥善保管敏感信息。
        </div>

        <div class="nav-group-title">日常运维 · 高频</div>
        <button type="button" class="nav-item active" data-panel="p-users">
          用户与配额
          <span class="subt">查询用户、改套餐与剩余次数、看流水</span>
        </button>

        <div class="nav-group-title">收入与安全 · 敏感</div>
        <button type="button" class="nav-item" data-panel="p-wechat">
          微信支付
          <span class="subt">商户号、证书与通知地址</span>
        </button>
        <button type="button" class="nav-item" data-panel="p-orders">
          VIP 订单
          <span class="subt">pay_orders：状态、金额、微信单号</span>
        </button>
        <button type="button" class="nav-item" data-panel="p-commission">
          代理与返佣
          <span class="subt">年 VIP 赠普通代理；20% 返佣台账（T+7 人工结算）</span>
        </button>
        <button type="button" class="nav-item" data-panel="p-sms">
          短信与统一身份
          <span class="subt">主站转发、腾讯短信占位</span>
        </button>

        <div class="nav-group-title">行情与数据 · 运维</div>
        <button type="button" class="nav-item" data-panel="p-market">
          行情路由监控
          <span class="subt">TuShare / 公共源命中情况</span>
        </button>
        <button type="button" class="nav-item" data-panel="p-hotspots-test">
          热点测试页
          <span class="subt">TuShare THS 指数抽样排行（仅测试用）</span>
        </button>
        <button type="button" class="nav-item" data-panel="p-data">
          数据源开关
          <span class="subt">付费源开关、令牌与优先级</span>
        </button>

        <div class="nav-group-title">系统配置</div>
        <button type="button" class="nav-item" data-panel="p-system">
          系统与安全开关
          <span class="subt">管理登录与邀请奖励等全站规则</span>
        </button>

        <div style="flex:1"></div>
        <button type="button" class="nav-item" id="btnLogout" style="margin-top:8px;border-color:var(--border);">
          登出（清除会话 Cookie）
          <span class="subt">脚本调用不受影响</span>
        </button>
      </aside>

      <div class="main">
        <div class="main-top">
          <span class="pill">操作状态</span>
          <span id="status" class="msg">正在校验登录…</span>
        </div>
        <div class="main-scroll">

          <section class="panel-page active" id="p-users">
            <div class="card split">
              <div>
                <div class="row">
                  <label>搜索用户</label>
                  <input id="q" placeholder="手机号片段 或 用户 ID" style="min-width: 240px" title="支持按手机号模糊、或按 userId 精确查找" />
                  <button id="btnSearch">查询</button>
                  <span class="muted small">进入本页自动加载最新用户；可再点查询筛选</span>
                </div>
                <div style="margin-top:12px; overflow:auto;">
                  <table>
                    <thead>
                      <tr>
                        <th style="width:96px;"><span class="th-cn">用户 ID</span><span class="th-en">userId</span></th>
                        <th><span class="th-cn">手机</span><span class="th-en">phone</span></th>
                        <th><span class="th-cn">邮箱</span><span class="th-en">email</span></th>
                        <th style="width:170px;"><span class="th-cn">注册时间</span><span class="th-en">createdAt</span></th>
                        <th style="width:100px;"><span class="th-cn">套餐</span><span class="th-en">plan</span></th>
                        <th style="width:120px;"><span class="th-cn">剩余次数摘要</span><span class="th-en">remaining</span></th>
                        <th style="width:86px;"><span class="th-cn">操作</span><span class="th-en">action</span></th>
                      </tr>
                    </thead>
                    <tbody id="usersBody"></tbody>
                  </table>
                </div>
              </div>
              <div>
                <div class="row">
                  <span class="pill">当前用户</span>
                  <span id="curUser" class="mono muted">—</span>
                </div>
                <div class="msg" id="userMeta"></div>
                <div class="card" style="margin-top:12px;">
                  <div class="row">
                    <span class="pill">配额与套餐</span>
                    <span id="quotaMeta" class="mono muted">—</span>
                  </div>
                  <div class="row" style="margin-top:10px;">
                    <label>套餐 <span class="muted small mono">plan</span></label>
                    <select id="setPlan" title="改为新套餐后保存生效">
                      <option value="">不修改套餐</option>
                      <option value="free">免费 free</option>
                      <option value="vip_trial_99">体验卡 vip_trial_99（7 天·低额度）</option>
                      <option value="vip_month">月度会员 vip_month</option>
                      <option value="vip_year_999">年度会员 vip_year_999</option>
                    </select>
                    <label style="margin-left:10px;">设为「日剩余」</label>
                    <input id="setRemainingDay" type="number" min="0" step="1" placeholder="如 20" style="width:120px" title="直接覆盖当日剩余查询次数，留空表示不覆盖" />
                    <label style="margin-left:10px;">设为「周剩余」</label>
                    <input id="setRemainingWeek" type="number" min="0" step="1" placeholder="如 200" style="width:120px" title="直接覆盖当周剩余，留空表示不覆盖" />
                  </div>
                  <div class="row" style="margin-top:10px;">
                    <label>日剩余 ±</label>
                    <input id="deltaDay" type="number" step="1" placeholder="+10 或 -5" style="width:140px" title="在现有日剩余上加减，留空表示不调整" />
                    <label style="margin-left:10px;">周剩余 ±</label>
                    <input id="deltaWeek" type="number" step="1" placeholder="+50 或 -20" style="width:140px" title="在现有周剩余上加减，留空表示不调整" />
                    <label style="margin-left:10px;">备注</label>
                    <input id="opNote" placeholder="选填：调整原因，写入运维流水" style="min-width:220px" />
                    <button id="btnApplyQuota">应用以上修改</button>
                  </div>
                  <div class="msg danger small">请先通过登录页写入会话；勿对公网暴露本服务且务必使用强管理密钥。</div>
                </div>
                <div class="card" style="margin-top:12px;">
                  <div class="row">
                    <span class="pill">用户基础信息</span>
                    <span class="muted small">邮箱/手机唯一，改错会影响登录归属</span>
                    <button id="btnSaveUserBasic" type="button">保存基础信息</button>
                  </div>
                  <div class="row" style="margin-top:10px;">
                    <label>邮箱 <span class="muted small mono">email</span></label>
                    <input id="editEmail" class="mono" placeholder="如 lei@itxin.com（留空=清空）" style="min-width:240px;" />
                    <label style="margin-left:10px;">手机 <span class="muted small mono">phone</span></label>
                    <input id="editPhone" class="mono" placeholder="如 189xxxx（留空=清空）" style="min-width:200px;" />
                  </div>
                </div>
                <div class="card" style="margin-top:12px;">
                  <div class="row">
                    <span class="pill">密码（管理员强制设置）</span>
                    <span class="muted small">不需要验证码；仅限超级网管</span>
                    <button id="btnAdminSetPw" type="button">保存新密码</button>
                  </div>
                  <div class="row" style="margin-top:10px;">
                    <label>新密码</label>
                    <input id="adminNewPw" type="password" placeholder="至少 6 位（不回显原密码）" style="min-width:240px;" />
                  </div>
                  <div class="msg small muted">提示：会立即覆盖用户密码；请谨慎操作并通知用户重新登录。</div>
                </div>
                <div class="card" style="margin-top:12px;">
                  <div class="row">
                    <span class="pill">最近扣次流水</span>
                    <span class="muted small">每次查询成功后的扣次记录</span>
                    <button id="btnReloadLedger">刷新</button>
                  </div>
                  <div style="margin-top:10px; max-height: 320px; overflow:auto;">
                    <table>
                      <thead>
                        <tr>
                          <th style="width:70px;"><span class="th-cn">序号</span><span class="th-en">id</span></th>
                          <th style="width:120px;"><span class="th-cn">时间</span><span class="th-en">time</span></th>
                          <th><span class="th-cn">标的</span><span class="th-en">secid</span></th>
                          <th style="width:72px;"><span class="th-cn">周期</span><span class="th-en">period</span></th>
                          <th style="width:90px;"><span class="th-cn">结果</span><span class="th-en">result</span></th>
                        </tr>
                      </thead>
                      <tbody id="ledgerBody"></tbody>
                    </table>
                  </div>
                </div>
                <div class="card" style="margin-top:12px;">
                  <div class="row">
                    <span class="pill">运维操作记录</span>
                    <span class="muted small">谁在何时改了配额等</span>
                    <button id="btnReloadOps">刷新</button>
                  </div>
                  <div style="margin-top:10px; max-height: 260px; overflow:auto;">
                    <table>
                      <thead>
                        <tr>
                          <th style="width:70px;"><span class="th-cn">序号</span><span class="th-en">id</span></th>
                          <th style="width:90px;"><span class="th-cn">用户</span><span class="th-en">userId</span></th>
                          <th style="width:120px;"><span class="th-cn">时间</span><span class="th-en">time</span></th>
                          <th style="width:110px;"><span class="th-cn">操作者</span><span class="th-en">actor</span></th>
                          <th><span class="th-cn">动作</span><span class="th-en">action</span></th>
                          <th style="width:220px;"><span class="th-cn">备注</span><span class="th-en">note</span></th>
                        </tr>
                      </thead>
                      <tbody id="opsBody"></tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-wechat">
            <div class="card" id="sec-wechat">
              <div id="wxCurrentSummary" class="msg small" style="margin:0 0 12px; line-height:1.65; padding:10px 12px; border-radius:10px; border:1px solid var(--border); background:var(--panel2);"></div>
              <div class="row">
                <span class="pill">微信支付</span>
                <span class="muted small">保存后立即生效；敏感项不回显明文，需更新时重新粘贴</span>
                <button type="button" id="btnLoadWechat">读取</button>
                <button type="button" id="btnSaveWechat">保存</button>
              </div>
              <div class="field-row" style="margin-top:10px;">
                <div class="field"><span class="lbl">商户号</span><input id="wx_wechat_mch_id" class="mono" style="min-width:200px;" placeholder="mchid" /></div>
                <div class="field"><span class="lbl">AppID</span><input id="wx_wechat_app_id" class="mono" style="min-width:220px;" /></div>
                <div class="field"><span class="lbl">证书序列号</span><input id="wx_wechat_mch_serial_no" class="mono" style="min-width:200px;" /></div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:280px;"><span class="lbl">私钥文件路径</span><input id="wx_wechat_mch_private_key_path" style="width:100%;" placeholder="apiclient_key.pem 绝对或相对路径" /></div>
                <div class="field"><span class="lbl">APIv3 密钥（32 位）</span><input id="wx_wechat_api_v3_key" type="password" autocomplete="off" style="min-width:200px;" placeholder="更新时填写" /></div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:280px;"><span class="lbl">支付结果通知 URL</span><input id="wx_wechat_notify_url" style="width:100%;" placeholder="https://域名/api/billing/wechat/notify" /></div>
                <div class="field" style="min-width:260px;"><span class="lbl">API 域名</span><input id="wx_wechat_pay_host" class="mono" placeholder="默认 api.mch.weixin.qq.com" /></div>
                <div class="field"><span class="lbl">跳过通知验签</span>
                  <select id="wx_wechat_notify_skip_verify" title="仅用于测试环境；线上务必关闭">
                    <option value="">默认</option>
                    <option value="0">关闭（0）</option>
                    <option value="1">开启（1，仅解密）</option>
                  </select>
                </div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:100%;">
                  <span class="lbl">私钥 PEM（可选，与路径二选一）</span>
                  <textarea id="wx_wechat_mch_private_key_pem" rows="4" style="width:100%; font-family:ui-monospace,monospace; font-size:11px;" placeholder="可选：整段粘贴 apiclient_key.pem；保存覆盖库内；留空不修改已存密钥"></textarea>
                </div>
              </div>
              <div class="msg small muted" style="margin-top:8px;">留空表示不修改现有配置；敏感项填了才会更新。保存后可用「VIP 下单/支付」做一次验证。</div>
            </div>
          </section>

          <section class="panel-page" id="p-orders">
            <div class="card" id="sec-orders">
              <div class="row">
                <span class="pill">VIP / 支付订单</span>
                <span class="muted small">数据表 pay_orders；点击表格一行跳转「用户与配额」；改单走微信商户平台；补单能力后期再做</span>
                <button type="button" id="btnLoadOrders">刷新</button>
                <button type="button" id="btnExportOrdersCsv">导出 CSV</button>
              </div>
              <div class="row" style="margin-top:12px; flex-wrap:wrap; gap:10px;">
                <label style="min-width:220px;">关键词 <input id="ordQ" class="mono" style="width:200px;" placeholder="商户单号 / 微信单号 / 用户ID" title="模糊匹配单号；纯数字同时匹配 user_id" /></label>
                <label>用户 ID <input id="ordUserId" type="number" min="0" step="1" placeholder="可选" style="width:100px;" /></label>
                <label>状态
                  <select id="ordStatus" title="订单状态">
                    <option value="">全部</option>
                    <option value="pending">pending（待支付）</option>
                    <option value="paid">paid（已支付）</option>
                  </select>
                </label>
                <label>套餐
                  <select id="ordPlan">
                    <option value="">全部</option>
                    <option value="vip_month">vip_month</option>
                    <option value="vip_year_999">vip_year_999</option>
                    <option value="vip_trial_99">vip_trial_99</option>
                  </select>
                </label>
                <label>每页 <input id="ordLimit" type="number" min="10" max="200" step="10" value="50" style="width:64px;" /></label>
                <button type="button" id="btnOrdPrev">上一页</button>
                <button type="button" id="btnOrdNext">下一页</button>
                <span class="muted small mono" id="ordMeta">—</span>
              </div>
              <div style="margin-top:12px; overflow:auto;">
                <table>
                  <thead>
                    <tr>
                      <th style="width:72px;"><span class="th-cn">订单 id</span><span class="th-en">id</span></th>
                      <th style="width:96px;"><span class="th-cn">用户</span><span class="th-en">userId</span></th>
                      <th style="width:120px;"><span class="th-cn">套餐</span><span class="th-en">plan</span></th>
                      <th style="width:88px;"><span class="th-cn">金额(元)</span><span class="th-en">amount</span></th>
                      <th style="width:88px;"><span class="th-cn">状态</span><span class="th-en">status</span></th>
                      <th style="width:72px;"><span class="th-cn">渠道</span><span class="th-en">channel</span></th>
                      <th style="width:72px;"><span class="th-cn">码</span><span class="th-en">qr</span></th>
                      <th style="width:170px;"><span class="th-cn">创建</span><span class="th-en">created</span></th>
                      <th style="width:170px;"><span class="th-cn">更新</span><span class="th-en">updated</span></th>
                      <th><span class="th-cn">商户单号</span><span class="th-en">out_trade_no</span></th>
                      <th><span class="th-cn">微信单号</span><span class="th-en">transaction_id</span></th>
                    </tr>
                  </thead>
                  <tbody id="ordersBody"></tbody>
                </table>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-commission">
            <div class="card" id="sec-commission">
              <div class="row">
                <span class="pill">代理与返佣（MVP）</span>
                <span class="muted small">返佣仅针对 <code class="mono">vip_year_999</code>；默认不退款；先人工结算</span>
              </div>

              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">动态配置（admin_config）</span>
                  <button type="button" id="btnLoadCommissionCfg">读取</button>
                  <button type="button" id="btnSaveCommissionCfg">保存</button>
                </div>
                <div class="field-row" style="margin-top:12px;">
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">返佣开关</span><span class="sub">agent_commission_enabled</span>
                    <select id="cfgCommEnabled">
                      <option value="1">开启（生成台账）</option>
                      <option value="0">关闭（不生成）</option>
                    </select>
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">普通代理返佣比例</span><span class="sub">agent_commission_rate_normal</span>
                    <input id="cfgCommRate" class="mono" placeholder="0.20" style="min-width:160px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">结算延迟（天）</span><span class="sub">agent_settle_delay_days</span>
                    <input id="cfgCommDelayDays" class="mono" placeholder="7" style="min-width:120px;" />
                  </div>
                </div>
              </div>

              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">待结算（eligible）</span>
                  <span class="muted small">status=pending 且 eligible_at ≤ now</span>
                  <button type="button" id="btnLoadEligible">刷新</button>
                </div>
                <div style="margin-top:12px; overflow:auto;">
                  <table>
                    <thead>
                      <tr>
                        <th style="width:72px;"><span class="th-cn">ID</span><span class="th-en">id</span></th>
                        <th style="width:170px;"><span class="th-cn">订单号</span><span class="th-en">out_trade_no</span></th>
                        <th style="width:96px;"><span class="th-cn">代理</span><span class="th-en">agent</span></th>
                        <th style="width:96px;"><span class="th-cn">买家</span><span class="th-en">buyer</span></th>
                        <th style="width:110px;"><span class="th-cn">金额(分)</span><span class="th-en">amount_fen</span></th>
                        <th style="width:88px;"><span class="th-cn">比例</span><span class="th-en">rate</span></th>
                        <th style="width:110px;"><span class="th-cn">返佣(分)</span><span class="th-en">commission_fen</span></th>
                        <th style="width:170px;"><span class="th-cn">可结算</span><span class="th-en">eligible_at</span></th>
                      </tr>
                    </thead>
                    <tbody id="eligibleBody"></tbody>
                  </table>
                </div>
                <div class="row" style="margin-top:12px; flex-wrap:wrap; gap:10px;">
                  <label>代理ID <input id="paidAgentId" class="mono" placeholder="agent_user_id" style="width:160px;" /></label>
                  <label>备注 <input id="paidNote" placeholder="转账流水/备注（可选）" style="min-width:260px;" /></label>
                  <button type="button" id="btnMarkPaid">标记已打款</button>
                </div>
              </div>

              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">补单（幂等）</span>
                  <span class="muted small">为已支付订单生成返佣台账（回调异常时用）</span>
                </div>
                <div class="row" style="margin-top:10px;">
                  <input id="regenOutTradeNo" class="mono" placeholder="out_trade_no" style="min-width:320px;" />
                  <button type="button" id="btnRegenCommission">生成返佣</button>
                </div>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-sms">
            <div class="card" id="sec-sms">
              <div class="row">
                <span class="pill">短信与统一身份</span>
                <button type="button" id="btnLoadSms">读取</button>
                <button type="button" id="btnSaveSms">保存</button>
              </div>
              <div class="field-row" style="margin-top:10px;">
                <div class="field" style="flex:1; min-width:280px;"><span class="lbl">主站 API 根 URL</span><input id="sms_identity_api_base" style="width:100%;" placeholder="https://api.xxx.com" /></div>
                <div class="field" style="min-width:220px;"><span class="lbl">短信内部密钥</span><input id="sms_internal_key" type="password" autocomplete="off" style="min-width:200px;" placeholder="已配置（不回显；更新时再填写）" /></div>
                <div class="field"><span class="lbl">短信通道</span>
                  <select id="sms_active_provider">
                    <option value="identity_proxy">106接口网（经主站 API，identity_proxy）</option>
                    <option value="tencent">腾讯短信（预留，未接发送）</option>
                  </select>
                </div>
              </div>
              <div class="msg small muted" id="sms-secret-hints" style="margin-top:6px;">
                <span id="sms_internal_key_hint"></span>
              </div>
              <div class="card-title" style="margin-top:14px;">短信防刷（预留，默认关闭）</div>
              <div class="msg small muted" style="margin-top:4px;">
                关闭时不影响现有发码流程；开启后，前端“获取验证码”会自动显示图形码并携带 token，后端校验失败则拒发短信。
              </div>
              <div class="field-row" style="margin-top:10px;">
                <div class="field">
                  <span class="lbl">启用图形码</span>
                  <select id="sms_captcha_enabled">
                    <option value="0">关闭（默认）</option>
                    <option value="1">开启（Turnstile）</option>
                  </select>
                </div>
                <div class="field">
                  <span class="lbl">提供方</span>
                  <select id="sms_captcha_provider">
                    <option value="turnstile">turnstile</option>
                  </select>
                </div>
                <div class="field" style="flex:1; min-width:260px;">
                  <span class="lbl">Site key（前端）</span>
                  <input id="sms_captcha_turnstile_site_key" class="mono" style="width:100%;" placeholder="0x4AAAAAA..." />
                </div>
                <div class="field" style="flex:1; min-width:260px;">
                  <span class="lbl">Secret key（后端）</span>
                  <input id="sms_captcha_turnstile_secret_key" type="password" autocomplete="off" class="mono" style="width:100%;" placeholder="已配置（不回显；更新时再填写）" />
                </div>
              </div>
              <div class="msg small muted" style="margin-top:6px;">
                <span id="sms_captcha_secret_hint"></span>
              </div>
              <div class="card-title" style="margin-top:14px;">106 接口核心</div>
              <div class="msg small muted" style="margin-top:4px;">模板须包含 <span class="mono">{code}</span>。密码不回显，更新时再填。</div>
              <div class="field-row" style="margin-top:10px;">
                <div class="field" style="flex:1; min-width:260px;"><span class="lbl">接口地址</span><input id="sms_106_endpoint" class="mono" style="width:100%;" placeholder="留空表示使用主站默认" /></div>
                <div class="field" style="min-width:160px;"><span class="lbl">账号</span><input id="sms_106_account" class="mono" autocomplete="off" /></div>
                <div class="field" style="min-width:180px;"><span class="lbl">密码</span><input id="sms_106_password" type="password" autocomplete="off" placeholder="已配置（不回显；更新时再填写）" /></div>
              </div>
              <div class="msg small muted" style="margin-top:6px;">
                <span id="sms_106_password_hint"></span>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:200px;"><span class="lbl">签名</span><input id="sms_106_sign_name" style="width:100%;" placeholder="可选" /></div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:100%;">
                  <span class="lbl">内容模板</span>
                  <textarea id="sms_106_template" rows="3" style="width:100%; resize:vertical;" placeholder="须含 {code}，与 106 平台审核文案一致"></textarea>
                </div>
              </div>
              <div class="card-title" style="margin-top:12px;">腾讯短信（预留，后期主通道不稳再接入 SDK）</div>
              <div class="field-row">
                <div class="field"><span class="lbl">SecretId</span><input id="sms_tencent_secret_id" class="mono" /></div>
                <div class="field"><span class="lbl">SecretKey</span><input id="sms_tencent_secret_key" type="password" autocomplete="off" placeholder="已配置（不回显；更新时再填写）" /></div>
                <div class="field"><span class="lbl">SdkAppId</span><input id="sms_tencent_sdk_app_id" class="mono" /></div>
              </div>
              <div class="msg small muted" style="margin-top:6px;">
                <span id="sms_tencent_secret_key_hint"></span>
              </div>
              <div class="field-row">
                <div class="field"><span class="lbl">短信签名</span><input id="sms_tencent_sign" /></div>
                <div class="field"><span class="lbl">模板 ID</span><input id="sms_tencent_template_id" class="mono" /></div>
                <div class="field"><span class="lbl">地域</span><input id="sms_tencent_region" class="mono" placeholder="ap-guangzhou" /></div>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-market">
            <div class="card">
              <div class="row">
                <span class="pill">行情路由监控</span>
                <span class="muted small">看当前是否走 TuShare、以及实际命中的数据源（腾讯/东财等）</span>
                <button id="btnLoadMarket">刷新</button>
              </div>
              <div class="msg small" id="marketMeta">—</div>
              <div style="margin-top:10px; overflow:auto;">
                <table>
                  <thead>
                    <tr>
                      <th><span class="th-cn">数据源</span><span class="th-en">source</span></th>
                      <th style="width:96px;"><span class="th-cn">命中次数</span><span class="th-en">hits</span></th>
                      <th style="width:170px;"><span class="th-cn">最近命中时间</span><span class="th-en">last</span></th>
                    </tr>
                  </thead>
                  <tbody id="routeBody"></tbody>
                </table>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-hotspots-test">
            <div class="card" id="sec-hotspots-test">
              <div class="row">
                <span class="pill">热点（排行）测试</span>
                <span class="muted small">同花顺板块抽样：按近 N 日累计涨跌幅排序（仅测试用）</span>
                <button type="button" id="btnRunHotspotsTest">运行测试</button>
              </div>
              <div class="field-row" style="margin-top:12px;">
                <div class="field" style="min-width:200px;">
                  <span class="lbl">抽样数量</span><span class="sub">sample（≤600，越大越接近全量）</span>
                  <input id="hsSample" type="number" min="1" max="600" step="1" value="600" style="width:140px;" />
                </div>
                <div class="field" style="min-width:200px;">
                  <span class="lbl">TopK</span><span class="sub">topk（≤50）</span>
                  <input id="hsTopK" type="number" min="1" max="50" step="1" value="10" style="width:140px;" />
                </div>
                <div class="field" style="min-width:200px;">
                  <span class="lbl">近30日</span><span class="sub">lookback_long</span>
                  <input id="hsLookbackLong" type="number" min="7" max="120" step="1" value="30" style="width:140px;" />
                </div>
                <div class="field" style="min-width:200px;">
                  <span class="lbl">每日列数</span><span class="sub">daily_days（交易日）</span>
                  <input id="hsDailyDays" type="number" min="5" max="20" step="1" value="10" style="width:140px;" />
                </div>
                <div class="field" style="min-width:200px;">
                  <span class="lbl">并发</span><span class="sub">concurrency（≤10）</span>
                  <input id="hsConc" type="number" min="1" max="10" step="1" value="6" style="width:140px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">同花顺资金榜过滤</span><span class="sub">仅收录“行业资金/概念资金”出现过的板块名</span>
                  <select id="hsGateFunds">
                    <option value="1">开启（推荐）</option>
                    <option value="0">关闭</option>
                  </select>
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">包含地方板块</span><span class="sub">例如：青海等（默认剔除）</span>
                  <select id="hsIncludeRegions">
                    <option value="0">否（推荐）</option>
                    <option value="1">是</option>
                  </select>
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">指数范围</span><span class="sub">默认全量 88xxxx（剔除 883/8820）</span>
                  <select id="hsAllow88xx">
                    <option value="1">全量 88xxxx</option>
                    <option value="0">仅 881/885/886</option>
                  </select>
                </div>
                <div class="field" style="min-width:260px;">
                  <span class="lbl">跌榜口径</span><span class="sub">涨榜=涨跌幅；跌榜=资金尾页（更贴近同花顺）</span>
                  <select id="hsLosersMode">
                    <option value="ths_daily">按涨跌幅（ths_daily）</option>
                    <option value="funds_tail" selected>按资金尾页（行业p2 + 概念p8）</option>
                  </select>
                </div>
              </div>
              <div class="msg small muted" style="margin-top:10px; line-height:1.65;">
                <div class="card-title" style="margin-bottom:6px;">说明</div>
                <div>1) 本测试会调用 TuShare 的 <code class="mono">ths_index</code> 与若干次 <code class="mono">ths_daily</code>。</div>
                <div>2) 已做硬限制：抽样 ≤200、并发 ≤10；避免触发每分钟频次限制。</div>
                <div>3) 真正上线的热点榜建议“收盘后生成快照”，页面只读快照；失败则沿用昨日。</div>
              </div>
              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">跌幅榜测试（按涨跌幅）</span>
                  <span class="muted small">与右侧“每日跌幅榜 10→1”同口径（仅用于对齐核验）</span>
                  <button type="button" id="btnLosersPctDebug">测试</button>
                </div>
                <pre id="hsLosersDebug" class="mono small" style="margin:10px 0 0; padding:10px; max-height:260px; overflow:auto; background:rgba(0,0,0,.06); border-radius:8px; white-space:pre-wrap;">（未运行）</pre>
              </div>
              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">结果对照</span>
                  <span class="muted small mono" id="hsMeta">—</span>
                </div>
                <div class="row" style="margin-top:12px; align-items:flex-start; gap:12px; flex-wrap:wrap;">
                  <div style="min-width:360px; max-width:420px; flex:0 0 420px; overflow:auto;">
                    <div class="card-title">近30日总榜（Top/Bottom）</div>
                    <table>
                      <thead>
                        <tr>
                          <th style="width:56px;">#</th>
                          <th>板块</th>
                          <th style="width:90px;">30日%</th>
                        </tr>
                      </thead>
                      <tbody id="hsLongTop"></tbody>
                      <tbody id="hsLongBottom"></tbody>
                    </table>
                  </div>
                  <div style="flex:1; min-width:720px; overflow:auto;">
                    <div class="card-title">最近交易日每日榜（每列=一天，上10下10）</div>
                    <table>
                      <thead>
                        <tr id="hsGridHead"></tr>
                      </thead>
                      <tbody id="hsGridBody"></tbody>
                    </table>
                  </div>
                </div>
                <div class="card-title" style="margin-top:12px;">失败样例（最多 10 条）</div>
                <pre id="hsFails" class="mono small" style="margin:8px 0 0; padding:10px; max-height:220px; overflow:auto; background:rgba(0,0,0,.06); border-radius:8px; white-space:pre-wrap;">（未运行）</pre>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-data">
            <div class="card">
              <div id="dataCurrentSummary" class="msg small" style="margin:0 0 12px; line-height:1.65; padding:10px 12px; border-radius:10px; border:1px solid var(--border); background:var(--panel2);"></div>
              <div class="row">
                <span class="pill">数据源开关</span>
                <span class="muted small">保存到数据库；约 5 秒内全进程生效（服务端有短缓存）</span>
              </div>
              <div class="field-row">
                <div class="field">
                  <span class="lbl">付费数据源</span>
                  <select id="cfgPaidProvider" title="开/关付费数据源">
                    <option value="">默认（未在后台覆盖）</option>
                    <option value="off">关闭（仅用腾讯/东财等公共源）</option>
                    <option value="tushare">TuShare 付费通道</option>
                  </select>
                </div>
                <div class="field" style="flex:1; min-width:220px;">
                  <span class="lbl">TuShare 令牌</span>
                  <input id="cfgTsToken" placeholder="留空表示不修改已有令牌" style="min-width:220px; width:100%;" title="更新令牌时填写；页面不会显示已保存的明文" />
                </div>
                <div class="field" style="flex:1.2; min-width:280px;">
                  <span class="lbl">请求顺序（逗号分隔）</span>
                  <input id="cfgPriority" placeholder="例如：公共优先 / 付费优先（按需填写）" style="min-width:280px; width:100%;" title="按优先级从左到右" />
                </div>
                <div class="field">
                  <span class="lbl">TuShare 实时 K 线</span>
                  <select id="cfgRtK" title="是否使用 TuShare 实时 K 相关接口（依实现与权限）">
                    <option value="">默认</option>
                    <option value="0">关闭（0）</option>
                    <option value="1">开启（1）</option>
                  </select>
                </div>
                <div class="field">
                  <span class="lbl">仅会员用付费源</span>
                  <select id="cfgVipOnly" title="开启后非会员跳过 TuShare，只用公共源">
                    <option value="">默认：全员可尝试付费源</option>
                    <option value="0">关闭限制（0）</option>
                    <option value="1">仅会员（1）</option>
                  </select>
                </div>
                <div class="field">
                  <span class="lbl">&nbsp;</span>
                  <span class="sub">&nbsp;</span>
                  <div class="row" style="gap:8px;">
                    <button id="btnLoadCfg">从服务器读取</button>
                    <button id="btnSaveCfg">保存到数据库</button>
                  </div>
                </div>
              </div>
              <div class="msg small muted" style="margin-top:12px; line-height:1.6;">
                <div class="card-title" style="margin-bottom:4px;">提示</div>
                <div>1) 开启付费数据源后，请先填写令牌并保存。</div>
                <div>2) 「请求顺序」用于调整优先级；保存后到「行情路由监控」页刷新确认生效。</div>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-system">
            <div class="card">
              <div id="sysCurrentSummary" class="msg small" style="margin:0 0 12px; line-height:1.65; padding:10px 12px; border-radius:10px; border:1px solid var(--border); background:var(--panel2);"></div>
              <div class="row">
                <span class="pill">系统与安全开关</span>
                <span class="muted small">保存后立即生效（无需重启进程）</span>
                <button type="button" id="btnLoadSystem">读取</button>
                <button type="button" id="btnSaveSystem">保存</button>
              </div>
              <div class="field-row" style="margin-top:14px;">
                <div class="field" style="min-width:280px;">
                  <span class="lbl">管理登录短信 OTP</span>
                  <select id="sysAdminOtpEnabled" title="关闭=仅管理密钥登录（预演默认）；开启=须白名单手机 + 短信码 + 管理密钥">
                    <option value="0">关闭</option>
                    <option value="1">开启（公网生产建议）</option>
                  </select>
                </div>
              </div>

              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">邀请奖励配置（MVP）</span>
                  <span class="muted small">保存后对「首次有效查询发奖」立即生效</span>
                  <button type="button" id="btnLoadInviteCfg">读取</button>
                  <button type="button" id="btnSaveInviteCfg">保存</button>
                </div>
                <div class="field-row" style="margin-top:12px;">
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">邀请人奖励（天，可选）</span>
                    <input id="cfgInviteInviterDaily" class="mono" placeholder="0" style="min-width:120px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">邀请人奖励（周）</span>
                    <input id="cfgInviteInviterWeekly" class="mono" placeholder="100" style="min-width:120px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">邀请人周封顶</span>
                    <input id="cfgInviteWeeklyCap" class="mono" placeholder="500" style="min-width:120px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">被邀请人奖励（天，可选）</span>
                    <input id="cfgInviteInviteeDaily" class="mono" placeholder="0" style="min-width:120px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">被邀请人奖励（周）</span>
                    <input id="cfgInviteInviteeWeekly" class="mono" placeholder="50" style="min-width:120px;" />
                  </div>
                </div>
              </div>

              <div class="msg small muted" style="margin-top:14px; line-height:1.65;">
                <div class="card-title" style="margin-bottom:6px;">说明</div>
                <div>1) 开启后，登录页会要求填写短信验证码（需已配置管理员白名单手机号与短信通道）。</div>
                <div>2) 邀请奖励在「好友首次有效查询」时发放；建议配合周封顶使用。</div>
                <div>3) 其它全站级开关后续也会统一放在本菜单。</div>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>

    <script>
      var ADMIN_BASE = __ADMIN_BASE_JS__;
      function $(id){ return document.getElementById(id); }
      function qsa(sel){
        try{ return document.querySelectorAll(sel) || []; }catch(e){ return []; }
      }
      function hasClass(el, cls){
        try{
          var cn = ' ' + String(el.className || '') + ' ';
          return cn.indexOf(' ' + cls + ' ') >= 0;
        }catch(e){ return false; }
      }
      function addClass(el, cls){
        try{
          if(hasClass(el, cls)) return;
          el.className = String(el.className || '').trim() + (String(el.className||'').trim() ? ' ' : '') + cls;
        }catch(e){}
      }
      function removeClass(el, cls){
        try{
          var parts = String(el.className || '').split(/\s+/).filter(function(x){ return x && x !== cls; });
          el.className = parts.join(' ');
        }catch(e){}
      }
      function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, function(c){ return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]); }); }
      // Always surface JS errors (some browsers hide console in compatibility modes)
      try{
        window.onerror = function(msg, src, line, col){
          try{
            var s = '页面脚本错误：' + String(msg||'') + (line?(' @'+line+':'+(col||0)):'');
            if($('status')) $('status').textContent = s;
          }catch(e){}
          return false;
        };
      }catch(e){}
      function fmtCfgLine(label, v){
        if(v === undefined || v === null || String(v).trim() === '')
          return '<span class="muted">'+esc(label)+'</span>：<span class="muted">未配置</span>';
        if(String(v) === '***')
          return '<span class="muted">'+esc(label)+'</span>：<strong>已配置</strong>（敏感项不回显）';
        var s = String(v);
        if(s.length > 140) s = s.slice(0, 137) + '…';
        return '<span class="muted">'+esc(label)+'</span>：<span class="mono">'+esc(s)+'</span>';
      }
      function fmtCfgVal(label, v){
        if(v === undefined || v === null || String(v).trim() === '')
          return '<span class="muted">'+esc(label)+'</span>：<span class="muted">（空）</span>';
        var s = String(v);
        if(s.length > 140) s = s.slice(0, 137) + '…';
        return '<span class="muted">'+esc(label)+'</span>：<span class="mono">'+esc(s)+'</span>';
      }
      function renderItemsSummary(items, pairs){
        var parts = [];
        pairs.forEach(function(p){ parts.push(fmtCfgLine(p.label, items[p.key])); });
        return parts.join('<br/>');
      }
      function fmtTs(ts){
        if(!ts) return '—';
        try{
          var d = new Date(ts*1000);
          function p(n){ return (n<10?'0':'')+n; }
          return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes());
        }catch(e){ return String(ts); }
      }
      function extraAdminHeaders(){
        var h = {};
        try{
          var k = (localStorage.getItem('ai24x_admin_key')||'').trim();
          if(k) h['X-Admin-Key'] = k;
        }catch(e){}
        return h;
      }
      async function api(path, opt){
        var o = Object.assign({}, opt||{});
        var headers = Object.assign({}, extraAdminHeaders(), (o.headers)||{});
        o.headers = headers;
        o.credentials = 'include';
        var r = await fetch(path, o);
        if(r.status === 401){
          var dest = ADMIN_BASE + '/login?next=' + encodeURIComponent(location.pathname + location.search + location.hash);
          location.href = dest;
          throw new Error('Unauthorized');
        }
        if(!r.ok){
          var t = await r.text().catch(function(){ return ''; });
          throw new Error('HTTP '+r.status+' '+t);
        }
        return await r.json();
      }

      var currentUserId = null;
      var ordOffset = 0;
      var ordLastTotal = 0;

      function setStatus(s){ $('status').textContent = s; }

      function ordPageLimit(){
        var lim = parseInt($('ordLimit').value, 10);
        if(isNaN(lim) || lim < 10) lim = 50;
        if(lim > 200) lim = 200;
        return lim;
      }

      function fmtFenYuan(fen){
        var n = Number(fen);
        if(!isFinite(n)) n = 0;
        return (n / 100).toFixed(2);
      }

      function ordFilterQuery(){
        var uid = parseInt($('ordUserId').value, 10);
        if(isNaN(uid) || uid < 0) uid = 0;
        var st = ($('ordStatus').value || '').trim();
        var pl = ($('ordPlan').value || '').trim();
        var sq = ($('ordQ') && $('ordQ').value) ? String($('ordQ').value).trim() : '';
        var qs = '';
        if(uid) qs += '&user_id='+encodeURIComponent(String(uid));
        if(st) qs += '&status='+encodeURIComponent(st);
        if(pl) qs += '&plan='+encodeURIComponent(pl);
        if(sq) qs += '&q='+encodeURIComponent(sq);
        return qs;
      }

      async function loadPayOrders(){
        var lim = ordPageLimit();
        var qs = '?limit='+encodeURIComponent(String(lim))+'&offset='+encodeURIComponent(String(ordOffset))+ordFilterQuery();
        setStatus('正在加载订单…');
        var d = await api('/api/admin/pay_orders'+qs);
        ordLastTotal = parseInt(d.total, 10) || 0;
        $('ordMeta').textContent = '共 '+ordLastTotal+' 条 · offset '+d.offset+' · limit '+d.limit;
        var body = $('ordersBody');
        body.innerHTML = '';
        (d.items || []).forEach(function(it){
          var tr = document.createElement('tr');
          tr.style.cursor = 'pointer';
          tr.title = '点击查看该用户的配额与运维流水';
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono">'+esc(it.user_id)+'</td>'+
            '<td class="mono">'+esc(it.plan)+'</td>'+
            '<td class="mono">'+esc(fmtFenYuan(it.amount_fen))+'</td>'+
            '<td>'+esc(it.status)+'</td>'+
            '<td class="mono">'+esc(it.channel)+'</td>'+
            '<td class="mono">'+(it.has_code_url ? '有' : '—')+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.created_at))+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.updated_at))+'</td>'+
            '<td class="mono" style="max-width:220px;word-break:break-all;">'+esc(it.out_trade_no)+'</td>'+
            '<td class="mono" style="max-width:200px;word-break:break-all;">'+esc(it.transaction_id||'')+'</td>';
          tr.addEventListener('click', async function(){
            try{
              showPanel('p-users');
              $('q').value = String(it.user_id);
              await loadUsers();
              await selectUser(it.user_id);
              setStatus('已打开用户 '+it.user_id+'，可在下方查看配额与「运维操作记录」（含 billing:vip）');
            }catch(e){ setStatus('跳转用户失败：'+e.message); }
          });
          body.appendChild(tr);
        });
        setStatus('订单已加载，本页 '+((d.items||[]).length)+' 条');
      }

      async function exportPayOrdersCsv(){
        var qs = '?cap=5000'+ordFilterQuery();
        var headers = Object.assign({ 'Accept': 'text/csv' }, extraAdminHeaders());
        setStatus('正在导出 CSV…');
        var r = await fetch('/api/admin/pay_orders_export'+qs, { credentials: 'include', headers: headers });
        if(r.status === 401){
          var dest = ADMIN_BASE + '/login?next=' + encodeURIComponent(location.pathname + location.search + location.hash);
          location.href = dest;
          throw new Error('Unauthorized');
        }
        if(!r.ok){
          var t = await r.text().catch(function(){ return ''; });
          throw new Error('HTTP '+r.status+' '+t);
        }
        var blob = await r.blob();
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'pay_orders_export.csv';
        a.click();
        URL.revokeObjectURL(a.href);
        setStatus('已下载 pay_orders_export.csv（当前筛选，最多 5000 条）');
      }

      async function loadCommissionCfg(){
        var d = await api('/api/admin/config');
        var it = d.items || {};
        $('cfgCommEnabled').value = (it.agent_commission_enabled != null && String(it.agent_commission_enabled).trim() !== '') ? String(it.agent_commission_enabled).trim() : '1';
        $('cfgCommRate').value = (it.agent_commission_rate_normal != null) ? String(it.agent_commission_rate_normal) : '';
        $('cfgCommDelayDays').value = (it.agent_settle_delay_days != null) ? String(it.agent_settle_delay_days) : '';
      }

      async function loadInviteCfg(){
        var d = await api('/api/admin/config');
        var it = d.items || {};
        if($('cfgInviteInviterWeekly')) $('cfgInviteInviterWeekly').value = (it.invite_reward_inviter_weekly != null) ? String(it.invite_reward_inviter_weekly) : '';
        if($('cfgInviteInviteeWeekly')) $('cfgInviteInviteeWeekly').value = (it.invite_reward_invitee_weekly != null) ? String(it.invite_reward_invitee_weekly) : '';
        if($('cfgInviteWeeklyCap')) $('cfgInviteWeeklyCap').value = (it.invite_weekly_cap != null) ? String(it.invite_weekly_cap) : '';
        if($('cfgInviteInviterDaily')) $('cfgInviteInviterDaily').value = (it.invite_reward_inviter_daily != null) ? String(it.invite_reward_inviter_daily) : '';
        if($('cfgInviteInviteeDaily')) $('cfgInviteInviteeDaily').value = (it.invite_reward_invitee_daily != null) ? String(it.invite_reward_invitee_daily) : '';
      }

      async function saveInviteCfg(){
        var iw = String(($('cfgInviteInviterWeekly') && $('cfgInviteInviterWeekly').value) || '').trim();
        var ew = String(($('cfgInviteInviteeWeekly') && $('cfgInviteInviteeWeekly').value) || '').trim();
        var cap = String(($('cfgInviteWeeklyCap') && $('cfgInviteWeeklyCap').value) || '').trim();
        var id = String(($('cfgInviteInviterDaily') && $('cfgInviteInviterDaily').value) || '').trim();
        var ed = String(($('cfgInviteInviteeDaily') && $('cfgInviteInviteeDaily').value) || '').trim();
        var tasks = [];
        if(iw !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'invite_reward_inviter_weekly', value: iw})}));
        if(ew !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'invite_reward_invitee_weekly', value: ew})}));
        if(cap !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'invite_weekly_cap', value: cap})}));
        if(id !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'invite_reward_inviter_daily', value: id})}));
        if(ed !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'invite_reward_invitee_daily', value: ed})}));
        if(tasks.length === 0){ setStatus('未检测到修改（为空的输入不会覆盖原配置）'); return; }
        setStatus('正在保存邀请奖励配置…');
        await Promise.all(tasks);
        setStatus('邀请奖励配置已写入数据库');
        await loadInviteCfg();
      }

      async function saveCommissionCfg(){
        var en = String($('cfgCommEnabled').value || '1').trim();
        var rt = String($('cfgCommRate').value || '').trim();
        var dd = String($('cfgCommDelayDays').value || '').trim();
        var tasks = [];
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_enabled', value: en})}));
        if(rt !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_rate_normal', value: rt})}));
        if(dd !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_settle_delay_days', value: dd})}));
        setStatus('正在保存返佣配置…');
        await Promise.all(tasks);
        setStatus('返佣配置已写入数据库');
        await loadCommissionCfg();
      }

      async function loadEligibleCommissions(){
        setStatus('正在加载待结算返佣…');
        var d = await api('/api/admin/commissions?eligible_only=1&limit=200&offset=0');
        var body = $('eligibleBody');
        body.innerHTML = '';
        (d.items || []).forEach(function(it){
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono" style="max-width:220px;word-break:break-all;">'+esc(it.out_trade_no)+'</td>'+
            '<td class="mono">'+esc(it.agent_user_id)+'</td>'+
            '<td class="mono">'+esc(it.buyer_user_id)+'</td>'+
            '<td class="mono">'+esc(it.amount_fen)+'</td>'+
            '<td class="mono">'+esc(it.rate)+'</td>'+
            '<td class="mono">'+esc(it.commission_fen)+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.eligible_at))+'</td>';
          body.appendChild(tr);
        });
        setStatus('待结算返佣已刷新（'+(d.items||[]).length+'条）');
      }

      async function markAgentPaid(){
        var uid = parseInt($('paidAgentId').value, 10);
        if(!uid || uid <= 0){ setStatus('请填写 agent_user_id'); return; }
        var note = String($('paidNote').value || '').trim();
        setStatus('正在标记已打款…');
        var r = await api('/api/admin/commissions/mark_paid', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({agent_user_id: uid, note: note})});
        setStatus('已标记：'+r.count+' 笔 · 合计 '+fmtFenYuan(r.total_fen)+' 元');
        await loadEligibleCommissions();
      }

      async function regenCommissionForOrder(){
        var otn = String($('regenOutTradeNo').value || '').trim();
        if(!otn){ setStatus('请填写 out_trade_no'); return; }
        setStatus('正在生成返佣台账（幂等）…');
        var r = await api('/api/admin/commissions/generate_for_order', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({out_trade_no: otn})});
        if(r && r.skipped) setStatus('已跳过：'+(r.reason||'skipped'));
        else setStatus('已处理：inserted='+(r.inserted?'1':'0'));
        await loadEligibleCommissions();
      }

      async function runHotspotsTest(){
        var sample = parseInt($('hsSample').value, 10) || 80;
        var topk = parseInt($('hsTopK').value, 10) || 10;
        var daysLong = parseInt($('hsLookbackLong').value, 10) || 30;
        var dailyDays = parseInt($('hsDailyDays').value, 10) || 10;
        var conc = parseInt($('hsConc').value, 10) || 6;
        var gate = parseInt($('hsGateFunds').value, 10);
        var incR = parseInt($('hsIncludeRegions').value, 10);
        var a88 = parseInt($('hsAllow88xx').value, 10);
        var lm = $('hsLosersMode') ? String($('hsLosersMode').value||'funds_tail') : 'funds_tail';
        sample = Math.max(1, Math.min(sample, 600));
        topk = Math.max(1, Math.min(topk, 50));
        daysLong = Math.max(7, Math.min(daysLong, 120));
        dailyDays = Math.max(5, Math.min(dailyDays, 20));
        conc = Math.max(1, Math.min(conc, 10));
        gate = isNaN(gate) ? 1 : gate;
        incR = isNaN(incR) ? 0 : incR;
        a88 = isNaN(a88) ? 1 : a88;
        lm = String(lm||'funds_tail').trim();
        setStatus('正在运行热点矩阵…（sample '+sample+' / top '+topk+' / long '+daysLong+'d / daily '+dailyDays+' cols / conc '+conc+'）');
        var d = await api('/api/admin/hotspots/grid?sample='+encodeURIComponent(sample)+'&topk='+encodeURIComponent(topk)+'&long_days='+encodeURIComponent(daysLong)+'&daily_days='+encodeURIComponent(dailyDays)+'&concurrency='+encodeURIComponent(conc)+'&gate_funds='+encodeURIComponent(gate)+'&include_regions='+encodeURIComponent(incR)+'&allow_88xx='+encodeURIComponent(a88)+'&losers_mode='+encodeURIComponent(lm));
        var metaEl = $('hsMeta');
        var failsEl = $('hsFails');
        var longTopEl = $('hsLongTop');
        var longBottomEl = $('hsLongBottom');
        var gridHead = $('hsGridHead');
        var gridBody = $('hsGridBody');
        if(!d || !d.ok){
          if(metaEl) metaEl.textContent = (d && d.error) ? String(d.error) : 'failed';
          if(failsEl) failsEl.textContent = JSON.stringify(d || {}, null, 2);
          if(longTopEl) longTopEl.innerHTML = '';
          if(longBottomEl) longBottomEl.innerHTML = '';
          if(gridHead) gridHead.innerHTML = '';
          if(gridBody) gridBody.innerHTML = '';
          setStatus('热点测试失败：'+(d && d.error ? d.error : 'unknown'));
          return;
        }
        var m = d.meta || {};
        if(metaEl){
          metaEl.textContent =
            'elapsed '+(m.elapsed_ms||'?')+'ms · picked '+(m.items_picked||0)+' after_filter '+(m.items_after_filter||0)+' · daily_cols '+((m.daily_dates||[]).length||0)+' · fail '+(m.items_fail||0)+
            ' · losers_source '+esc(m.losers_source||'');
        }
        if(failsEl) failsEl.textContent = JSON.stringify(d.fails_head || [], null, 2);

        function renderLong(tbody, items, mode){
          if(!tbody) return;
          tbody.innerHTML = '';
          (items || []).forEach(function(it, idx){
            var win = (it.window_pct_change == null) ? '' : Number(it.window_pct_change).toFixed(2);
            var tr = document.createElement('tr');
            var rn = 0;
            if(mode === 'top') rn = idx+1;
            else if(mode === 'bottom') rn = (items||[]).length - idx;
            else rn = idx+1;
            tr.innerHTML =
              '<td class="mono '+(mode==='top'?'rk-up':(mode==='bottom'?'rk-down':''))+'">'+esc(rn)+'</td>'+
              '<td>'+esc(it.name||'')+'</td>'+
              '<td class="mono">'+esc(win)+'</td>';
            tbody.appendChild(tr);
          });
        }
        renderLong(longTopEl, d.long && d.long.top ? d.long.top : [], 'top');
        // For long bottom, show 10→1 with 10 least-bad, 1 worst.
        var lb = (d.long && d.long.bottom_display) ? d.long.bottom_display : ((d.long && d.long.bottom) ? d.long.bottom : []);
        renderLong(longBottomEl, lb || [], 'bottom');

        // Grid header: first column is rank, then each trade_date column
        if(gridHead){
          var h = '<th style="width:56px;">#</th>';
          function fmtMd(td){
            try{
              td = String(td||'').trim();
              if(td.length===8 && /^\d+$/.test(td)){
                var m = parseInt(td.slice(4,6),10)||0;
                var da = parseInt(td.slice(6,8),10)||0;
                if(m>0 && da>0) return m+'月'+da+'日';
              }
            }catch(e){}
            return String(td||'');
          }
          // newest date on the left
          var colsH = (d.daily || []).slice().reverse();
          colsH.forEach(function(col){
            var td = String(col.trade_date||'');
            h += '<th style="min-width:110px;" class="mono">'+esc(fmtMd(td))+'</th>';
          });
          gridHead.innerHTML = h;
        }
        // Build 20 rows: 1..topk, then -1..-topk
        if(gridBody){
          gridBody.innerHTML = '';
          // newest date on the left
          var cols = (d.daily || []).slice().reverse();
          function cellName(col, i, isBottom){
            try{
              var arr = isBottom ? (col.bottom_display||col.bottom||[]) : (col.top||[]);
              var it = arr[i] || null;
              return it ? String(it.name||'') : '';
            }catch(e){ return ''; }
          }
          for(var i=0;i<topk;i++){
            var tr = document.createElement('tr');
            var row = '<td class="mono rk-up">'+esc(i+1)+'</td>';
            cols.forEach(function(col){
              var nm = cellName(col, i, false);
              row += '<td>'+esc(nm)+'</td>';
            });
            tr.innerHTML = row;
            gridBody.appendChild(tr);
          }
          for(var j=0;j<topk;j++){
            var tr2 = document.createElement('tr');
            var row2 = '<td class="mono rk-down">'+esc(topk-j)+'</td>';
            cols.forEach(function(col){
              // For "倒数榜 10→1": row 10 is the least-bad among losers, row 1 is the worst.
              var nm2 = cellName(col, j, true);
              row2 += '<td>'+esc(nm2)+'</td>';
            });
            tr2.innerHTML = row2;
            gridBody.appendChild(tr2);
          }
        }
        // Also print a compact debug line for today's bottom list.
        try{
          var todayCol = (d.daily && d.daily.length) ? d.daily[d.daily.length-1] : null;
          var btm = todayCol ? (todayCol.bottom_display||todayCol.bottom||[]) : [];
          var names = (btm||[]).slice(0, topk).map(function(x){
            if(!x) return '';
            var nm = String(x.name||'');
            var p = (x.pct_change==null) ? '' : (' '+Number(x.pct_change).toFixed(2)+'%');
            var n = (x.net_yi==null) ? '' : (' '+Number(x.net_yi).toFixed(2)+'亿');
            return nm + p + n;
          }).filter(function(s){ return s; });
          if(failsEl){
            failsEl.textContent = (failsEl.textContent||'') + '\\n\\n[今日 bottom10 口径='+String(m.losers_source||'')+']\\n' + names.join('\\n');
          }
        }catch(e){}
        setStatus('热点矩阵完成（30日Top/Bottom各'+topk+'；每日列 '+((d.daily||[]).length||0)+'）');
      }

      async function runLosersPctDebug(){
        var outEl = $('hsLosersDebug');
        if(outEl) outEl.textContent = '加载中…';
        try{
          var sample = parseInt($('hsSample').value, 10) || 600;
          var topk = parseInt($('hsTopK').value, 10) || 10;
          var daysLong = parseInt($('hsLookbackLong').value, 10) || 30;
          var dailyDays = parseInt($('hsDailyDays').value, 10) || 10;
          var conc = parseInt($('hsConc').value, 10) || 6;
          var gate = parseInt($('hsGateFunds').value, 10);
          var incR = parseInt($('hsIncludeRegions').value, 10);
          var a88 = parseInt($('hsAllow88xx').value, 10);
          sample = Math.max(1, Math.min(sample, 600));
          topk = Math.max(1, Math.min(topk, 20));
          daysLong = Math.max(7, Math.min(daysLong, 120));
          dailyDays = Math.max(5, Math.min(dailyDays, 20));
          conc = Math.max(1, Math.min(conc, 10));
          gate = isNaN(gate) ? 1 : gate;
          incR = isNaN(incR) ? 0 : incR;
          a88 = isNaN(a88) ? 1 : a88;
          var lm = $('hsLosersMode') ? String($('hsLosersMode').value||'funds_tail') : 'funds_tail';
          var d = await api('/api/admin/hotspots/grid?sample='+encodeURIComponent(sample)+'&topk='+encodeURIComponent(topk)+'&long_days='+encodeURIComponent(daysLong)+'&daily_days='+encodeURIComponent(dailyDays)+'&concurrency='+encodeURIComponent(conc)+'&gate_funds='+encodeURIComponent(gate)+'&include_regions='+encodeURIComponent(incR)+'&allow_88xx='+encodeURIComponent(a88)+'&losers_mode='+encodeURIComponent(lm));
          if(!d || !d.ok) throw new Error('grid_failed');
          var todayCol = (d.daily && d.daily.length) ? d.daily[d.daily.length-1] : null;
          var td = todayCol ? String(todayCol.trade_date||'') : '';
          var btm = todayCol ? (todayCol.bottom_display||todayCol.bottom||[]) : [];
          var lines = [];
          lines.push('【交易日】'+td);
          lines.push('【跌榜 10→1（口径='+lm+'）】');
          for(var i=0;i<Math.min(topk, (btm||[]).length);i++){
            var it = btm[i] || {};
            var nm = String(it.name||'');
            var pct = (it.pct_change==null) ? '' : Number(it.pct_change).toFixed(2)+'%';
            lines.push(String(topk - i).padStart(2,' ')+'  '+nm+'  '+pct);
          }
          if(outEl) outEl.textContent = lines.join('\\\\n');
          setStatus('已生成跌幅榜结果');
        }catch(e){
          if(outEl) outEl.textContent = '失败：' + (e && e.message ? e.message : String(e||''));
          setStatus('生成失败：'+(e && e.message ? e.message : 'unknown'));
        }
      }

      function showPanel(id){
        try{
          var pages = qsa('.panel-page');
          for(var i=0;i<pages.length;i++){
            var p = pages[i];
            if(!p || !p.id) continue;
            if(p.id === id) addClass(p, 'active');
            else removeClass(p, 'active');
          }
          var navs = qsa('.nav-item[data-panel]');
          for(var j=0;j<navs.length;j++){
            var b = navs[j];
            if(!b) continue;
            if(b.getAttribute('data-panel') === id) addClass(b, 'active');
            else removeClass(b, 'active');
          }
        }catch(e){
          try{ setStatus('切换菜单失败：'+(e && e.message ? e.message : String(e))); }catch(e2){}
        }
        if(id === 'p-users'){
          loadUsers().catch(function(e){ setStatus('用户列表：'+e.message); });
        }
        if(id === 'p-orders'){
          ordOffset = 0;
          loadPayOrders().catch(function(e){ setStatus('订单：'+e.message); });
        }
        if(id === 'p-system'){
          loadSystem().catch(function(e){ setStatus('系统配置读取失败：'+e.message); });
          loadInviteCfg().catch(function(e){ setStatus('邀请配置读取失败：'+e.message); });
        }
        if(id === 'p-wechat'){
          loadWechat().catch(function(e){ setStatus('微信支付配置：'+e.message); });
        }
        if(id === 'p-sms'){
          loadSms().catch(function(e){ setStatus('短信配置：'+e.message); });
        }
        if(id === 'p-data'){
          loadConfig().catch(function(e){ setStatus('数据源配置：'+e.message); });
        }
        if(id === 'p-commission'){
          loadCommissionCfg().catch(function(e){ setStatus('返佣配置读取失败：'+e.message); });
          loadEligibleCommissions().catch(function(e){ setStatus('待结算读取失败：'+e.message); });
        }
        if(id === 'p-hotspots-test'){
          // manual run only
        }
        try{ history.replaceState(null, '', '#'+id); }catch(e){}
      }

      async function loadSystem(){
        var d = await api('/api/admin/config');
        var it = d.items || {};
        var v = String(it.admin_browser_otp_enabled != null ? it.admin_browser_otp_enabled : '0').trim().toLowerCase();
        var on = (v === '1' || v === 'true' || v === 'yes' || v === 'on');
        var sel = $('sysAdminOtpEnabled');
        if(sel) sel.value = on ? '1' : '0';
        var sum = $('sysCurrentSummary');
        if(sum){
          sum.innerHTML =
            '<div class="card-title" style="margin-bottom:6px;">当前配置</div>' +
            renderItemsSummary(it, [
              {label:'管理登录短信 OTP', key:'admin_browser_otp_enabled'},
              {label:'付费数据源开关', key:'paid_provider'},
              {label:'请求顺序', key:'paid_provider_priority'},
              {label:'实时 K 线开关', key:'tushare_use_rt_k'},
              {label:'仅会员用付费源', key:'paid_vip_only'},
              {label:'邀请人奖励（周）', key:'invite_reward_inviter_weekly'},
              {label:'被邀请人奖励（周）', key:'invite_reward_invitee_weekly'},
              {label:'邀请人周封顶', key:'invite_weekly_cap'},
            ]) +
            '<p class="muted small" style="margin:10px 0 0;">未显示的项：保持默认配置。</p>';
        }
      }

      async function saveSystem(){
        var sel = $('sysAdminOtpEnabled');
        var v = sel ? String(sel.value || '0') : '0';
        setStatus('正在保存系统配置…');
        await api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'admin_browser_otp_enabled', value: v})});
        setStatus('已保存。若改了管理 OTP 开关，请新开标签打开「登录页」验证（或通知他人重新登录）。');
      }

      async function loadUsers(){
        var q = $('q').value.trim();
        setStatus('正在加载用户列表…');
        var data = await api('/api/admin/users?q='+encodeURIComponent(q));
        var body = $('usersBody');
        body.innerHTML = '';
        data.items.forEach(function(u){
          var tr = document.createElement('tr');
          tr.style.cursor='pointer';
          tr.innerHTML =
            '<td class="mono">'+esc(u.id)+'</td>'+
            '<td class="mono">'+esc(u.phone||'')+'</td>'+
            '<td class="mono">'+esc(u.email||'')+'</td>'+
            '<td class="mono">'+esc(fmtTs(u.created_at))+'</td>'+
            '<td>'+esc(u.quota ? u.quota.plan : '')+'</td>'+
            '<td class="mono">'+esc(u.quota ? u.quota.remaining : '')+'</td>'+
            '<td><button type="button" class="mono" style="padding:6px 10px;border-radius:10px;" data-act="edit">编辑</button></td>';
          tr.addEventListener('click', function(){ selectUser(u.id); });
          tr.querySelector('button[data-act="edit"]').addEventListener('click', function(ev){
            ev.preventDefault();
            ev.stopPropagation();
            selectUser(u.id);
            try{ document.getElementById('curUser').scrollIntoView({behavior:'smooth', block:'start'}); }catch(e){}
          });
          body.appendChild(tr);
        });
        setStatus('查询完成，共 '+data.items.length+' 条');
      }

      async function selectUser(uid){
        currentUserId = uid;
        $('curUser').textContent = String(uid);
        $('ledgerBody').innerHTML = '';
        $('opsBody').innerHTML = '';
        $('userMeta').textContent = '正在加载用户详情…';
        $('quotaMeta').textContent = '—';
        if($('editEmail')) $('editEmail').value = '';
        if($('editPhone')) $('editPhone').value = '';
        $('setRemainingDay').value = '';
        $('setRemainingWeek').value = '';
        $('deltaDay').value = '';
        $('deltaWeek').value = '';
        $('opNote').value = '';
        $('setPlan').value = '';
        if($('btnApplyQuota')) $('btnApplyQuota').disabled = false;

        var d = await api('/api/admin/user/'+encodeURIComponent(uid));
        var u = d.user || {};
        var inv = d.invite || {};
        var metaParts = [];
        if (u.phone) metaParts.push('手机 <span class="mono">'+esc(u.phone)+'</span>');
        if (u.email) metaParts.push('邮箱 <strong class="mono">'+esc(u.email)+'</strong>');
        metaParts.push('注册时间 <span class="mono">'+esc(fmtTs(u.created_at))+'</span>');
        if (inv.my_code) metaParts.push('邀请码 <span class="mono">'+esc(inv.my_code)+'</span>');
        if (inv.inviter_id) metaParts.push('邀请人 <span class="mono">'+esc(inv.inviter_id)+'</span>');
        $('userMeta').innerHTML = metaParts.join(' · ');
        if($('editEmail')) $('editEmail').value = u.email || '';
        if($('editPhone')) $('editPhone').value = u.phone || '';
        if(d.quota){
          $('quotaMeta').textContent =
            '套餐 '+d.quota.plan+
            ' · 剩余摘要 '+d.quota.remaining+
            '（当日 '+d.quota.remaining_day+'/'+d.quota.daily_limit+' · 当周 '+(d.quota.remaining_week!=null?d.quota.remaining_week:d.quota.remaining_month)+'/'+(d.quota.weekly_limit!=null?d.quota.weekly_limit:d.quota.monthly_limit)+'）';
        }
        await loadLedger();
        await loadOps();
      }

      async function saveUserBasic(){
        if(!currentUserId) return;
        var email = ($('editEmail').value || '').trim();
        var phone = ($('editPhone').value || '').trim();
        setStatus('正在保存用户基础信息…');
        await api('/api/admin/user/'+encodeURIComponent(currentUserId)+'/basic_update', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({email: email, phone: phone})
        });
        await selectUser(currentUserId);
        setStatus('已保存用户基础信息。');
      }

      async function adminSetPassword(){
        if(!currentUserId) return;
        var npw = ($('adminNewPw') && $('adminNewPw').value) ? String($('adminNewPw').value) : '';
        if(!npw || npw.length < 6) throw new Error('新密码至少 6 位');
        setStatus('正在保存新密码…');
        await api('/api/admin/user/'+encodeURIComponent(currentUserId)+'/password_set', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({new_password: npw})
        });
        if($('adminNewPw')) $('adminNewPw').value = '';
        setStatus('密码已更新。');
      }

      async function loadLedger(){
        if(!currentUserId) return;
        var d = await api('/api/admin/quota_ledger?user_id='+encodeURIComponent(currentUserId)+'&limit=50');
        var body = $('ledgerBody');
        body.innerHTML = '';
        (d.items||[]).forEach(function(it){
          var tr=document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.consumed_at))+'</td>'+
            '<td class="mono">'+esc(it.secid)+'</td>'+
            '<td>'+esc(it.period)+'</td>'+
            '<td>'+esc(it.result)+'</td>';
          body.appendChild(tr);
        });
      }

      async function loadOps(){
        if(!currentUserId) return;
        var d = await api('/api/admin/ops_ledger?user_id='+encodeURIComponent(currentUserId)+'&limit=50');
        var body = $('opsBody');
        body.innerHTML = '';
        (d.items||[]).forEach(function(it){
          var tr=document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono">'+esc(it.user_id)+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.created_at))+'</td>'+
            '<td class="mono">'+esc(it.actor||'')+'</td>'+
            '<td class="mono">'+esc(it.action||'')+'</td>'+
            '<td>'+esc(it.note||'')+'</td>';
          body.appendChild(tr);
        });
      }

      async function applyQuota(){
        if(!currentUserId) return;
        var plan = ($('setPlan').value||'').trim();
        var sDay = ($('setRemainingDay').value||'').trim();
        var sWeek = ($('setRemainingWeek').value||'').trim();
        var dDay = ($('deltaDay').value||'').trim();
        var dWeek = ($('deltaWeek').value||'').trim();
        var note = ($('opNote').value||'').trim();

        var body = {};
        if(plan) body.plan = plan;
        if(sDay !== '') body.set_remaining_day = Math.max(0, Math.floor(Number(sDay)));
        if(sWeek !== '') body.set_remaining_week = Math.max(0, Math.floor(Number(sWeek)));
        if(dDay !== '') body.delta_day = Math.floor(Number(dDay));
        if(dWeek !== '') body.delta_week = Math.floor(Number(dWeek));
        if(note) body.note = note;

        if(Object.keys(body).length===0){ setStatus('请至少填写一项配额或套餐修改'); return; }
        setStatus('正在提交配额调整…');

        var d = await api('/api/admin/user/'+encodeURIComponent(currentUserId)+'/quota_adjust', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify(body)
        });
        setStatus('已更新：套餐 '+d.quota.plan+' · 剩余摘要 '+d.quota.remaining+'（当日 '+d.quota.remaining_day+' · 当周 '+d.quota.remaining_week+'）');
        await selectUser(currentUserId);
      }

      async function loadConfig(){
        var d = await api('/api/admin/config');
        var items = d.items || {};
        $('cfgPaidProvider').value = (items.paid_provider != null ? String(items.paid_provider) : '');
        $('cfgPriority').value = (items.paid_provider_priority != null ? String(items.paid_provider_priority) : '');
        $('cfgRtK').value = (items.tushare_use_rt_k != null ? String(items.tushare_use_rt_k) : '');
        $('cfgVipOnly').value = (items.paid_vip_only != null ? String(items.paid_vip_only) : '');
        $('cfgTsToken').value = '';
        var ds = $('dataCurrentSummary');
        if(ds){
          ds.innerHTML =
            '<div class="card-title" style="margin-bottom:6px;">当前配置</div>' +
            renderItemsSummary(items, [
              {label:'付费数据源', key:'paid_provider'},
              {label:'请求顺序', key:'paid_provider_priority'},
              {label:'实时 K 线', key:'tushare_use_rt_k'},
              {label:'仅会员用付费源', key:'paid_vip_only'},
            ]) +
            '<p class="muted small" style="margin:10px 0 0;">令牌已保存时不会在页面显示；需要更新时在下方输入框填写后保存。</p>';
        }
      }

      async function loadWechat(){
        var d = await api('/api/admin/config');
        var it = d.items || {};
        function put(k, elId){
          var el = $(elId);
          if(!el) return;
          var v = it[k];
          if(v === undefined || v === null) { el.value = ''; return; }
          if(String(v) === '***') { el.value = ''; return; }
          el.value = String(v);
        }
        put('wechat_mch_id','wx_wechat_mch_id');
        put('wechat_app_id','wx_wechat_app_id');
        put('wechat_mch_serial_no','wx_wechat_mch_serial_no');
        put('wechat_mch_private_key_path','wx_wechat_mch_private_key_path');
        put('wechat_notify_url','wx_wechat_notify_url');
        put('wechat_pay_host','wx_wechat_pay_host');
        put('wechat_notify_skip_verify','wx_wechat_notify_skip_verify');
        $('wx_wechat_api_v3_key').value = '';
        $('wx_wechat_mch_private_key_pem').value = '';
        var wxs = $('wxCurrentSummary');
        if(wxs){
          wxs.innerHTML =
            '<div class="card-title" style="margin-bottom:6px;">当前配置</div>' +
            renderItemsSummary(it, [
              {label:'商户号', key:'wechat_mch_id'},
              {label:'AppID', key:'wechat_app_id'},
              {label:'证书序列号', key:'wechat_mch_serial_no'},
              {label:'私钥文件路径', key:'wechat_mch_private_key_path'},
              {label:'通知地址', key:'wechat_notify_url'},
              {label:'API 域名', key:'wechat_pay_host'},
              {label:'跳过通知验签', key:'wechat_notify_skip_verify'},
              {label:'APIv3 密钥', key:'wechat_api_v3_key'},
              {label:'私钥 PEM', key:'wechat_mch_private_key_pem'},
            ]) +
            '<p class="muted small" style="margin:10px 0 0;">敏感项已保存时不会在页面显示；需要更新时在下方表单填写后保存。</p>';
        }
      }

      async function saveWechat(){
        var tasks = [];
        var simple = ['wechat_mch_id','wechat_app_id','wechat_mch_serial_no','wechat_mch_private_key_path','wechat_notify_url','wechat_pay_host','wechat_notify_skip_verify'];
        simple.forEach(function(k){
          var el = $('wx_'+k);
          var v = el ? String(el.value||'').trim() : '';
          tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:k, value:v})}));
        });
        var v3 = String($('wx_wechat_api_v3_key').value||'').trim();
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'wechat_api_v3_key', value:v3})}));
        var pem = String($('wx_wechat_mch_private_key_pem').value||'').trim();
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'wechat_mch_private_key_pem', value:pem})}));
        setStatus('正在保存微信支付配置…');
        await Promise.all(tasks);
        setStatus('微信支付配置已写入数据库');
        await loadWechat();
      }

      async function loadSms(){
        var eff = await api('/api/admin/sms_effective');
        // Keep snapshot for safe "save only changes" behavior.
        window.__smsEff = eff || {};
        function putVal(elId, v){
          var el = $(elId);
          if(!el) return;
          el.value = (v !== undefined && v !== null) ? String(v) : '';
        }
        putVal('sms_identity_api_base', eff.identity_api_base || '');
        putVal('sms_active_provider', eff.sms_active_provider || 'identity_proxy');
        putVal('sms_captcha_enabled', eff.sms_captcha_enabled || '0');
        putVal('sms_captcha_provider', eff.sms_captcha_provider || 'turnstile');
        putVal('sms_captcha_turnstile_site_key', eff.sms_captcha_turnstile_site_key || '');
        putVal('sms_106_endpoint', eff.sms_106_endpoint || '');
        putVal('sms_106_account', eff.sms_106_account || '');
        putVal('sms_106_sign_name', eff.sms_106_sign_name || '');
        putVal('sms_106_template', eff.sms_106_template || '');
        putVal('sms_tencent_secret_id', eff.sms_tencent_secret_id || '');
        putVal('sms_tencent_sdk_app_id', eff.sms_tencent_sdk_app_id || '');
        putVal('sms_tencent_sign', eff.sms_tencent_sign || '');
        putVal('sms_tencent_template_id', eff.sms_tencent_template_id || '');
        putVal('sms_tencent_region', eff.sms_tencent_region || 'ap-guangzhou');

        // Secrets never echoed back; show hint via placeholder.
        var ik = $('sms_internal_key');
        if(ik){
          ik.value = '';
          ik.placeholder = eff.sms_internal_key_set ? '已配置（不回显；更新时再填写）' : '未配置';
        }
        if($('sms_internal_key_hint')){
          $('sms_internal_key_hint').textContent = eff.sms_internal_key_masked ? ('当前：' + String(eff.sms_internal_key_masked)) : '';
        }
        var sk = $('sms_captcha_turnstile_secret_key');
        if(sk){
          sk.value = '';
          sk.placeholder = eff.sms_captcha_turnstile_secret_key_set ? '已配置（不回显；更新时再填写）' : '未配置';
        }
        if($('sms_captcha_secret_hint')){
          $('sms_captcha_secret_hint').textContent = eff.sms_captcha_turnstile_secret_key_masked ? ('当前：' + String(eff.sms_captcha_turnstile_secret_key_masked)) : '';
        }
        var p106 = $('sms_106_password');
        if(p106){
          p106.value = '';
          p106.placeholder = eff.sms_106_password_set ? '已配置（不回显；更新时再填写）' : '未配置';
        }
        if($('sms_106_password_hint')){
          $('sms_106_password_hint').textContent = eff.sms_106_password_masked ? ('当前：' + String(eff.sms_106_password_masked)) : '';
        }
        var tsk = $('sms_tencent_secret_key');
        if(tsk){
          tsk.value = '';
          tsk.placeholder = eff.sms_tencent_secret_key_set ? '已配置（不回显；更新时再填写）' : '未配置';
        }
        if($('sms_tencent_secret_key_hint')){
          $('sms_tencent_secret_key_hint').textContent = eff.sms_tencent_secret_key_masked ? ('当前：' + String(eff.sms_tencent_secret_key_masked)) : '';
        }
      }

      async function saveSms(){
        var eff = window.__smsEff || {};
        function val(id){ var el = $(id); return el ? String(el.value||'').trim() : ''; }
        var tasks = [];
        function post(key, value){
          tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:key, value:String(value||'').trim()})}));
        }
        function postIfChanged(key, id, prev){
          var v = val(id);
          var p = (prev !== undefined && prev !== null) ? String(prev) : '';
          if(v === p) return;
          // Safety: avoid deleting existing config by accident.
          // If you really want to clear a value later, we can add explicit "清空" buttons.
          if(v === '') return;
          post(key, v);
        }
        function postSecretIfFilled(key, id){
          var v = val(id);
          if(!v) return; // do not overwrite/clear secrets when left empty
          post(key, v);
        }

        postIfChanged('identity_api_base', 'sms_identity_api_base', eff.identity_api_base);
        postIfChanged('sms_active_provider', 'sms_active_provider', eff.sms_active_provider);
        postIfChanged('sms_captcha_enabled', 'sms_captcha_enabled', eff.sms_captcha_enabled);
        postIfChanged('sms_captcha_provider', 'sms_captcha_provider', eff.sms_captcha_provider);
        postIfChanged('sms_captcha_turnstile_site_key', 'sms_captcha_turnstile_site_key', eff.sms_captcha_turnstile_site_key);

        postIfChanged('sms_106_endpoint', 'sms_106_endpoint', eff.sms_106_endpoint);
        postIfChanged('sms_106_account', 'sms_106_account', eff.sms_106_account);
        postIfChanged('sms_106_sign_name', 'sms_106_sign_name', eff.sms_106_sign_name);
        postIfChanged('sms_106_template', 'sms_106_template', eff.sms_106_template);

        postIfChanged('sms_tencent_secret_id', 'sms_tencent_secret_id', eff.sms_tencent_secret_id);
        postIfChanged('sms_tencent_sdk_app_id', 'sms_tencent_sdk_app_id', eff.sms_tencent_sdk_app_id);
        postIfChanged('sms_tencent_sign', 'sms_tencent_sign', eff.sms_tencent_sign);
        postIfChanged('sms_tencent_template_id', 'sms_tencent_template_id', eff.sms_tencent_template_id);
        postIfChanged('sms_tencent_region', 'sms_tencent_region', eff.sms_tencent_region);

        // Secrets: only update when admin typed something.
        postSecretIfFilled('sms_internal_key', 'sms_internal_key');
        postSecretIfFilled('sms_captcha_turnstile_secret_key', 'sms_captcha_turnstile_secret_key');
        postSecretIfFilled('sms_106_password', 'sms_106_password');
        postSecretIfFilled('sms_tencent_secret_key', 'sms_tencent_secret_key');

        if(tasks.length === 0){ setStatus('未检测到修改（为空的输入不会覆盖原配置）'); return; }
        setStatus('正在保存短信与身份配置…');
        await Promise.all(tasks);
        setStatus('短信与身份配置已写入数据库');
        await loadSms();
      }

      async function saveConfig(){
        var pv = $('cfgPaidProvider').value;
        var tsToken = ($('cfgTsToken').value || '').trim();
        var pr = $('cfgPriority').value.trim();
        var rk = $('cfgRtK').value;
        var vo = $('cfgVipOnly').value;
        var tasks = [];
        if(pv !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'paid_provider', value: pv})}));
        if(tsToken !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'tushare_token', value: tsToken})}));
        if(pr !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'paid_provider_priority', value: pr})}));
        if(rk !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'tushare_use_rt_k', value: rk})}));
        if(vo !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'paid_vip_only', value: vo})}));
        if(tasks.length===0){ setStatus('请至少修改一项后再保存（全部留空表示不写数据库）'); return; }
        setStatus('正在保存数据源配置…');
        await Promise.all(tasks);
        setStatus('已保存到数据库，约 5 秒内生效');
      }

      async function loadMarket(){
        var md = await api('/api/status/market-data');
        var paid = (md && md.paid) ? md.paid : {};
        var route = (md && md.route) ? md.route : {};
        var meta =
          '当前付费源 <strong>' + esc(paid.provider || '—') + '</strong> <span class="muted">(paid_provider)</span>' +
          ' · 请求顺序 <span class="mono">' + esc(paid.priority || '—') + '</span>' +
          ' · TuShare 令牌已配置 <strong>' + (paid.tushare_token_set ? '是' : '否') + '</strong>' +
          ' · 仅会员使用付费 <strong>' + (paid.vip_only ? '是' : '否') + '</strong>';
        $('marketMeta').innerHTML = meta;
        var body = $('routeBody');
        body.innerHTML = '';
        var keys = Object.keys(route || {}).sort(function(a,b){ return (route[b].hits||0)-(route[a].hits||0); });
        keys.forEach(function(k){
          var it = route[k] || {};
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(k)+'</td>'+
            '<td class="mono">'+esc(it.hits||0)+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.last_ts||0))+'</td>';
          body.appendChild(tr);
        });
        setStatus('行情路由状态已刷新');
      }

      async function boot(){
        var navBtns = qsa('.nav-item[data-panel]');
        for(var i=0;i<navBtns.length;i++){
          (function(btn){
            try{
              btn.onclick = function(){
                try{ showPanel(btn.getAttribute('data-panel')); }catch(e){ setStatus('切换失败：'+(e && e.message ? e.message : String(e))); }
              };
            }catch(e){}
          })(navBtns[i]);
        }
        try{
          await api('/api/admin/ping');
          setStatus('已登录（浏览器会话 Cookie；若配置了 localStorage 头键也会一并发送）');
        }catch(e){
          if((e && e.message) === 'Unauthorized'){
            // After server restart, in-memory session may be lost. Redirect to login to avoid a "dead" admin UI.
            try{
              var nxt = location.pathname + location.search + location.hash;
              location.href = ADMIN_BASE + '/login?next=' + encodeURIComponent(nxt);
              return;
            }catch(e2){}
            setStatus('会话失效，请重新登录：' + ADMIN_BASE + '/login');
            return;
          }
          setStatus('会话无效或网络错误：' + ((e && e.message) ? e.message : String(e)) + ' · 请打开 ' + ADMIN_BASE + '/login');
          return;
        }
        var hash = (location.hash||'').replace(/^#/,'');
        if(hash && document.getElementById(hash)) showPanel(hash);
        else showPanel('p-users');

        $('btnLogout').addEventListener('click', async function(){
          try{
            await fetch('/api/admin/logout', { method:'POST', credentials:'include' });
          }catch(e){}
          try{
            localStorage.removeItem('ai24x_admin_key');
          }catch(e){}
          location.href = ADMIN_BASE + '/login';
        });

        $('btnLoadCfg').addEventListener('click', async function(){
          try{ await loadConfig(); setStatus('已从服务器读取数据源配置'); }catch(e){ setStatus('读取数据源配置失败：'+e.message); }
        });
        $('btnSaveCfg').addEventListener('click', async function(){
          try{ await saveConfig(); }catch(e){ setStatus('保存数据源配置失败：'+e.message); }
        });
        if($('btnLoadSystem')) $('btnLoadSystem').addEventListener('click', async function(){
          try{ await loadSystem(); setStatus('已读取系统配置'); }catch(e){ setStatus('读取系统配置失败：'+e.message); }
        });
        if($('btnSaveSystem')) $('btnSaveSystem').addEventListener('click', async function(){
          try{ await saveSystem(); }catch(e){ setStatus('保存系统配置失败：'+e.message); }
        });
        if($('btnLoadInviteCfg')) $('btnLoadInviteCfg').addEventListener('click', async function(){
          try{ await loadInviteCfg(); setStatus('已读取邀请奖励配置'); }catch(e){ setStatus('读取邀请奖励配置失败：'+e.message); }
        });
        if($('btnSaveInviteCfg')) $('btnSaveInviteCfg').addEventListener('click', async function(){
          try{ await saveInviteCfg(); }catch(e){ setStatus('保存邀请奖励配置失败：'+e.message); }
        });
        $('btnLoadWechat').addEventListener('click', async function(){
          try{ await loadWechat(); setStatus('已读取微信支付配置'); }catch(e){ setStatus('读取失败：'+e.message); }
        });
        $('btnSaveWechat').addEventListener('click', async function(){
          try{ await saveWechat(); }catch(e){ setStatus('保存微信支付失败：'+e.message); }
        });
        $('btnLoadOrders').addEventListener('click', async function(){
          try{ ordOffset = 0; await loadPayOrders(); }catch(e){ setStatus('加载订单失败：'+e.message); }
        });
        $('btnExportOrdersCsv').addEventListener('click', async function(){
          try{ await exportPayOrdersCsv(); }catch(e){ setStatus('导出失败：'+e.message); }
        });
        $('btnOrdPrev').addEventListener('click', async function(){
          try{
            var lim = ordPageLimit();
            ordOffset = Math.max(0, ordOffset - lim);
            await loadPayOrders();
          }catch(e){ setStatus('加载订单失败：'+e.message); }
        });
        $('btnOrdNext').addEventListener('click', async function(){
          try{
            var lim = ordPageLimit();
            if(ordOffset + lim < ordLastTotal) ordOffset += lim;
            await loadPayOrders();
          }catch(e){ setStatus('加载订单失败：'+e.message); }
        });
        if($('btnLoadCommissionCfg')) $('btnLoadCommissionCfg').addEventListener('click', async function(){
          try{ await loadCommissionCfg(); setStatus('已读取返佣配置'); }catch(e){ setStatus('读取返佣配置失败：'+e.message); }
        });
        if($('btnSaveCommissionCfg')) $('btnSaveCommissionCfg').addEventListener('click', async function(){
          try{ await saveCommissionCfg(); }catch(e){ setStatus('保存返佣配置失败：'+e.message); }
        });
        if($('btnLoadEligible')) $('btnLoadEligible').addEventListener('click', async function(){
          try{ await loadEligibleCommissions(); }catch(e){ setStatus('刷新待结算失败：'+e.message); }
        });
        if($('btnMarkPaid')) $('btnMarkPaid').addEventListener('click', async function(){
          try{ await markAgentPaid(); }catch(e){ setStatus('标记已打款失败：'+e.message); }
        });
        if($('btnRegenCommission')) $('btnRegenCommission').addEventListener('click', async function(){
          try{ await regenCommissionForOrder(); }catch(e){ setStatus('补单失败：'+e.message); }
        });
        if($('btnRunHotspotsTest')) $('btnRunHotspotsTest').addEventListener('click', async function(){
          try{ await runHotspotsTest(); }catch(e){ setStatus('热点测试失败：'+e.message); }
        });
        if($('btnLosersPctDebug')) $('btnLosersPctDebug').addEventListener('click', async function(){
          try{ await runLosersPctDebug(); }catch(e){ setStatus('生成失败：'+e.message); }
        });
        $('btnLoadSms').addEventListener('click', async function(){
          try{ await loadSms(); setStatus('已读取短信与身份配置'); }catch(e){ setStatus('读取失败：'+e.message); }
        });
        $('btnSaveSms').addEventListener('click', async function(){
          try{ await saveSms(); }catch(e){ setStatus('保存短信配置失败：'+e.message); }
        });
        // 诊断工具已移除（避免界面出现接口/代码字段名）
        $('btnLoadMarket').addEventListener('click', async function(){
          try{ await loadMarket(); }catch(e){ setStatus('刷新行情路由失败：'+e.message); }
        });
        $('btnSearch').addEventListener('click', loadUsers);
        $('btnReloadLedger').addEventListener('click', loadLedger);
        $('btnReloadOps').addEventListener('click', loadOps);
        $('btnApplyQuota').addEventListener('click', applyQuota);
        if($('btnSaveUserBasic')) $('btnSaveUserBasic').addEventListener('click', function(){
          saveUserBasic().catch(function(e){ setStatus('保存基础信息失败：'+e.message); });
        });
        if($('btnAdminSetPw')) $('btnAdminSetPw').addEventListener('click', function(){
          adminSetPassword().catch(function(e){ setStatus('保存新密码失败：'+e.message); });
        });
      }

      boot();
    </script>
  </body>
</html>"""
    )
    return s.replace("__ADMIN_BASE_JS__", json.dumps(admin_base, ensure_ascii=False))
