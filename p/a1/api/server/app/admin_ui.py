from __future__ import annotations

import json
import os

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
      button:hover { border-color: rgba(96,165,250,0.70); background: rgba(96,165,250,0.06); }
      button:active { transform: translateY(0.5px); }
      button[disabled] { opacity: 0.55; cursor: not-allowed; }
      button[disabled]:hover { border-color: var(--border); background: var(--panel2); }

      /* Admin UI: make "application buttons" brighter and more clickable */
      button[id^="btnSave"],
      button[id^="btnApply"],
      button[id^="btnRun"],
      button[id^="btnSubmit"] {
        background: rgba(52,211,153,0.14);
        border-color: rgba(52,211,153,0.48);
        color: #eafff7;
      }
      button[id^="btnSave"]:hover,
      button[id^="btnApply"]:hover,
      button[id^="btnRun"]:hover,
      button[id^="btnSubmit"]:hover {
        background: rgba(52,211,153,0.20);
        border-color: rgba(52,211,153,0.70);
      }

      button[id^="btnLoad"],
      button[id^="btnReload"],
      button[id^="btnExport"],
      button[id^="btnSearch"] {
        background: rgba(96,165,250,0.10);
        border-color: rgba(96,165,250,0.45);
        color: #eef6ff;
      }
      button[id^="btnLoad"]:hover,
      button[id^="btnReload"]:hover,
      button[id^="btnExport"]:hover,
      button[id^="btnSearch"]:hover {
        background: rgba(96,165,250,0.16);
        border-color: rgba(96,165,250,0.75);
      }

      /* danger buttons stay obvious */
      button.danger {
        background: rgba(251,113,133,0.10);
        border-color: rgba(251,113,133,0.45);
        color: #fff1f2;
      }
      button.danger:hover {
        background: rgba(251,113,133,0.16);
        border-color: rgba(251,113,133,0.75);
      }
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
    try:
        build = str(int(os.path.getmtime(__file__)))
    except Exception:
        build = "0"
    s = (
        """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI24X 管理后台</title>
    <script>
      // Admin UI cache-bust: avoid requiring hard refresh after updates.
      (function(){
        try{
          var BUILD = "__ADMIN_UI_BUILD__";
          var k = "ai24x_admin_ui_build";
          var old = String(localStorage.getItem(k) || "");
          if(old !== BUILD){
            localStorage.setItem(k, BUILD);
            var sep = (location.search && location.search.indexOf("?") === 0) ? "&" : "?";
            var q = (location.search || "");
            if(q.indexOf("ui_build=") >= 0) return;
            location.replace(location.pathname + q + sep + "ui_build=" + encodeURIComponent(BUILD) + (location.hash || ""));
          }
        }catch(e){}
      })();
    </script>
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
      .nav-group { margin-top: 10px; }
      .nav-l1 {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 10px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: rgba(96,165,250,.06);
        color: var(--text);
        cursor: pointer;
        font-size: 12px;
        font-weight: 900;
      }
      .nav-l1:hover { background: rgba(96,165,250,.10); }
      .nav-l1.active { border-color: rgba(96,165,250,.55); background: rgba(96,165,250,.12); }
      .nav-l1 .chev { opacity: .7; transition: transform .12s ease; }
      .nav-group.is-collapsed .nav-l1 .chev { transform: rotate(-90deg); }
      /* 子菜单不在左侧展开，统一渲染到右侧子导航栏 */
      .nav-l2 { display: none; }
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
      .subnav {
        margin-top: 10px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
      .subnav-item{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 7px 10px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--panel2);
        color: var(--text);
        cursor: pointer;
        font-size: 12px;
        font-weight: 800;
      }
      .subnav-item:hover{ border-color: rgba(96,165,250,.45); }
      .subnav-item.active{
        border-color: rgba(96,165,250,.55);
        background: rgba(96,165,250,.12);
        color: var(--pri);
      }
      .subnav-item .subt{ font-size: 11px; font-weight: 500; color: var(--muted); }
      .main-scroll { flex: 1; overflow: auto; padding: 16px 16px 32px; }
      .panel-page { display: none; }
      .panel-page.active { display: block; }
      .panel-page > .card:first-child { margin-top: 0; }
      .rk-up { color: #fb7185; }
      .rk-down { color: #34d399; }
      /* SMS provider tabs */
      .sms-tabs { display: flex; gap: 0; border-bottom: 2px solid var(--border); margin-bottom: 14px; }
      .sms-tab {
        padding: 8px 18px;
        border: none;
        background: transparent;
        color: var(--muted);
        font-size: 13px;
        cursor: pointer;
        border-bottom: 2px solid transparent;
        margin-bottom: -2px;
        transition: all .15s;
      }
      .sms-tab:hover { color: var(--text); }
      .sms-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
    </style>
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <div class="brand">AI24X 管理后台</div>
        <div class="side-hint">
          左侧按「使用频率 / 业务重要性 / 敏感配置」分区。请在可信网络环境下操作并妥善保管敏感信息。
        </div>

        <div class="nav-group" data-group="g-users">
          <button type="button" class="nav-l1" data-group-btn="g-users">
            <span>用户与运营</span><span class="chev">▾</span>
          </button>
          <div class="nav-l2">
            <button type="button" class="nav-item active" data-panel="p-users">
              用户与配额
              <span class="subt">查询用户、改套餐与剩余次数、看流水</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-feedback">
              用户反馈
              <span class="subt">工单列表、统一回复与关闭</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-notices">
              通告管理
              <span class="subt">公告发布、置顶与定向</span>
            </button>
          </div>
        </div>

        <div class="nav-group" data-group="g-pay">
          <button type="button" class="nav-l1" data-group-btn="g-pay">
            <span>支付与订单</span><span class="chev">▾</span>
          </button>
          <div class="nav-l2">
            <button type="button" class="nav-item" data-panel="p-orders">
              VIP 订单
              <span class="subt">pay_orders：状态、金额、微信单号</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-wechat">
              微信支付
              <span class="subt">商户号、证书与通知地址</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-alipay">
              支付宝支付
              <span class="subt">AppID、私钥、公钥与回调</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-billing">
              VIP 套餐与定价
              <span class="subt">名称、标价与联调小额实扣</span>
            </button>
          </div>
        </div>

        <div class="nav-group" data-group="g-settle">
          <button type="button" class="nav-l1" data-group-btn="g-settle">
            <span>伙伴与结算</span><span class="chev">▾</span>
          </button>
          <div class="nav-l2">
            <button type="button" class="nav-item" data-panel="p-agent">
              伙伴与邀请
              <span class="subt">排行榜 + 伙伴详情（树/订单/返佣/提现摘要）</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-commission">
              伙伴与返佣
              <span class="subt">支持多层推荐返佣；台账记录（T+N 到期后可提现，人工审核打款）</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-payout">
              提现申请
              <span class="subt">审核、打款记录、备注与流水号</span>
            </button>
          </div>
        </div>

        <div class="nav-group" data-group="g-ops">
          <button type="button" class="nav-l1" data-group-btn="g-ops">
            <span>行情与数据</span><span class="chev">▾</span>
          </button>
          <div class="nav-l2">
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
          </div>
        </div>

        <div class="nav-group" data-group="g-system">
          <button type="button" class="nav-l1" data-group-btn="g-system">
            <span>系统配置</span><span class="chev">▾</span>
          </button>
          <div class="nav-l2">
            <button type="button" class="nav-item" data-panel="p-sms">
              短信与统一身份
              <span class="subt">主站转发、腾讯短信占位</span>
            </button>
            <button type="button" class="nav-item" data-panel="p-system">
              系统与安全开关
              <span class="subt">管理登录与邀请奖励等全站规则</span>
            </button>
          </div>
        </div>

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
          <div class="subnav" id="subnav" aria-label="子菜单"></div>
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
                    <span class="pill">充值 / 重置账号（测试用）</span>
                    <span class="muted small">清理测试数据，用于重复走邀请码/激活/支付/返佣链路（保留 user_id）</span>
                    <button id="btnOpenReset" type="button">展开</button>
                    <button id="btnRunReset" type="button" class="danger" disabled>执行重置</button>
                  </div>
                  <div class="msg small muted" style="margin-top:8px; line-height:1.6;">
                    说明：执行会写入「运维操作记录」action=<code class="mono">user:reset</code>。生产环境默认禁用（需显式开关）。
                  </div>
                  <div id="resetBox" hidden style="margin-top:10px;">
                    <div class="row" style="flex-wrap:wrap; gap:10px; align-items:center;">
                      <label><input type="checkbox" id="rs_invite" checked /> 清空邀请码绑定</label>
                      <label><input type="checkbox" id="rs_quota" checked /> 重置配额到默认 free</label>
                      <label><input type="checkbox" id="rs_ledger" checked /> 清空扣次流水</label>
                      <label><input type="checkbox" id="rs_orders" checked /> 清空支付订单</label>
                      <label><input type="checkbox" id="rs_reward" checked /> 清空邀请奖励流水</label>
                      <label><input type="checkbox" id="rs_comm" checked /> 清空返佣台账</label>
                    </div>
                    <div class="row" style="margin-top:10px; flex-wrap:wrap; gap:10px; align-items:center;">
                      <label>备注</label>
                      <input id="rs_note" placeholder="选填：为何重置" style="min-width:280px;" />
                      <span class="muted small">提示：先点击“展开”，确认勾选项，再点击“执行重置”。</span>
                    </div>
                  </div>
                </div>
                <div class="card" style="margin-top:12px;">
                  <div class="row">
                    <span class="pill">伙伴与邀请（快捷入口）</span>
                    <span class="muted small">已迁移到「伙伴与结算 → 伙伴与邀请」。这里仅提供一键跳转到详情页。</span>
                  </div>
                  <div class="row" style="margin-top:10px; flex-wrap:wrap; gap:10px; align-items:center;">
                    <button id="btnOpenAgentFromCur" type="button" onclick="openAgentFromCurrentUser()">打开当前用户的伙伴详情</button>
                    <span class="muted small mono" id="treeMeta">提示：先在左侧列表选择一个用户。</span>
                  </div>
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

          <section class="panel-page" id="p-feedback">
            <div class="card" id="sec-feedback">
              <div class="row">
                <span class="pill">用户反馈</span>
                <span class="muted small">登录用户提交的工单（表 user_feedback）；与前台「反馈」页联动，回复后用户可在「我的工单」查看</span>
                <button type="button" id="btnFbLoad">刷新</button>
              </div>
              <div class="row" style="margin-top:12px; flex-wrap:wrap; gap:10px;">
                <label>关键词 <input id="fbQ" class="mono" style="width:200px;" placeholder="标题 / 正文 / 用户 ID / 手机 / 邮箱" /></label>
                <label>状态
                  <select id="fbStatus">
                    <option value="">全部</option>
                    <option value="open">待处理 open</option>
                    <option value="replied">已回复 replied</option>
                    <option value="closed">已关闭 closed</option>
                  </select>
                </label>
                <label>分类
                  <select id="fbCat">
                    <option value="">全部</option>
                    <option value="suggestion">建议</option>
                    <option value="bug">Bug / 错误</option>
                    <option value="billing">会员与支付</option>
                    <option value="account">账号与安全</option>
                    <option value="data">行情与数据</option>
                    <option value="agent">代理合作</option>
                    <option value="other">其它</option>
                    <option value="data_signal">行情与数据（旧 slug）</option>
                  </select>
                </label>
                <label>每页 <input id="fbLimit" type="number" min="10" max="200" step="10" value="50" style="width:64px;" /></label>
                <button type="button" id="btnFbPrev">上一页</button>
                <button type="button" id="btnFbNext">下一页</button>
                <span class="muted small mono" id="fbMeta">—</span>
              </div>
              <div style="margin-top:12px; overflow:auto;">
                <table>
                  <thead>
                    <tr>
                      <th style="width:72px;"><span class="th-cn">ID</span><span class="th-en">id</span></th>
                      <th style="width:88px;"><span class="th-cn">用户</span><span class="th-en">userId</span></th>
                      <th style="width:120px;"><span class="th-cn">分类</span><span class="th-en">category</span></th>
                      <th style="width:88px;"><span class="th-cn">状态</span><span class="th-en">status</span></th>
                      <th><span class="th-cn">标题 / 摘要</span><span class="th-en">title</span></th>
                      <th style="width:160px;"><span class="th-cn">创建</span><span class="th-en">created</span></th>
                    </tr>
                  </thead>
                  <tbody id="fbBody"></tbody>
                </table>
              </div>
              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">选中工单</span>
                  <span id="fbSelMeta" class="mono muted">—</span>
                </div>
                <div id="fbDetail" class="msg small" style="margin-top:10px; line-height:1.65;"></div>
                <div class="row" style="margin-top:10px;">
                  <label style="flex:1; min-width:240px;">管理员回复（用户可见）
                    <textarea id="fbReply" rows="5" style="width:100%; font-size:13px; margin-top:4px;" placeholder="填写对用户展示的回复；选择「关闭」时可留空以保留原回复"></textarea>
                  </label>
                </div>
                <div class="row" style="margin-top:10px; flex-wrap:wrap; gap:10px; align-items:center;">
                  <label>标记
                    <select id="fbReplyStatus">
                      <option value="replied">已回复（replied）</option>
                      <option value="closed">关闭（closed）</option>
                    </select>
                  </label>
                  <label>署名
                    <input id="fbReplyBy" placeholder="选填，默认「管理员」" style="width:160px;" />
                  </label>
                  <button type="button" id="btnFbSubmitReply">保存</button>
                </div>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-notices">
            <div class="card" id="sec-notices">
              <div class="row">
                <span class="pill">通告管理</span>
                <span class="muted small">发布系统公告/活动说明/结算规则；支持置顶与定向（指定用户/按伙伴等级）</span>
                <button type="button" id="btnLoadNotices">刷新</button>
                <button type="button" id="btnCreateNotice">发布</button>
              </div>
              <div class="field-row" style="margin-top:12px; flex-wrap:wrap;">
                <div class="field" style="min-width:220px; flex:1;">
                  <span class="lbl">标题</span><span class="sub">title</span>
                  <input id="nt_title" placeholder="例如：结算规则调整 / 系统升级通知" style="width:100%;" />
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:240px;">
                  <span class="lbl">范围</span><span class="sub">scope</span>
                  <select id="nt_scope">
                    <option value="all">全体（all）</option>
                    <option value="agent_level">按伙伴等级（agent_level）</option>
                    <option value="user">指定用户（user）</option>
                  </select>
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">目标用户ID</span><span class="sub">target_user_id</span>
                  <input id="nt_target_user_id" type="number" min="0" step="1" placeholder="scope=user 时填" style="width:160px;" />
                </div>
                <div class="field" style="min-width:240px;">
                  <span class="lbl">目标等级</span><span class="sub">target_agent_level</span>
                  <select id="nt_target_agent_level">
                    <option value="">（空）</option>
                    <option value="starter">starter（入门）</option>
                    <option value="growth">growth（成长）</option>
                    <option value="pro">pro（专业）</option>
                  </select>
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">置顶</span><span class="sub">pinned</span>
                  <select id="nt_pinned">
                    <option value="0">否（0）</option>
                    <option value="1">是（1）</option>
                  </select>
                </div>
              </div>
              <div class="field-row" style="margin-top:10px;">
                <div class="field" style="min-width:100%;">
                  <span class="lbl">正文</span><span class="sub">body</span>
                  <textarea id="nt_body" rows="5" style="width:100%; font-family: ui-sans-serif, system-ui; font-size: 13px;" placeholder="建议包含：时间范围/规则/客服入口"></textarea>
                </div>
              </div>
              <div class="msg small muted" style="margin-top:8px;">
                提示：scope=agent_level 会匹配用户当前有效伙伴等级；scope=user 仅对该 user_id 可见。下线请把 status 设为 archived。
              </div>
              <div style="margin-top:12px; overflow:auto;">
                <table>
                  <thead>
                    <tr>
                      <th style="width:72px;"><span class="th-cn">ID</span><span class="th-en">id</span></th>
                      <th style="width:80px;"><span class="th-cn">状态</span><span class="th-en">status</span></th>
                      <th style="width:60px;"><span class="th-cn">置顶</span><span class="th-en">pin</span></th>
                      <th style="width:120px;"><span class="th-cn">范围</span><span class="th-en">scope</span></th>
                      <th><span class="th-cn">标题</span><span class="th-en">title</span></th>
                      <th style="width:170px;"><span class="th-cn">时间</span><span class="th-en">created</span></th>
                      <th style="width:220px;"><span class="th-cn">操作</span><span class="th-en">ops</span></th>
                    </tr>
                  </thead>
                  <tbody id="nt_tbody"></tbody>
                </table>
              </div>
              <div class="msg small muted" style="margin-top:8px;">
                说明：MVP 支持发布/置顶/下线与定向；已读状态在用户端自动记录。
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

          <section class="panel-page" id="p-alipay">
            <div class="card" id="sec-alipay">
              <div id="aliCurrentSummary" class="msg small" style="margin:0 0 12px; line-height:1.65; padding:10px 12px; border-radius:10px; border:1px solid var(--border); background:var(--panel2);"></div>
              <div class="row">
                <span class="pill">支付宝 H5（WAP）</span>
                <span class="muted small">保存后立即生效；私钥不回显明文，需更新时重新填写</span>
                <button type="button" id="btnLoadAlipay">读取</button>
                <button type="button" id="btnSaveAlipay">保存</button>
              </div>
              <div class="field-row" style="margin-top:10px;">
                <div class="field"><span class="lbl">AppID</span><input id="ali_alipay_app_id" class="mono" style="min-width:240px;" placeholder="2088..." /></div>
                <div class="field" style="flex:1; min-width:280px;"><span class="lbl">网关</span><input id="ali_alipay_gateway" class="mono" style="width:100%;" placeholder="https://openapi.alipay.com/gateway.do" /></div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:320px;"><span class="lbl">异步回调 notify_url</span><input id="ali_alipay_notify_url" style="width:100%;" placeholder="https://域名/api/billing/alipay/notify" /></div>
                <div class="field" style="flex:1; min-width:320px;"><span class="lbl">同步跳转 return_url</span><input id="ali_alipay_return_url" style="width:100%;" placeholder="https://域名/account.html" /></div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:320px;"><span class="lbl">商户私钥文件路径</span><input id="ali_alipay_merchant_private_key_path" class="mono" style="width:100%;" placeholder="绝对路径（推荐生产）" /></div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:100%;">
                  <span class="lbl">支付宝公钥（验签用）</span>
                  <textarea id="ali_alipay_public_key" rows="5" style="width:100%; font-family:ui-monospace,monospace; font-size:11px;" placeholder="-----BEGIN PUBLIC KEY----- ..."></textarea>
                </div>
              </div>
              <div class="field-row">
                <div class="field" style="flex:1; min-width:100%;">
                  <span class="lbl">商户私钥 PEM（可选，与路径二选一）</span>
                  <textarea id="ali_alipay_merchant_private_key_pem" rows="4" style="width:100%; font-family:ui-monospace,monospace; font-size:11px;" placeholder="可选：整段粘贴商户私钥 PEM；留空不修改已存私钥"></textarea>
                </div>
              </div>
              <div class="msg small muted" style="margin-top:8px;">留空表示不修改现有配置；敏感项填了才会更新。正式环境网关通常为 https://openapi.alipay.com/gateway.do。</div>
            </div>
          </section>

          <section class="panel-page" id="p-billing">
            <div class="card" id="sec-billing">
              <div class="row">
                <span class="pill">VIP 套餐与定价</span>
                <span class="muted small">写入 admin_config；用于测试/促销临时调整；保存后立即影响下单金额与订单标题</span>
                <button type="button" id="btnLoadBilling">读取</button>
                <button type="button" id="btnSaveBilling">保存</button>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:220px;">
                  <span class="lbl">体验卡名称</span><span class="sub">vip_title_trial</span>
                  <input id="bill_vip_title_trial" placeholder="AI24X VIP体验卡" style="min-width:220px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">月卡名称</span><span class="sub">vip_title_month</span>
                  <input id="bill_vip_title_month" placeholder="AI24X VIP月会员" style="min-width:220px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">年卡名称</span><span class="sub">vip_title_year</span>
                  <input id="bill_vip_title_year" placeholder="AI24X VIP年会员" style="min-width:220px;" />
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:220px;">
                  <span class="lbl">体验卡标价(分)</span><span class="sub">price_vip_trial_fen</span>
                  <input id="bill_price_vip_trial_fen" class="mono" type="number" min="1" step="1" placeholder="990" style="width:160px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">月卡标价(分)</span><span class="sub">price_vip_month_fen</span>
                  <input id="bill_price_vip_month_fen" class="mono" type="number" min="1" step="1" placeholder="9900" style="width:160px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">年卡标价(分)</span><span class="sub">price_vip_year_fen</span>
                  <input id="bill_price_vip_year_fen" class="mono" type="number" min="1" step="1" placeholder="99900" style="width:160px;" />
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:240px;">
                  <span class="lbl">体验卡日上限</span><span class="sub">vip_trial_daily_cap</span>
                  <input id="bill_vip_trial_daily_cap" class="mono" type="number" min="0" step="1" placeholder="20" style="width:160px;" />
                </div>
                <div class="field" style="min-width:240px;">
                  <span class="lbl">体验卡周上限</span><span class="sub">vip_trial_weekly</span>
                  <input id="bill_vip_trial_weekly" class="mono" type="number" min="0" step="1" placeholder="100" style="width:160px;" />
                </div>
                <div class="field" style="min-width:240px;">
                  <span class="lbl">VIP日上限（月/年共用）</span><span class="sub">vip_daily_cap</span>
                  <input id="bill_vip_daily_cap" class="mono" type="number" min="0" step="1" placeholder="150" style="width:160px;" />
                </div>
                <div class="field" style="min-width:240px;">
                  <span class="lbl">VIP周上限（月/年共用）</span><span class="sub">vip_weekly</span>
                  <input id="bill_vip_weekly" class="mono" type="number" min="0" step="1" placeholder="500" style="width:160px;" />
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:240px;">
                  <span class="lbl">非 prod 小额实扣开关</span><span class="sub">billing_dev_real_pay</span>
                  <select id="bill_billing_dev_real_pay">
                    <option value="">默认（跟随 .env）</option>
                    <option value="0">关闭（0）</option>
                    <option value="1">开启（1，仅非 prod 生效）</option>
                  </select>
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">非 prod 实扣金额(分)</span><span class="sub">billing_dev_amount_fen</span>
                  <input id="bill_billing_dev_amount_fen" class="mono" type="number" min="1" step="1" placeholder="10" style="width:160px;" />
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:240px;">
                  <span class="lbl">用户端开启微信支付</span><span class="sub">billing_pay_wechat_enabled</span>
                  <select id="bill_billing_pay_wechat_enabled">
                    <option value="">默认（开启）</option>
                    <option value="1">开启（1）</option>
                    <option value="0">关闭（0）</option>
                  </select>
                </div>
                <div class="field" style="min-width:240px;">
                  <span class="lbl">用户端开启支付宝</span><span class="sub">billing_pay_alipay_enabled</span>
                  <select id="bill_billing_pay_alipay_enabled">
                    <option value="">默认（开启）</option>
                    <option value="1">开启（1）</option>
                    <option value="0">关闭（0）</option>
                  </select>
                </div>
              </div>
              <div class="field-row" style="margin-top:12px; flex-wrap:wrap;">
                <div class="field" style="min-width:220px;">
                  <span class="lbl">成长档名称</span><span class="sub">agent_title_growth</span>
                  <input id="bill_agent_title_growth" placeholder="伙伴计划 · 成长档" style="min-width:220px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">成长档标价(分)</span><span class="sub">price_agent_growth_fen</span>
                  <input id="bill_price_agent_growth_fen" class="mono" type="number" min="1" step="1" placeholder="29900" style="width:160px;" />
                </div>
                <div class="field" style="min-width:240px;">
                  <span class="lbl">开放成长档升级</span><span class="sub">agent_upgrade_growth_enabled</span>
                  <select id="bill_agent_upgrade_growth_enabled">
                    <option value="">默认（开启）</option>
                    <option value="1">开启（1）</option>
                    <option value="0">关闭（0）</option>
                  </select>
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:220px;">
                  <span class="lbl">专业档名称</span><span class="sub">agent_title_pro</span>
                  <input id="bill_agent_title_pro" placeholder="伙伴计划 · 专业档" style="min-width:220px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">专业档标价(分)</span><span class="sub">price_agent_pro_fen</span>
                  <input id="bill_price_agent_pro_fen" class="mono" type="number" min="1" step="1" placeholder="99900" style="width:160px;" />
                </div>
                <div class="field" style="min-width:240px;">
                  <span class="lbl">开放专业档升级</span><span class="sub">agent_upgrade_pro_enabled</span>
                  <select id="bill_agent_upgrade_pro_enabled">
                    <option value="">默认（开启）</option>
                    <option value="1">开启（1）</option>
                    <option value="0">关闭（0）</option>
                  </select>
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:360px;">
                  <span class="lbl">升级档订单参与返佣</span><span class="sub">agent_upgrade_commission_enabled</span>
                  <select id="bill_agent_upgrade_commission_enabled">
                    <option value="">默认（关闭）</option>
                    <option value="1">开启（1）</option>
                    <option value="0">关闭（0）</option>
                  </select>
                </div>
                <div class="msg small muted" style="margin-top:6px;">
                  说明：关闭时，用户购买「成长/专业」升级档不会生成佣金流水；VIP 订单不受影响。
                </div>
              </div>
              <div class="field-row" style="margin-top:10px; flex-wrap:wrap;">
                <div class="field" style="min-width:360px;">
                  <span class="lbl">伙伴结算模式</span><span class="sub">partner_payout_mode</span>
                  <select id="bill_partner_payout_mode">
                    <option value="">默认（权益回馈·推荐）</option>
                    <option value="rewards">权益回馈（不可提现）</option>
                    <option value="cash">现金提现（私域白名单试点）</option>
                  </select>
                </div>
                <div class="msg small muted" style="margin-top:6px;">
                  合规说明：默认「权益回馈」，邀请回馈以查询额度/会员权益发放，用户端不展示提现入口；仅当私域白名单试点时可切换「现金提现」。
                </div>
              </div>
              <div class="msg small muted" style="margin-top:8px;">
                说明：这里的“标价”会进入订单（后台展示/对账）。若开启“非 prod 小额实扣”，下单时真实扣款金额会被替换为该小额（仅联调用，线上务必关闭）。
              </div>
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
                    <option value="pending">待支付（pending）</option>
                    <option value="paid">已支付（paid）</option>
                  </select>
                </label>
                <label>套餐
                  <select id="ordPlan">
                    <option value="">全部</option>
                    <option value="vip_trial_99">VIP 体验卡（vip_trial_99）</option>
                    <option value="vip_month">VIP 月卡（vip_month）</option>
                    <option value="vip_year_999">VIP 年卡（vip_year_999）</option>
                    <option value="agent_growth">伙伴升级·成长（agent_growth）</option>
                    <option value="agent_pro">伙伴升级·专业（agent_pro）</option>
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
                      <th style="width:140px;"><span class="th-cn">用户账号</span><span class="th-en">phone</span></th>
                      <th style="width:120px;"><span class="th-cn">套餐</span><span class="th-en">plan</span></th>
                      <th style="width:88px;"><span class="th-cn">实收(元)</span><span class="th-en">amount</span></th>
                      <th style="width:96px;"><span class="th-cn">实收(分)</span><span class="th-en">amount_fen</span></th>
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

          <section class="panel-page" id="p-agent">
            <div class="card">
              <div class="row">
                <span class="pill">伙伴与邀请</span>
                <span class="muted small">方案A：独立页。排行榜默认按「直推人数」排序；详情页可加载树与汇总指标。</span>
              </div>
              <div class="row" style="margin-top:12px; flex-wrap:wrap; gap:10px;">
                <label>排行榜口径
                  <select id="agentRankMetric">
                    <option value="direct_invites">直推人数</option>
                    <option value="activated_direct">直推激活</option>
                    <option value="paid_amount_direct_fen">直推订单额</option>
                    <option value="paid_orders_direct">直推付费单数</option>
                    <option value="commission_pending_fen">待结算返佣(分)</option>
                    <option value="commission_paid_fen">已结算返佣(分)</option>
                  </select>
                </label>
                <label>每页 <input id="agentRankLimit" type="number" min="10" max="200" step="10" value="50" style="width:64px;" /></label>
                <button type="button" id="btnAgentRankLoad">刷新排行榜</button>
                <button type="button" id="btnAgentRankPrev">上一页</button>
                <button type="button" id="btnAgentRankNext">下一页</button>
                <span class="muted small mono" id="agentRankMeta">—</span>
              </div>
              <div style="margin-top:12px; overflow:auto;">
                <table>
                  <thead>
                    <tr>
                      <th style="width:96px;"><span class="th-cn">用户</span><span class="th-en">userId</span></th>
                      <th style="width:140px;"><span class="th-cn">身份</span><span class="th-en">masked</span></th>
                      <th style="width:96px;"><span class="th-cn">直推</span><span class="th-en">direct</span></th>
                      <th style="width:96px;"><span class="th-cn">激活</span><span class="th-en">activated</span></th>
                      <th style="width:120px;"><span class="th-cn">直推订单额(元)</span><span class="th-en">paid_yuan</span></th>
                      <th style="width:96px;"><span class="th-cn">直推单数</span><span class="th-en">paid_orders</span></th>
                      <th style="width:120px;"><span class="th-cn">待结算(元)</span><span class="th-en">pending_yuan</span></th>
                      <th style="width:120px;"><span class="th-cn">已结算(元)</span><span class="th-en">paid_comm_yuan</span></th>
                      <th style="width:96px;"><span class="th-cn">操作</span><span class="th-en">action</span></th>
                    </tr>
                  </thead>
                  <tbody id="agentRankBody"></tbody>
                </table>
              </div>
            </div>

            <div class="card" style="margin-top:12px;">
              <div class="row">
                <span class="pill">伙伴详情</span>
                <span class="muted small">输入伙伴 user_id：展示汇总（订单/返佣/提现）+ 邀请树（BFS）。</span>
              </div>
              <div class="row" style="margin-top:12px; flex-wrap:wrap; gap:10px;">
                <label>伙伴 user_id <input id="agentDetailUserId" type="number" min="1" step="1" placeholder="例如 10001" style="width:120px;" /></label>
                <label>深度 <input id="agentDetailDepth" type="number" min="1" max="6" step="1" value="3" style="width:64px;" /></label>
                <label>limit <input id="agentDetailLimit" type="number" min="50" max="2000" step="50" value="300" style="width:80px;" /></label>
                <button type="button" id="btnAgentDetailLoad">加载详情</button>
              </div>
              <div class="msg small" id="agentDetailSummary" style="margin-top:10px;">—</div>
              <div style="margin-top:12px; overflow:auto;">
                <table>
                  <thead>
                    <tr>
                      <th style="width:96px;"><span class="th-cn">用户</span><span class="th-en">userId</span></th>
                      <th style="width:140px;"><span class="th-cn">身份</span><span class="th-en">masked</span></th>
                      <th style="width:72px;"><span class="th-cn">激活</span><span class="th-en">act</span></th>
                      <th style="width:88px;"><span class="th-cn">直推</span><span class="th-en">direct</span></th>
                      <th style="width:96px;"><span class="th-cn">付费单</span><span class="th-en">paid</span></th>
                      <th style="width:120px;"><span class="th-cn">订单额(元)</span><span class="th-en">amount</span></th>
                      <th style="width:120px;"><span class="th-cn">待结算(元)</span><span class="th-en">pending</span></th>
                      <th style="width:120px;"><span class="th-cn">已结算(元)</span><span class="th-en">paid_comm</span></th>
                    </tr>
                  </thead>
                  <tbody id="agentTreeBody"></tbody>
                </table>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-commission">
            <div class="card" id="sec-commission">
              <div class="row">
                <span class="pill">代理与返佣</span>
                <span class="muted small">支持三级推荐：同一订单可生成多条返佣台账（不同 depth）；默认不退款；先人工结算</span>
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
                    <span class="lbl">直推返佣比例</span><span class="sub">agent_commission_rate_l1</span>
                    <input id="cfgCommRateL1" class="mono" placeholder="0.20" style="min-width:160px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">间推返佣比例</span><span class="sub">agent_commission_rate_l2</span>
                    <input id="cfgCommRateL2" class="mono" placeholder="0.05" style="min-width:160px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">团队返佣比例</span><span class="sub">agent_commission_rate_l3</span>
                    <input id="cfgCommRateL3" class="mono" placeholder="0.02" style="min-width:160px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">团队返佣门槛</span><span class="sub">agent_commission_l3_min_level</span>
                    <select id="cfgCommL3MinLevel">
                      <option value="starter">入门（starter，无门槛）</option>
                      <option value="growth">成长（growth，默认）</option>
                      <option value="pro">专业（pro）</option>
                    </select>
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">总比例上限</span><span class="sub">agent_commission_rate_cap_total</span>
                    <input id="cfgCommCapTotal" class="mono" placeholder="0.30" style="min-width:160px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">结算延迟（天）</span><span class="sub">agent_settle_delay_days</span>
                    <input id="cfgCommDelayDays" class="mono" placeholder="7" style="min-width:120px;" />
                  </div>
                </div>
              </div>

              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">金银铜推广等级</span>
                  <span class="muted small">按近 N 天团队GMV + 活跃直推自动晋级；直推返点按本人等级阶梯计提（铜/银/金）</span>
                </div>
                <div class="field-row" style="margin-top:12px;">
                  <div class="field" style="min-width:200px;">
                    <span class="lbl">等级开关</span><span class="sub">promo_tier_enabled</span>
                    <select id="cfgPromoTierEnabled">
                      <option value="1">开启（按等级阶梯返点）</option>
                      <option value="0">关闭（回退统一直推比例）</option>
                    </select>
                  </div>
                  <div class="field" style="min-width:200px;">
                    <span class="lbl">铜档·团队GMV(元)</span><span class="sub">promo_tier_bronze_team_gmv_fen</span>
                    <input id="cfgPromoBronzeGmv" class="mono" placeholder="3000" style="min-width:140px;" />
                  </div>
                  <div class="field" style="min-width:150px;">
                    <span class="lbl">铜档·活跃直推</span><span class="sub">promo_tier_bronze_active_direct</span>
                    <input id="cfgPromoBronzeAd" class="mono" placeholder="3" style="min-width:90px;" />
                  </div>
                  <div class="field" style="min-width:200px;">
                    <span class="lbl">银档·团队GMV(元)</span><span class="sub">promo_tier_silver_team_gmv_fen</span>
                    <input id="cfgPromoSilverGmv" class="mono" placeholder="20000" style="min-width:140px;" />
                  </div>
                  <div class="field" style="min-width:150px;">
                    <span class="lbl">银档·活跃直推</span><span class="sub">promo_tier_silver_active_direct</span>
                    <input id="cfgPromoSilverAd" class="mono" placeholder="10" style="min-width:90px;" />
                  </div>
                  <div class="field" style="min-width:200px;">
                    <span class="lbl">金档·团队GMV(元)</span><span class="sub">promo_tier_gold_team_gmv_fen</span>
                    <input id="cfgPromoGoldGmv" class="mono" placeholder="80000" style="min-width:140px;" />
                  </div>
                  <div class="field" style="min-width:150px;">
                    <span class="lbl">金档·活跃直推</span><span class="sub">promo_tier_gold_active_direct</span>
                    <input id="cfgPromoGoldAd" class="mono" placeholder="30" style="min-width:90px;" />
                  </div>
                  <div class="field" style="min-width:150px;">
                    <span class="lbl">铜档直推返点</span><span class="sub">promo_tier_rate_bronze</span>
                    <input id="cfgPromoRateBronze" class="mono" placeholder="0.15" style="min-width:90px;" />
                  </div>
                  <div class="field" style="min-width:150px;">
                    <span class="lbl">银档直推返点</span><span class="sub">promo_tier_rate_silver</span>
                    <input id="cfgPromoRateSilver" class="mono" placeholder="0.20" style="min-width:90px;" />
                  </div>
                  <div class="field" style="min-width:150px;">
                    <span class="lbl">金档直推返点</span><span class="sub">promo_tier_rate_gold</span>
                    <input id="cfgPromoRateGold" class="mono" placeholder="0.25" style="min-width:90px;" />
                  </div>
                </div>
              </div>

              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">城市合伙人（签约代理）</span>
                  <span class="muted small">现金提现仅对签约城市合伙人开放；区域/协议编号用于对账</span>
                  <button type="button" id="btnLoadCityPartners">刷新列表</button>
                </div>
                <div class="field-row" style="margin-top:12px;">
                  <div class="field" style="min-width:110px;">
                    <span class="lbl">用户 ID</span>
                    <input id="cpUserId" class="mono" placeholder="user_id" style="width:100px;" />
                  </div>
                  <div class="field" style="min-width:180px;">
                    <span class="lbl">城市/区域</span>
                    <input id="cpRegion" placeholder="例如：杭州" style="min-width:130px;" />
                  </div>
                  <div class="field" style="min-width:220px;">
                    <span class="lbl">协议编号</span>
                    <input id="cpAgreementNo" placeholder="例如：CP-HZ-2026-001" style="min-width:170px;" />
                  </div>
                  <div class="field" style="min-width:180px;">
                    <span class="lbl">签约状态</span>
                    <select id="cpEnabled">
                      <option value="1">已签约（开放现金提现）</option>
                      <option value="0">未签约</option>
                    </select>
                  </div>
                  <div class="field">
                    <button type="button" id="btnSetCityPartner">保存</button>
                  </div>
                </div>
                <div class="row" style="margin-top:10px; flex-wrap:wrap; gap:10px;">
                  <input id="cpSearch" placeholder="搜索手机/邮箱/ID" style="min-width:220px;" />
                  <span id="cpMeta" class="muted small"></span>
                </div>
                <div style="margin-top:10px; overflow:auto;">
                  <table>
                    <thead>
                      <tr>
                        <th style="width:80px;">ID</th>
                        <th style="width:90px;">等级</th>
                        <th style="width:130px;">区域</th>
                        <th style="width:180px;">协议编号</th>
                        <th style="width:200px;">账号</th>
                        <th>更新时间</th>
                      </tr>
                    </thead>
                    <tbody id="cpBody"></tbody>
                  </table>
                </div>
              </div>

              <div class="card" style="margin-top:12px;">
                <div class="row">
                  <span class="pill">城市合伙人申请审核</span>
                  <span class="muted small">支付后人工审核：通过=签约+自动生成协议编号；驳回=记录原因</span>
                  <button type="button" id="btnLoadCpApps">刷新</button>
                  <select id="cpAppStatus">
                    <option value="pending" selected>待审核</option>
                    <option value="">全部</option>
                    <option value="approved">已通过</option>
                    <option value="rejected">已驳回</option>
                  </select>
                </div>
                <div class="row" style="margin-top:10px; flex-wrap:wrap; gap:10px;">
                  <input id="cpAppSearch" placeholder="搜索手机/邮箱/ID/区域/联系人" style="min-width:240px;" />
                  <span id="cpAppMeta" class="muted small"></span>
                </div>
                <div style="margin-top:10px; overflow:auto;">
                  <table>
                    <thead>
                      <tr>
                        <th style="width:60px;">ID</th>
                        <th style="width:70px;">用户ID</th>
                        <th style="width:110px;">区域</th>
                        <th style="width:130px;">联系人</th>
                        <th style="width:150px;">账号</th>
                        <th style="width:120px;">申请时间</th>
                        <th style="width:80px;">状态</th>
                        <th>操作 / 备注</th>
                      </tr>
                    </thead>
                    <tbody id="cpAppBody"></tbody>
                  </table>
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
                        <th style="width:66px;"><span class="th-cn">层级</span><span class="th-en">depth</span></th>
                        <th style="width:96px;"><span class="th-cn">买家</span><span class="th-en">buyer</span></th>
                        <th style="width:110px;"><span class="th-cn">金额(元)</span><span class="th-en">amount_yuan</span></th>
                        <th style="width:110px;"><span class="th-cn">金额(分)</span><span class="th-en">amount_fen</span></th>
                        <th style="width:88px;"><span class="th-cn">比例</span><span class="th-en">rate</span></th>
                        <th style="width:110px;"><span class="th-cn">返佣(元)</span><span class="th-en">commission_yuan</span></th>
                        <th style="width:110px;"><span class="th-cn">返佣(分)</span><span class="th-en">commission_fen</span></th>
                        <th style="width:170px;"><span class="th-cn">可结算</span><span class="th-en">eligible_at</span></th>
                      </tr>
                    </thead>
                    <tbody id="eligibleBody"></tbody>
                  </table>
                </div>
                <details style="margin-top:12px;">
                  <summary class="muted small" style="cursor:pointer; user-select:none;">
                    旧流程（不推荐）：直接把「待结算返佣」标记为已打款
                  </summary>
                  <div class="msg small" style="margin-top:10px;">
                    建议优先使用左侧「提现申请」面板：有申请ID、可导出批量表、可追踪流水，避免重复打款。
                  </div>
                  <div class="row" style="margin-top:10px; flex-wrap:wrap; gap:10px;">
                    <label>代理ID <input id="paidAgentId" class="mono" placeholder="agent_user_id" style="width:160px;" /></label>
                    <label>备注 <input id="paidNote" placeholder="转账流水/备注（可选）" style="min-width:260px;" /></label>
                    <button type="button" id="btnMarkPaid">旧流程：标记已打款</button>
                  </div>
                </details>
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

          <section class="panel-page" id="p-payout">
            <div class="card" id="sec-payout">
              <div class="row">
                <span class="pill">提现申请（MVP）</span>
                <span class="muted small">流程建议：先「通过」→ 实际打款后点「打款完成」；如不通过则「驳回」</span>
                <button type="button" id="btnLoadPayoutReq">刷新</button>
                <button type="button" id="btnExportPayoutAlipay">导出支付宝批量表</button>
              </div>
              <div class="field-row" style="margin-top:12px;">
                <div class="field" style="min-width:200px;">
                  <span class="lbl">筛选状态</span>
                  <select id="payoutStatus">
                    <option value="">全部</option>
                    <option value="pending">待处理</option>
                    <option value="approved">已通过</option>
                    <option value="paid">已打款</option>
                    <option value="rejected">已驳回</option>
                  </select>
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">用户 ID（可选）</span>
                  <input id="payoutUserId" class="mono" placeholder="user_id" style="min-width:160px;" />
                </div>
                <div class="field" style="min-width:200px;">
                  <span class="lbl">每页数量</span>
                  <input id="payoutLimit" class="mono" value="50" style="width:120px;" />
                </div>
                <div class="field" style="flex:1; min-width:260px;">
                  <span class="lbl">操作备注（可选）</span>
                  <input id="payoutNote" placeholder="例如：已核对账号；或驳回原因" style="width:100%;" />
                </div>
                <div class="field" style="flex:1; min-width:240px;">
                  <span class="lbl">打款流水号（可选）</span>
                  <input id="payoutTransferRef" class="mono" placeholder="支付宝流水号/批次号" style="width:100%;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">导出后标记</span>
                  <select id="payoutExportMark">
                    <option value="1">标记为「已导出」</option>
                    <option value="0">不标记</option>
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:10px; flex-wrap:wrap;">
                <span id="payoutMeta" class="muted small"></span>
                <div style="flex:1"></div>
                <button type="button" id="btnPayoutPrev">上一页</button>
                <button type="button" id="btnPayoutNext">下一页</button>
              </div>
              <div style="margin-top:12px; overflow:auto;">
                <table>
                  <thead>
                    <tr>
                      <th style="width:70px;"><span class="th-cn">申请ID</span><span class="th-en">id</span></th>
                      <th style="width:90px;"><span class="th-cn">用户</span><span class="th-en">user</span></th>
                      <th style="width:96px;"><span class="th-cn">金额(元)</span><span class="th-en">amount</span></th>
                      <th style="width:92px;"><span class="th-cn">状态</span><span class="th-en">status</span></th>
                      <th style="width:92px;"><span class="th-cn">已导出</span><span class="th-en">exported</span></th>
                      <th style="width:92px;"><span class="th-cn">渠道</span><span class="th-en">channel</span></th>
                      <th><span class="th-cn">收款信息</span><span class="th-en">account</span></th>
                      <th style="width:160px;"><span class="th-cn">申请时间</span><span class="th-en">created</span></th>
                      <th style="width:160px;"><span class="th-cn">更新时间</span><span class="th-en">updated</span></th>
                      <th style="width:160px;"><span class="th-cn">打款流水</span><span class="th-en">transfer</span></th>
                      <th style="width:260px;"><span class="th-cn">备注</span><span class="th-en">note</span></th>
                      <th style="width:240px;"><span class="th-cn">操作</span><span class="th-en">actions</span></th>
                    </tr>
                  </thead>
                  <tbody id="payoutBody"></tbody>
                </table>
              </div>
            </div>
          </section>

          <section class="panel-page" id="p-sms">
            <div class="card">
              <div class="row">
                <span class="pill">短信与统一身份</span>
                <button type="button" id="btnLoadSms">读取</button>
                <button type="button" id="btnSaveSms">保存</button>
              </div>
              <div class="field-row" style="margin-top:10px;">
                <div class="field" style="flex:1; min-width:280px;"><span class="lbl">主站 API 根 URL</span><input id="sms_identity_api_base" style="width:100%;" placeholder="https://api.xxx.com" /></div>
                <div class="field" style="min-width:220px;"><span class="lbl">内部密钥</span><input id="sms_internal_key" type="password" autocomplete="off" style="min-width:200px;" placeholder="已配置（不回显；更新时再填写）" /></div>
                <div class="field"><span class="lbl">当前短信通道</span>
                  <select id="sms_active_provider">
                    <option value="local">106网关（本站直发 · 正式）</option>
                    <option value="identity_proxy">106网关（经主站 API · 旧）</option>
                    <option value="tencent">腾讯云（电信可用；移动签名未过）</option>
                    <option value="juhe">爱聚合/聚合（备案中 · 勿用）</option>
                  </select>
                </div>
                <div class="field"><span class="lbl">账号模式</span>
                  <select id="auth_local_enabled">
                    <option value="0">转发主站注册登录（旧）</option>
                    <option value="1">本站独立账号（P1 · 不写主站）</option>
                  </select>
                </div>
              </div>
              <div class="msg small muted" id="sms-secret-hints" style="margin-top:6px;">
                <span id="sms_internal_key_hint"></span>
                <span style="margin-left:12px;">正式：短信「本站直发 106」+ 账号「本站独立」。开启独立账号前须先导入主站 password_hash（按 id），否则老用户无法登录。</span>
              </div>
            </div>
            <!-- Provider tabs -->
            <div class="card" style="margin-top:14px;">
              <div class="sms-tabs">
                <button class="sms-tab active" data-tab="tab-106">106网关</button>
                <button class="sms-tab" data-tab="tab-tencent">腾讯短信</button>
                <button class="sms-tab" data-tab="tab-juhe">聚合数据</button>
                <button class="sms-tab" data-tab="tab-logs">发送记录</button>
              </div>
              <div class="sms-tab-content" id="tab-106">
                <div class="msg small muted" style="margin:4px 0 8px;">⚙ 106网关 · 选「本站直发」时在此填账号；接口地址可留空用默认。模板须含 <span class="mono">{code}</span></div>
                <div class="field-row">
                  <div class="field" style="flex:1; min-width:260px;"><span class="lbl">接口地址（endpoint）</span><input id="sms_106_endpoint" class="mono" style="width:100%;" placeholder="不填使用主站默认" /></div>
                  <div class="field" style="min-width:160px;"><span class="lbl">账号（account）</span><input id="sms_106_account" class="mono" autocomplete="off" /></div>
                  <div class="field" style="min-width:180px;"><span class="lbl">密码（password）</span><input id="sms_106_password" type="password" autocomplete="off" placeholder="已配置（不回显）" /></div>
                </div>
                <div class="msg small muted" style="margin-top:6px;"><span id="sms_106_password_hint"></span></div>
                <div class="field-row">
                  <div class="field" style="min-width:200px;"><span class="lbl">签名（sign_name）</span><input id="sms_106_sign_name" style="width:100%;" placeholder="如：速度网络" /></div>
                </div>
                <div class="field-row">
                  <div class="field" style="flex:1;"><span class="lbl">内容模板（template）</span><textarea id="sms_106_template" rows="3" style="width:100%; resize:vertical;" placeholder="须含 {code}，与平台审核文案一致"></textarea></div>
                </div>
              </div>
              <div class="sms-tab-content" id="tab-tencent" style="display:none;">
                <div class="msg small muted" style="margin:4px 0 8px;">☁ 腾讯云短信 · 需在控制台报备签名和模板。API 采用 TC3-HMAC-SHA256 签名</div>
                <div class="field-row">
                  <div class="field" style="min-width:200px;"><span class="lbl">SecretId（密钥ID）</span><input id="sms_tencent_secret_id" class="mono" placeholder="腾讯云 API 密钥" /></div>
                  <div class="field" style="min-width:200px;"><span class="lbl">SecretKey（密钥Key）</span><input id="sms_tencent_secret_key" type="password" autocomplete="off" placeholder="已配置（不回显）" /></div>
                </div>
                <div class="msg small muted" style="margin-top:6px;"><span id="sms_tencent_secret_key_hint"></span></div>
                <div class="field-row">
                  <div class="field" style="min-width:180px;"><span class="lbl">SDK AppID（应用ID）</span><input id="sms_tencent_sdk_app_id" class="mono" placeholder="如：1400006666" /></div>
                  <div class="field" style="min-width:180px;"><span class="lbl">签名（SignName）</span><input id="sms_tencent_sign" placeholder="审核通过的签名" /></div>
                  <div class="field" style="min-width:180px;"><span class="lbl">模板ID（TemplateId）</span><input id="sms_tencent_template_id" class="mono" placeholder="如：1110" /></div>
                  <div class="field" style="min-width:120px;"><span class="lbl">地域（Region）</span><input id="sms_tencent_region" class="mono" placeholder="ap-guangzhou" /></div>
                </div>
              </div>
              <div class="sms-tab-content" id="tab-juhe" style="display:none;">
                <div class="msg small muted" style="margin:4px 0 8px;">📊 聚合数据 · 模板用 #code# 变量。已接入可用（POST v.juhe.cn/sms/send）</div>
                <div class="field-row">
                  <div class="field" style="flex:1; min-width:260px;"><span class="lbl">AppKey（应用密钥）</span><input id="sms_juhe_key" class="mono" style="width:100%;" placeholder="聚合数据中心获取" /></div>
                </div>
                <div class="field-row">
                  <div class="field" style="min-width:200px;"><span class="lbl">模板ID（tpl_id）</span><input id="sms_juhe_template_id" class="mono" placeholder="审核通过的模板ID" /></div>
                  <div class="field" style="flex:1;"><span class="lbl">签名（sign）</span><input id="sms_juhe_sign" placeholder="报备的短信签名" /></div>
                </div>
                <div class="field-row">
                  <div class="field" style="flex:1;"><span class="lbl">内容模板（template）</span><textarea id="sms_juhe_template" rows="3" style="width:100%; resize:vertical;" placeholder="须含 #code#，如：您的验证码是：#code#"></textarea></div>
                </div>
              </div>
              <div class="sms-tab-content" id="tab-logs" style="display:none;">
                <div class="row" style="margin-bottom:8px;"><button type="button" id="btnLoadSmsLogs">刷新</button></div>
                <div class="field-row" style="gap:8px; flex-wrap:wrap; align-items:flex-end;">
                  <div class="field" style="min-width:140px;"><span class="lbl">手机号</span><input id="sms_log_phone" placeholder="模糊搜索" style="width:100%;" /></div>
                  <div class="field" style="min-width:100px;"><span class="lbl">用途</span><select id="sms_log_purpose"><option value="">全部</option><option value="login">登录</option><option value="register">注册</option><option value="forgot">忘记密码</option><option value="admin">管理员</option></select></div>
                  <div class="field" style="min-width:80px;"><span class="lbl">状态</span><select id="sms_log_status"><option value="">全部</option><option value="ok">成功</option><option value="fail">失败</option></select></div>
                  <button type="button" id="btnSearchSmsLogs">查询</button>
                </div>
                <div class="msg small muted" id="smsLogSummary" style="margin-top:6px;">—</div>
                <div style="margin-top:8px; overflow:auto; max-height:400px;">
                  <table class="tbl" style="min-width:700px; width:100%;">
                    <thead><tr><th>时间</th><th>手机号</th><th>用途</th><th>通道</th><th>状态</th><th>错误信息</th><th>IP</th></tr></thead>
                    <tbody id="smsLogTbody"><tr><td colspan="7" class="muted" style="text-align:center;">点击刷新加载</td></tr></tbody>
                  </table>
                </div>
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
                <div class="field" style="min-width:220px;">
                  <span class="lbl">free 默认每日配额</span>
                  <span class="sub">free_daily_cap（留空=使用 .env 默认）</span>
                  <input id="sysFreeDailyCap" class="mono" placeholder="10" style="min-width:120px;" />
                </div>
                <div class="field" style="min-width:220px;">
                  <span class="lbl">free 默认每周配额</span>
                  <span class="sub">free_weekly（留空=使用 .env 默认）</span>
                  <input id="sysFreeWeekly" class="mono" placeholder="50" style="min-width:120px;" />
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
          var parts = String(el.className || '').split(/\\s+/).filter(function(x){ return x && x !== cls; });
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
      var fbOffset = 0;
      var fbLastTotal = 0;
      var fbSelected = null;

      function setStatus(s){ $('status').textContent = s; }

      function fbPageLimit(){
        var lim = parseInt($('fbLimit').value, 10);
        if(isNaN(lim) || lim < 10) lim = 50;
        if(lim > 200) lim = 200;
        return lim;
      }
      function fbFilterQuery(){
        var qs = '';
        var st = ($('fbStatus').value || '').trim();
        var cat = ($('fbCat').value || '').trim();
        var sq = ($('fbQ') && $('fbQ').value) ? String($('fbQ').value).trim() : '';
        if(st) qs += '&status='+encodeURIComponent(st);
        if(cat) qs += '&category='+encodeURIComponent(cat);
        if(sq) qs += '&q='+encodeURIComponent(sq);
        return qs;
      }
      function fbCatLabel(c){
        var m = {
          suggestion:'建议',
          bug:'Bug/错误',
          billing:'会员与支付',
          account:'账号与安全',
          data:'行情与数据',
          data_signal:'行情与数据(旧)',
          agent:'代理合作',
          other:'其它'
        };
        return m[c] || c || '—';
      }
      function renderFbDetail(it){
        if(!it){
          $('fbSelMeta').textContent = '—';
          $('fbDetail').innerHTML = '';
          if($('fbReply')) $('fbReply').value = '';
          return;
        }
        var uid = it.user_id;
        var ph = it.user_phone || '';
        var em = it.user_email || '';
        $('fbSelMeta').textContent = '#'+it.id+' · user '+uid+' · '+fbCatLabel(it.category)+' · '+String(it.status||'');
        var parts = [];
        parts.push('<div><strong>用户</strong> ID '+esc(uid)+(ph?' · 手机 '+esc(ph):'')+(em?' · 邮箱 '+esc(em):'')+'</div>');
        parts.push('<div style="margin-top:8px;"><strong>标题</strong> '+esc(it.title||'（无）')+'</div>');
        parts.push('<div style="margin-top:8px; white-space:pre-wrap;"><strong>描述</strong><br/>'+esc(it.body||'')+'</div>');
        if((it.contact||'').trim()) parts.push('<div style="margin-top:8px;"><strong>用户留联</strong> '+esc(it.contact)+'</div>');
        if((it.admin_reply||'').trim()) parts.push('<div style="margin-top:10px; padding:10px; border-radius:10px; border:1px solid var(--border); background:var(--panel2);"><strong>当前回复</strong>（'+esc(it.replied_by||'')+' · '+esc(fmtTs(it.replied_at||0))+'）<br/><span style="white-space:pre-wrap;">'+esc(it.admin_reply)+'</span></div>');
        $('fbDetail').innerHTML = parts.join('');
        if($('fbReply')) $('fbReply').value = String(it.admin_reply||'');
      }
      async function loadFeedbackAdmin(reselectId){
        var lim = fbPageLimit();
        var qs = '?limit='+encodeURIComponent(String(lim))+'&offset='+encodeURIComponent(String(fbOffset))+fbFilterQuery();
        setStatus('正在加载用户反馈…');
        var d = await api('/api/admin/feedback'+qs);
        fbLastTotal = parseInt(d.total, 10) || 0;
        $('fbMeta').textContent = '共 '+fbLastTotal+' 条 · offset '+(d.offset!=null?d.offset:fbOffset)+' · limit '+(d.limit!=null?d.limit:lim);
        var body = $('fbBody');
        body.innerHTML = '';
        var wantId = reselectId != null ? reselectId : (fbSelected && fbSelected.id);
        var hit = null;
        (d.items || []).forEach(function(it){
          var tr = document.createElement('tr');
          tr.style.cursor = 'pointer';
          var tit = String(it.title||'').trim();
          var sum = tit || (String(it.body||'').slice(0, 48) + (String(it.body||'').length > 48 ? '…' : ''));
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono">'+esc(it.user_id)+'</td>'+
            '<td class="mono">'+esc(fbCatLabel(it.category))+'</td>'+
            '<td>'+esc(it.status)+'</td>'+
            '<td style="max-width:360px;word-break:break-word;">'+esc(sum)+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.created_at))+'</td>';
          tr.addEventListener('click', function(){
            fbSelected = it;
            renderFbDetail(it);
          });
          body.appendChild(tr);
          if(wantId != null && String(it.id) === String(wantId)) hit = it;
        });
        if(hit){
          fbSelected = hit;
          renderFbDetail(hit);
        }
        setStatus('用户反馈列表已更新');
      }

      function ntScope(){
        try{ return String(($('nt_scope').value||'all')).trim(); }catch(e){ return 'all'; }
      }
      var ntEditingId = null;
      function ntResetForm(){
        ntEditingId = null;
        try{ $('nt_title').value=''; $('nt_body').value=''; }catch(e){}
        try{ $('nt_scope').value='all'; }catch(e2){}
        try{ $('nt_target_user_id').value=''; }catch(e3){}
        try{ $('nt_target_agent_level').value=''; }catch(e4){}
        try{ $('nt_pinned').value='0'; }catch(e5){}
        try{
          var btn = $('btnCreateNotice');
          if(btn) btn.textContent = '发布';
        }catch(e6){}
      }
      async function loadNoticesAdmin(){
        setStatus('正在加载通告…');
        var d = await api('/api/admin/notices?limit=80&offset=0');
        var body = $('nt_tbody');
        if(body) body.innerHTML = '';
        (d.items || []).forEach(function(it){
          var tr = document.createElement('tr');
          var pin = it.pinned ? '1' : '0';
          var ops =
            '<button type="button" data-act="pin" data-id="'+esc(it.id)+'" data-pin="'+(it.pinned?'0':'1')+'">'+(it.pinned?'取消置顶':'置顶')+'</button> '+
            '<button type="button" data-act="st" data-id="'+esc(it.id)+'" data-st="'+(it.status==='active'?'archived':'active')+'">'+(it.status==='active'?'下线':'上线')+'</button> '+
            '<button type="button" data-act="edit" data-id="'+esc(it.id)+'">编辑</button>';
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td>'+esc(it.status||'')+'</td>'+
            '<td class="mono">'+esc(pin)+'</td>'+
            '<td class="mono">'+esc(it.scope||'')+'</td>'+
            '<td style="max-width:420px; word-break:break-word;">'+esc(it.title||'')+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.created_at||0))+'</td>'+
            '<td>'+ops+'</td>';
          tr.querySelectorAll('button[data-act]').forEach(function(b){
            b.addEventListener('click', async function(){
              try{
                var id = parseInt(b.getAttribute('data-id')||'0', 10) || 0;
                if(b.getAttribute('data-act') === 'edit'){
                  ntEditingId = id;
                  try{ $('nt_title').value = String(it.title||''); }catch(e0){}
                  try{ $('nt_body').value = String(it.body||''); }catch(e1){}
                  try{ $('nt_scope').value = String(it.scope||'all'); }catch(e2){}
                  try{ $('nt_target_user_id').value = (it.target_user_id!=null?String(it.target_user_id):''); }catch(e3){}
                  try{ $('nt_target_agent_level').value = String(it.target_agent_level||''); }catch(e4){}
                  try{ $('nt_pinned').value = it.pinned ? '1' : '0'; }catch(e5){}
                  try{
                    var btn = $('btnCreateNotice');
                    if(btn) btn.textContent = '保存修改';
                  }catch(e6){}
                  setStatus('已进入编辑模式：#'+id+'（修改后点「保存修改」）');
                  return;
                }
                if(b.getAttribute('data-act') === 'pin'){
                  var p = String(b.getAttribute('data-pin')||'0');
                  await api('/api/admin/notices/pin', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({notice_id:id, pinned:p})});
                }else{
                  var st = String(b.getAttribute('data-st')||'');
                  await api('/api/admin/notices/set_status', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({notice_id:id, status:st})});
                }
                await loadNoticesAdmin();
                setStatus('已更新通告');
              }catch(e){ setStatus('操作失败：'+e.message); }
            });
          });
          body && body.appendChild(tr);
        });
        setStatus('通告列表已更新');
      }
      async function createNoticeAdmin(){
        var title = String(($('nt_title').value||'')).trim();
        var body = String(($('nt_body').value||'')).trim();
        var scope = ntScope();
        var tu = String(($('nt_target_user_id').value||'')).trim();
        var al = String(($('nt_target_agent_level').value||'')).trim();
        var pin = String(($('nt_pinned').value||'0')).trim();
        if(ntEditingId){
          setStatus('保存修改中…');
          await api('/api/admin/notices/update', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
              notice_id: ntEditingId,
              title:title,
              body:body,
              scope:scope,
              target_user_id: tu ? parseInt(tu,10) : null,
              target_agent_level: al,
              pinned: pin
            })
          });
          ntResetForm();
        }else{
          setStatus('发布中…');
          await api('/api/admin/notices/create', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
              title:title,
              body:body,
              scope:scope,
              target_user_id: tu ? parseInt(tu,10) : null,
              target_agent_level: al,
              pinned: pin
            })
          });
          try{ $('nt_title').value=''; $('nt_body').value=''; }catch(e){}
        }
        await loadNoticesAdmin();
        setStatus(ntEditingId ? '通告已更新' : '通告已发布');
      }
      async function submitFeedbackReply(){
        if(!fbSelected || !fbSelected.id){
          setStatus('请先在表格中选择一条工单');
          return;
        }
        var sid = fbSelected.id;
        var reply = ($('fbReply').value || '').trim();
        var st = ($('fbReplyStatus').value || 'replied').trim();
        var by = ($('fbReplyBy').value || '').trim();
        setStatus('正在保存回复…');
        await api('/api/admin/feedback/reply', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ id: sid, reply: reply, status: st, replied_by: by })
        });
        setStatus('已保存');
        await loadFeedbackAdmin(sid);
      }

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

      function ordStatusZh(st){
        st = String(st||'').trim().toLowerCase();
        if(st === 'pending') return '待支付';
        if(st === 'paid') return '已支付';
        if(st === 'failed') return '失败';
        if(st === 'canceled' || st === 'cancelled') return '已取消';
        return st || '—';
      }
      function ordPlanZh(p){
        p = String(p||'').trim();
        if(p === 'vip_trial_99') return 'VIP 体验卡';
        if(p === 'vip_month') return 'VIP 月卡';
        if(p === 'vip_year_999') return 'VIP 年卡';
        if(p === 'agent_growth') return '伙伴升级·成长';
        if(p === 'agent_pro') return '伙伴升级·专业';
        if(p === 'free') return '免费';
        return p || '—';
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
          function maskPhone(s){
            s = String(s||'').trim();
            if(!s) return '—';
            var digits = s.replace(/\\D/g,'');
            if(digits.length === 11){
              return digits.slice(0,3)+'****'+digits.slice(7);
            }
            if(s.indexOf('@') >= 0){
              var a = s.split('@');
              var u = a[0]||'';
              var d0 = a.slice(1).join('@')||'';
              if(u.length <= 2) return u + '***@' + d0;
              return u.slice(0,2) + '***' + u.slice(-1) + '@' + d0;
            }
            if(s.length <= 4) return s;
            return s.slice(0,2) + '***' + s.slice(-2);
          }
          var acct = it.user_phone ? String(it.user_phone) : (it.user_email ? String(it.user_email) : '');
          var tr = document.createElement('tr');
          tr.style.cursor = 'pointer';
          tr.title = '点击查看该用户的配额与运维流水';
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono">'+esc(maskPhone(acct))+'<span class="muted small">（id '+esc(it.user_id)+'）</span></td>'+
            '<td class="mono">'+esc(ordPlanZh(it.plan))+'<span class="muted small">（'+esc(it.plan||'')+'）</span></td>'+
            '<td class="mono">'+esc(fmtFenYuan(it.amount_fen))+'</td>'+
            '<td class="mono">'+esc(it.amount_fen)+'</td>'+
            '<td>'+esc(ordStatusZh(it.status))+'<span class="muted small">（'+esc(it.status||'')+'）</span></td>'+
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
        if($('cfgCommRateL1')) $('cfgCommRateL1').value = (it.agent_commission_rate_l1 != null) ? String(it.agent_commission_rate_l1) : ((it.agent_commission_rate_normal != null) ? String(it.agent_commission_rate_normal) : '');
        if($('cfgCommRateL2')) $('cfgCommRateL2').value = (it.agent_commission_rate_l2 != null) ? String(it.agent_commission_rate_l2) : '';
        if($('cfgCommRateL3')) $('cfgCommRateL3').value = (it.agent_commission_rate_l3 != null) ? String(it.agent_commission_rate_l3) : '';
        try{ if($('cfgCommL3MinLevel')) $('cfgCommL3MinLevel').value = String(it.agent_commission_l3_min_level || 'growth'); }catch(e0){}
        if($('cfgCommCapTotal')) $('cfgCommCapTotal').value = (it.agent_commission_rate_cap_total != null) ? String(it.agent_commission_rate_cap_total) : '';
        $('cfgCommDelayDays').value = (it.agent_settle_delay_days != null) ? String(it.agent_settle_delay_days) : '';
        if($('cfgPromoTierEnabled')) $('cfgPromoTierEnabled').value = (it.promo_tier_enabled != null && String(it.promo_tier_enabled).trim() !== '') ? String(it.promo_tier_enabled).trim() : '1';
        function fen2yuan(v){ if(v == null || v === '') return ''; return String(Math.round(Number(v) / 100)); }
        if($('cfgPromoBronzeGmv')) $('cfgPromoBronzeGmv').value = fen2yuan(it.promo_tier_bronze_team_gmv_fen);
        if($('cfgPromoBronzeAd')) $('cfgPromoBronzeAd').value = (it.promo_tier_bronze_active_direct != null) ? String(it.promo_tier_bronze_active_direct) : '';
        if($('cfgPromoSilverGmv')) $('cfgPromoSilverGmv').value = fen2yuan(it.promo_tier_silver_team_gmv_fen);
        if($('cfgPromoSilverAd')) $('cfgPromoSilverAd').value = (it.promo_tier_silver_active_direct != null) ? String(it.promo_tier_silver_active_direct) : '';
        if($('cfgPromoGoldGmv')) $('cfgPromoGoldGmv').value = fen2yuan(it.promo_tier_gold_team_gmv_fen);
        if($('cfgPromoGoldAd')) $('cfgPromoGoldAd').value = (it.promo_tier_gold_active_direct != null) ? String(it.promo_tier_gold_active_direct) : '';
        if($('cfgPromoRateBronze')) $('cfgPromoRateBronze').value = (it.promo_tier_rate_bronze != null) ? String(it.promo_tier_rate_bronze) : '';
        if($('cfgPromoRateSilver')) $('cfgPromoRateSilver').value = (it.promo_tier_rate_silver != null) ? String(it.promo_tier_rate_silver) : '';
        if($('cfgPromoRateGold')) $('cfgPromoRateGold').value = (it.promo_tier_rate_gold != null) ? String(it.promo_tier_rate_gold) : '';
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
        var rt1 = String(($('cfgCommRateL1') && $('cfgCommRateL1').value) || '').trim();
        var rt2 = String(($('cfgCommRateL2') && $('cfgCommRateL2').value) || '').trim();
        var rt3 = String(($('cfgCommRateL3') && $('cfgCommRateL3').value) || '').trim();
        var l3min = String(($('cfgCommL3MinLevel') && $('cfgCommL3MinLevel').value) || '').trim();
        var cap = String(($('cfgCommCapTotal') && $('cfgCommCapTotal').value) || '').trim();
        var dd = String($('cfgCommDelayDays').value || '').trim();
        var tasks = [];
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_enabled', value: en})}));
        if(rt1 !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_rate_l1', value: rt1})}));
        if(rt2 !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_rate_l2', value: rt2})}));
        if(rt3 !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_rate_l3', value: rt3})}));
        if(l3min !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_l3_min_level', value: l3min})}));
        if(cap !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_commission_rate_cap_total', value: cap})}));
        if(dd !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'agent_settle_delay_days', value: dd})}));
        var pte = String($('cfgPromoTierEnabled').value || '1').trim();
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'promo_tier_enabled', value: pte})}));
        function yuan2fen(v){ if(v === '') return ''; return String(Math.round(Number(v) * 100)); }
        var pr = {
          promo_tier_bronze_team_gmv_fen: yuan2fen(String(($('cfgPromoBronzeGmv') && $('cfgPromoBronzeGmv').value) || '').trim()),
          promo_tier_bronze_active_direct: String(($('cfgPromoBronzeAd') && $('cfgPromoBronzeAd').value) || '').trim(),
          promo_tier_silver_team_gmv_fen: yuan2fen(String(($('cfgPromoSilverGmv') && $('cfgPromoSilverGmv').value) || '').trim()),
          promo_tier_silver_active_direct: String(($('cfgPromoSilverAd') && $('cfgPromoSilverAd').value) || '').trim(),
          promo_tier_gold_team_gmv_fen: yuan2fen(String(($('cfgPromoGoldGmv') && $('cfgPromoGoldGmv').value) || '').trim()),
          promo_tier_gold_active_direct: String(($('cfgPromoGoldAd') && $('cfgPromoGoldAd').value) || '').trim(),
          promo_tier_rate_bronze: String(($('cfgPromoRateBronze') && $('cfgPromoRateBronze').value) || '').trim(),
          promo_tier_rate_silver: String(($('cfgPromoRateSilver') && $('cfgPromoRateSilver').value) || '').trim(),
          promo_tier_rate_gold: String(($('cfgPromoRateGold') && $('cfgPromoRateGold').value) || '').trim()
        };
        Object.keys(pr).forEach(function(k){ if(pr[k] !== '') tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:k, value: pr[k]})})); });
        setStatus('正在保存返佣配置…');
        await Promise.all(tasks);
        setStatus('返佣配置已写入数据库');
        await loadCommissionCfg();
      }

      async function loadCityPartners(){
        var q = String(($('cpSearch') && $('cpSearch').value) || '').trim();
        var qs = q ? ('?q=' + encodeURIComponent(q)) : '';
        var d = await api('/api/admin/agent/city_partners' + qs);
        var body = $('cpBody');
        body.innerHTML = '';
        (d.items || []).forEach(function(it){
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(it.user_id)+'</td>'+
            '<td>'+esc(it.level||'')+'</td>'+
            '<td>'+esc(it.city_region||'')+'</td>'+
            '<td class="mono">'+esc(it.city_agreement_no||'')+'</td>'+
            '<td class="mono">'+esc(it.phone||it.email||'')+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.updated_at))+'</td>';
          body.appendChild(tr);
        });
        var meta = $('cpMeta');
        if(meta) meta.textContent = '共 '+((d.total != null) ? d.total : (d.items||[]).length)+' 位城市合伙人';
      }

      async function setCityPartner(){
        var uid = String(($('cpUserId') && $('cpUserId').value) || '').trim();
        if(!uid){ setStatus('请填写用户 ID'); return; }
        var region = String(($('cpRegion') && $('cpRegion').value) || '').trim();
        var ag = String(($('cpAgreementNo') && $('cpAgreementNo').value) || '').trim();
        var en = String(($('cpEnabled') && $('cpEnabled').value) || '0').trim();
        setStatus('正在保存城市合伙人…');
        var d = await api('/api/admin/agent/city_partner', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id: uid, city_partner: en, city_region: region, city_agreement_no: ag})});
        setStatus('已保存城市合伙人：用户 '+uid+(d.city_partner ? ' 已签约' : ' 未签约')+(d.city_region ? ' · '+d.city_region : ''));
        await loadCityPartners();
      }

      async function loadCpApps(){
        var st = String(($('cpAppStatus') && $('cpAppStatus').value) || '').trim();
        var q = String(($('cpAppSearch') && $('cpAppSearch').value) || '').trim();
        var qs = [];
        if(st) qs.push('status=' + encodeURIComponent(st));
        if(q) qs.push('q=' + encodeURIComponent(q));
        var d = await api('/api/admin/agent/city_partner/applications' + (qs.length ? ('?' + qs.join('&')) : ''));
        var body = $('cpAppBody');
        if(!body) return;
        body.innerHTML = '';
        (d.items || []).forEach(function(it){
          var tr = document.createElement('tr');
          tr.dataset.appId = String(it.id);
          var pending = it.status === 'pending';
          var ops;
          if(pending){
            ops = '<td>' +
              '<input class="cpAppRegion" placeholder="区域(默认'+esc(it.region||'')+')" style="width:110px;" /> ' +
              '<input class="cpAppAg" placeholder="协议编号(自动)" style="width:120px;" /> ' +
              '<input class="cpAppNote" placeholder="备注" style="width:90px;" /> ' +
              '<button type="button" data-approve="1">通过</button> ' +
              '<button type="button" data-reject="1">驳回</button></td>';
          } else {
            ops = '<td class="muted small">'+esc(it.admin_note||'')+'</td>';
          }
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>' +
            '<td class="mono">'+esc(it.user_id)+'</td>' +
            '<td>'+esc(it.region||'')+'</td>' +
            '<td>'+esc(it.contact_name||'')+'</td>' +
            '<td class="mono">'+esc(it.user_phone||it.user_email||'')+'</td>' +
            '<td class="mono">'+esc(fmtTs(it.created_at))+'</td>' +
            '<td>'+esc(it.status)+'</td>' +
            ops;
          body.appendChild(tr);
        });
        var meta = $('cpAppMeta');
        if(meta) meta.textContent = '共 '+((d.total != null) ? d.total : (d.items||[]).length)+' 条申请';
      }

      async function reviewCpApp(appId, approve, tr){
        if(!appId){ setStatus('无效申请 ID'); return; }
        var region = '', ag = '', note = '';
        if(tr){
          var r0 = tr.querySelector('.cpAppRegion'); if(r0) region = String(r0.value||'').trim();
          var a0 = tr.querySelector('.cpAppAg'); if(a0) ag = String(a0.value||'').trim();
          var n0 = tr.querySelector('.cpAppNote'); if(n0) note = String(n0.value||'').trim();
        }
        if(approve){
          var msg = '确认通过该城市合伙人申请并签约？';
          if(region) msg += '（区域：' + region + '）';
          if(ag) msg += '（协议：' + ag + '）';
          if(!window.confirm(msg)) return;
        } else {
          if(!window.confirm('确认驳回该申请？')) return;
        }
        setStatus(approve ? '正在通过并签约…' : '正在驳回…');
        var d = await api('/api/admin/agent/city_partner/review', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({application_id: appId, approve: approve, admin_note: note, region: region, agreement_no: ag})});
        setStatus((approve ? '已通过并签约：' : '已驳回：') + (d.agreement_no ? '协议 '+d.agreement_no : ''));
        await loadCpApps();
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
            '<td class="mono">'+esc(it.level_depth||1)+'</td>'+
            '<td class="mono">'+esc(it.buyer_user_id)+'</td>'+
            '<td class="mono">'+esc(fmtFenYuan(it.amount_fen))+'</td>'+
            '<td class="mono">'+esc(it.amount_fen)+'</td>'+
            '<td class="mono">'+esc(it.rate)+'</td>'+
            '<td class="mono">'+esc(fmtFenYuan(it.commission_fen))+'</td>'+
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
        setStatus('正在执行旧流程：标记已打款…');
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

      var payoutOffset = 0;
      var payoutLastTotal = 0;

      function payoutPageLimit(){
        var lim = parseInt($('payoutLimit').value, 10);
        if(isNaN(lim) || lim < 10) lim = 50;
        if(lim > 200) lim = 200;
        return lim;
      }

      function payoutFilterQuery(){
        var st = String(($('payoutStatus') && $('payoutStatus').value) || '').trim().toLowerCase();
        var uid = parseInt(($('payoutUserId') && $('payoutUserId').value) || '0', 10);
        if(isNaN(uid) || uid < 0) uid = 0;
        var qs = '';
        if(st) qs += '&status='+encodeURIComponent(st);
        if(uid) qs += '&user_id='+encodeURIComponent(String(uid));
        return qs;
      }

      function parseAccountSnapshot(s){
        try{
          if(!s) return null;
          if(typeof s === 'object') return s;
          var t = String(s);
          if(!t) return null;
          return JSON.parse(t);
        }catch(e){
          return null;
        }
      }

      function renderAccountSnap(snap){
        if(!snap) return '—';
        var ch = String(snap.channel||'');
        var name = String(snap.account_name||'');
        var no = String(snap.account_no_masked||'');
        var ph = String(snap.phone||'');
        var parts = [];
        if(ch) parts.push('渠道：'+ch);
        if(name) parts.push('姓名：'+name);
        if(no) parts.push('账号：'+no);
        if(ph) parts.push('手机：'+ph);
        return parts.length ? parts.join(' · ') : '—';
      }

      async function loadPayoutRequests(){
        var lim = payoutPageLimit();
        var qs = '?limit='+encodeURIComponent(String(lim))+'&offset='+encodeURIComponent(String(payoutOffset))+payoutFilterQuery();
        setStatus('正在加载提现申请…');
        var d = await api('/api/admin/payout_requests'+qs);
        payoutLastTotal = (d && d.total != null) ? (parseInt(d.total, 10) || 0) : payoutLastTotal;
        if($('payoutMeta')) $('payoutMeta').textContent = 'offset '+(d.offset||0)+' · limit '+(d.limit||lim);
        var body = $('payoutBody');
        body.innerHTML = '';
        (d.items || []).forEach(function(it){
          var tr = document.createElement('tr');
          var snap = parseAccountSnapshot(it.account_snapshot);
          var expTxt = (it.exported_at != null && String(it.exported_at)) ? ('是' + (it.exported_note ? ('（'+esc(it.exported_note)+'）') : '')) : '—';
          var actHtml =
            '<button type="button" data-act="approve" data-id="'+esc(it.id)+'">通过</button> ' +
            '<button type="button" data-act="paid" data-id="'+esc(it.id)+'">打款完成</button> ' +
            '<button type="button" data-act="reject" data-id="'+esc(it.id)+'">驳回</button>';
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono">'+esc(it.user_id)+'</td>'+
            '<td class="mono">'+esc(fmtFenYuan(it.amount_fen))+'</td>'+
            '<td>'+esc(it.status)+'</td>'+
            '<td>'+expTxt+'</td>'+
            '<td class="mono">'+esc(it.channel||'')+'</td>'+
            '<td style="max-width:420px;word-break:break-all;">'+esc(renderAccountSnap(snap))+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.created_at))+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.updated_at))+'</td>'+
            '<td class="mono" style="max-width:220px;word-break:break-all;">'+esc(it.transfer_ref||'')+'</td>'+
            '<td style="max-width:320px;word-break:break-all;">'+esc(it.note||'')+'</td>'+
            '<td>'+actHtml+'</td>';
          tr.querySelectorAll('button[data-act]').forEach(function(btn){
            btn.addEventListener('click', async function(){
              var rid = parseInt(btn.getAttribute('data-id')||'0', 10) || 0;
              var act = String(btn.getAttribute('data-act')||'').trim();
              if(!rid){ setStatus('请求 ID 无效'); return; }
              var st = (act === 'approve') ? 'approved' : (act === 'paid') ? 'paid' : (act === 'reject') ? 'rejected' : '';
              if(!st){ setStatus('未知操作'); return; }
              var note = String(($('payoutNote') && $('payoutNote').value) || '').trim();
              var tref = String(($('payoutTransferRef') && $('payoutTransferRef').value) || '').trim();
              setStatus('正在更新申请 '+rid+'…');
              await api('/api/admin/payout_requests/set_status', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id: rid, status: st, note: note, transfer_ref: tref})});
              setStatus('已更新：'+rid+' → '+st);
              await loadPayoutRequests();
            });
          });
          body.appendChild(tr);
        });
        setStatus('提现申请已加载，本页 '+((d.items||[]).length)+' 条');
      }

      async function exportPayoutAlipayCsv(){
        var st = String(($('payoutStatus') && $('payoutStatus').value) || '').trim();
        var mark = String(($('payoutExportMark') && $('payoutExportMark').value) || '1').trim();
        var qs = '?cap=5000';
        if(st) qs += '&status=' + encodeURIComponent(st);
        qs += '&mark=' + encodeURIComponent(mark);
        qs += '&mark_note=' + encodeURIComponent('alipay_batch');
        var headers = Object.assign({ 'Accept': 'text/csv' }, extraAdminHeaders());
        setStatus('正在导出支付宝批量表…');
        var r = await fetch('/api/admin/payout_requests_export_alipay'+qs, { credentials: 'include', headers: headers });
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
        a.download = 'alipay_batch.csv';
        a.click();
        URL.revokeObjectURL(a.href);
        setStatus('已下载 alipay_batch.csv（默认导出「已通过」，可在筛选里切换状态；最多 5000 条）');
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
              if(td.length===8 && /^\\d+$/.test(td)){
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
          // Update URL hash without triggering anchor scroll (prevents sidebar "drift").
          try{
            var h = String(id||'').replace(/^#/,'');
            history.replaceState(null, '', location.pathname + location.search + (h ? ('#'+h) : ''));
          }catch(e3){}
          try{
            if(window.__ai24x_admin_syncSubnavActive) window.__ai24x_admin_syncSubnavActive();
          }catch(e4){}
        }catch(e){
          try{ setStatus('切换菜单失败：'+(e && e.message ? e.message : String(e))); }catch(e2){}
        }
        if(id === 'p-users'){
          loadUsers().catch(function(e){ setStatus('用户列表：'+e.message); });
        }
        if(id === 'p-feedback'){
          fbOffset = 0;
          loadFeedbackAdmin().catch(function(e){ setStatus('用户反馈：'+e.message); });
        }
        if(id === 'p-notices'){
          loadNoticesAdmin().catch(function(e){ setStatus('通告：'+e.message); });
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
        if(id === 'p-alipay'){
          loadAlipay().catch(function(e){ setStatus('支付宝支付配置：'+e.message); });
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
        if(id === 'p-payout'){
          payoutOffset = 0;
          loadPayoutRequests().catch(function(e){ setStatus('提现申请：'+e.message); });
        }
        if(id === 'p-agent'){
          agentRankOffset = 0;
          loadAgentRank().catch(function(e){ setStatus('代理与邀请：'+e.message); });
        }
        if(id === 'p-hotspots-test'){
          // manual run only
        }
        try{ history.replaceState(null, '', '#'+id); }catch(e){}
      }

      var agentRankOffset = 0;
      var agentRankLastTotal = 0;

      function fenToYuanStr(fen){
        try{
          var f = Number(fen||0);
          return (f/100).toFixed(2);
        }catch(e){ return '0.00'; }
      }

      async function loadAgentRank(){
        var metric = $('agentRankMetric') ? String($('agentRankMetric').value||'direct_invites') : 'direct_invites';
        var lim = $('agentRankLimit') ? parseInt($('agentRankLimit').value,10) : 50;
        if(isNaN(lim) || lim < 10) lim = 50;
        if(lim > 200) lim = 200;
        setStatus('正在加载代理排行榜…');
        var d = await api('/api/admin/agent/rank?metric='+encodeURIComponent(metric)+'&limit='+encodeURIComponent(lim)+'&offset='+encodeURIComponent(agentRankOffset));
        var items = (d && d.items) ? d.items : [];
        agentRankLastTotal = items.length;
        var body = $('agentRankBody');
        if(body) body.innerHTML = '';
        items.forEach(function(it){
          var uid = it.user_id || 0;
          var who = it.phone_masked || it.email_masked || '';
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(uid)+'</td>'+
            '<td class="mono">'+esc(who)+'</td>'+
            '<td class="mono">'+esc(it.direct_invites||0)+'</td>'+
            '<td class="mono">'+esc(it.activated_direct||0)+'</td>'+
            '<td class="mono">'+esc(fenToYuanStr(it.paid_amount_direct_fen||0))+'</td>'+
            '<td class="mono">'+esc(it.paid_orders_direct||0)+'</td>'+
            '<td class="mono">'+esc(fenToYuanStr(it.commission_pending_fen||0))+'</td>'+
            '<td class="mono">'+esc(fenToYuanStr(it.commission_paid_fen||0))+'</td>'+
            '<td><button type="button" class="btn-mini" data-agent-open="'+esc(uid)+'">打开</button></td>';
          if(body) body.appendChild(tr);
        });
        if($('agentRankMeta')) $('agentRankMeta').textContent = 'offset='+agentRankOffset+' · count='+agentRankLastTotal+' · metric='+metric;
        try{
          Array.prototype.slice.call(qsa('#agentRankBody button[data-agent-open]') || []).forEach(function(b){
            b.onclick = function(){
              var uid = parseInt(b.getAttribute('data-agent-open')||'0',10);
              if($('agentDetailUserId')) $('agentDetailUserId').value = String(uid||'');
              showPanel('p-agent');
              loadAgentDetail().catch(function(e){ setStatus('代理详情：'+e.message); });
            };
          });
        }catch(e){}
        setStatus('代理排行榜已刷新');
      }

      async function loadAgentDetail(){
        var uid = $('agentDetailUserId') ? parseInt($('agentDetailUserId').value,10) : 0;
        if(isNaN(uid) || uid <= 0) throw new Error('请输入代理 user_id');
        var depth = $('agentDetailDepth') ? parseInt($('agentDetailDepth').value,10) : 3;
        if(isNaN(depth) || depth < 1) depth = 3;
        if(depth > 6) depth = 6;
        var lim = $('agentDetailLimit') ? parseInt($('agentDetailLimit').value,10) : 300;
        if(isNaN(lim) || lim < 50) lim = 300;
        if(lim > 2000) lim = 2000;
        setStatus('正在加载代理详情…');
        var d = await api('/api/admin/agent/detail?user_id='+encodeURIComponent(uid)+'&depth='+encodeURIComponent(depth)+'&limit='+encodeURIComponent(lim));
        var sum = (d && d.summary) ? d.summary : {};
        var st = (d && d.agent_status) ? d.agent_status : null;
        if($('agentDetailSummary')){
          var lvl0 = st && st.level ? String(st.level) : '';
          var locked = st && st.tier_locked ? true : false;
          var lvl = lvl0;
          if(lvl === 'normal' || lvl === 'starter' || !lvl) lvl = 'starter';
          if(lvl === 'senior') lvl = 'growth';
          if(lvl === 'gold') lvl = 'pro';
          $('agentDetailSummary').innerHTML =
            '<div><b>成长等级</b>：<span class="mono">'+esc(lvl||'starter')+'</span>'+(locked?' <span class="pill" style="margin-left:6px;">locked</span>':'')+'</div>'+
            '<div><b>直推订单额</b>：<span class="mono">'+esc(fenToYuanStr(sum.paid_amount_direct_fen||0))+'</span> 元（'+esc(sum.paid_orders_direct||0)+' 单）</div>'+
            '<div><b>返佣</b>：待结算 <span class="mono">'+esc(fenToYuanStr(sum.commission_pending_fen||0))+'</span> 元 · 已申请 <span class="mono">'+esc(fenToYuanStr(sum.commission_requested_fen||0))+'</span> 元 · 已打款 <span class="mono">'+esc(fenToYuanStr(sum.commission_paid_fen||0))+'</span> 元</div>'+
            '<div><b>提现申请</b>：pending <span class="mono">'+esc(fenToYuanStr(sum.payout_pending_fen||0))+'</span> 元 · approved <span class="mono">'+esc(fenToYuanStr(sum.payout_approved_fen||0))+'</span> 元 · paid <span class="mono">'+esc(fenToYuanStr(sum.payout_paid_fen||0))+'</span> 元</div>'+
            '<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">'+
              '<label class="muted small">设置等级 '+
                '<select id="agentTierLevel" style="margin-left:6px;">'+
                  '<option value="starter">starter</option>'+
                  '<option value="growth">growth</option>'+
                  '<option value="pro">pro</option>'+
                '</select>'+
              '</label>'+
              '<label class="muted small"><input type="checkbox" id="agentTierLocked" '+(locked?'checked':'')+' /> locked</label>'+
              '<button type="button" class="btn-mini" id="btnAgentTierSave">保存</button>'+
            '</div>';
          try{
            var sel = document.getElementById('agentTierLevel');
            if(sel) sel.value = (lvl||'starter');
            var btn = document.getElementById('btnAgentTierSave');
            if(btn){
              btn.onclick = async function(){
                try{
                  var lv = document.getElementById('agentTierLevel') ? String(document.getElementById('agentTierLevel').value||'starter') : 'starter';
                  var lk = document.getElementById('agentTierLocked') && document.getElementById('agentTierLocked').checked ? 1 : 0;
                  setStatus('正在保存等级/锁定…');
                  await api('/api/admin/agent/tier_set', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id: uid, level: lv, locked: lk, note: 'admin_ui'})});
                  await loadAgentDetail();
                  setStatus('已保存。');
                }catch(e){ setStatus('保存失败：'+(e&&e.message?e.message:String(e||''))); }
              };
            }
          }catch(e0){}
        }
        var tree = (d && d.tree) ? d.tree : {};
        var nodes = tree.nodes || [];
        var body = $('agentTreeBody');
        if(body) body.innerHTML = '';
        nodes.forEach(function(n){
          var who = n.phone_masked || n.email_masked || '';
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(n.user_id||0)+'</td>'+
            '<td class="mono">'+esc(who)+'</td>'+
            '<td class="mono">'+esc(n.activated ? 'Y':'')+'</td>'+
            '<td class="mono">'+esc(n.direct_invites||0)+'</td>'+
            '<td class="mono">'+esc(n.paid_orders||0)+'</td>'+
            '<td class="mono">'+esc(fenToYuanStr(n.paid_amount_fen||0))+'</td>'+
            '<td class="mono">'+esc(fenToYuanStr(n.commission_pending_fen||0))+'</td>'+
            '<td class="mono">'+esc(fenToYuanStr(n.commission_paid_fen||0))+'</td>';
          if(body) body.appendChild(tr);
        });
        setStatus('代理详情已刷新');
      }

      async function loadSystem(){
        var d = await api('/api/admin/config');
        var it = d.items || {};
        var v = String(it.admin_browser_otp_enabled != null ? it.admin_browser_otp_enabled : '0').trim().toLowerCase();
        var on = (v === '1' || v === 'true' || v === 'yes' || v === 'on');
        var sel = $('sysAdminOtpEnabled');
        if(sel) sel.value = on ? '1' : '0';
        if($('sysFreeDailyCap')) $('sysFreeDailyCap').value = (it.free_daily_cap != null) ? String(it.free_daily_cap) : '';
        if($('sysFreeWeekly')) $('sysFreeWeekly').value = (it.free_weekly != null) ? String(it.free_weekly) : '';
        var sum = $('sysCurrentSummary');
        if(sum){
          sum.innerHTML =
            '<div class="card-title" style="margin-bottom:6px;">当前配置</div>' +
            renderItemsSummary(it, [
              {label:'管理登录短信 OTP', key:'admin_browser_otp_enabled'},
              {label:'free 默认每日配额', key:'free_daily_cap'},
              {label:'free 默认每周配额', key:'free_weekly'},
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
        var fd = String(($('sysFreeDailyCap') && $('sysFreeDailyCap').value) || '').trim();
        var fw = String(($('sysFreeWeekly') && $('sysFreeWeekly').value) || '').trim();
        setStatus('正在保存系统配置…');
        var tasks = [];
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'admin_browser_otp_enabled', value: v})}));
        // free defaults (blank = delete override -> fallback to .env)
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'free_daily_cap', value: fd})}));
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'free_weekly', value: fw})}));
        await Promise.all(tasks);
        setStatus('已保存。free 默认配额将用于新用户初始化与“重置到默认 free”。');
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
        if($('treeRootId')) $('treeRootId').value = String(uid);
        if($('editEmail')) $('editEmail').value = '';
        if($('editPhone')) $('editPhone').value = '';
        $('setRemainingDay').value = '';
        $('setRemainingWeek').value = '';
        $('deltaDay').value = '';
        $('deltaWeek').value = '';
        $('opNote').value = '';
        $('setPlan').value = '';
        if($('btnApplyQuota')) $('btnApplyQuota').disabled = false;
        try{
          if($('resetBox')) $('resetBox').hidden = true;
          if($('btnOpenReset')) $('btnOpenReset').textContent = '展开';
          if($('btnRunReset')) $('btnRunReset').disabled = true;
        }catch(e0){}

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
        resetUiSync();
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
        function secidPretty(secid){
          var s = secid == null ? '' : String(secid).trim();
          if(!s) return '';
          // Known indices shortcuts
          if(s === '1.000001') return '上证指数（1.000001）';
          if(s === '0.399001') return '深证成指（0.399001）';
          if(s === '0.399006') return '创业板指（0.399006）';
          if(s === '0.899050') return '北证50（0.899050）';
          // Generic secid market mapping: 1.x = SH, 0.0/0.3 = SZ, 0.899 = BJ
          var m = s.match(/^(\\d+)\\.(\\d{3,})$/);
          if(!m) return s;
          var mk = m[1];
          var code = m[2];
          var tag = mk === '1' ? 'SH' : 'SZ';
          try{
            if(s.indexOf('0.899') === 0) tag = 'BJ';
          }catch(e){}
          return tag + code + '（' + s + '）';
        }
        (d.items||[]).forEach(function(it){
          var tr=document.createElement('tr');
          tr.innerHTML =
            '<td class="mono">'+esc(it.id)+'</td>'+
            '<td class="mono">'+esc(fmtTs(it.consumed_at))+'</td>'+
            '<td class="mono">'+esc(secidPretty(it.secid))+'</td>'+
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

      function fmtFenYuan(fen){
        try{
          var n = Number(fen||0);
          if(!isFinite(n)) n = 0;
          return (n/100).toFixed(2);
        }catch(e){ return '0.00'; }
      }

      function resetUiSync(){
        try{
          var rb = $('resetBox');
          var run = $('btnRunReset');
          if(run) run.disabled = !currentUserId || !(rb && !rb.hidden);
        }catch(e){}
      }

      function openResetBox(){
        if(!currentUserId){ setStatus('请先选择一个用户'); return; }
        var rb = $('resetBox');
        if(!rb) return;
        rb.hidden = !rb.hidden;
        var btn = $('btnOpenReset');
        if(btn) btn.textContent = rb.hidden ? '展开' : '收起';
        resetUiSync();
      }

      async function runReset(){
        if(!currentUserId) return;
        var rb = $('resetBox');
        if(!rb || rb.hidden){ setStatus('请先点击“展开”确认重置范围'); return; }
        var body = {
          invite_binding: !!($('rs_invite') && $('rs_invite').checked),
          quota_reset: !!($('rs_quota') && $('rs_quota').checked),
          quota_ledger: !!($('rs_ledger') && $('rs_ledger').checked),
          pay_orders: !!($('rs_orders') && $('rs_orders').checked),
          reward_ledger: !!($('rs_reward') && $('rs_reward').checked),
          commission_ledger: !!($('rs_comm') && $('rs_comm').checked),
          note: String(($('rs_note') && $('rs_note').value) ? $('rs_note').value : '').trim()
        };
        var ok = false;
        try{
          ok = window.confirm('确认重置用户 '+String(currentUserId)+'？\\n\\n将清理：'+
            (body.invite_binding?'邀请码绑定、':'')+
            (body.quota_reset?'配额、':'')+
            (body.quota_ledger?'扣次流水、':'')+
            (body.pay_orders?'支付订单、':'')+
            (body.reward_ledger?'邀请奖励、':'')+
            (body.commission_ledger?'返佣台账、':'')+
            '。');
        }catch(e){ ok = true; }
        if(!ok) return;
        setStatus('正在执行重置…');
        await api('/api/admin/user/'+encodeURIComponent(currentUserId)+'/reset', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify(body)
        });
        await selectUser(currentUserId);
        setStatus('已重置账号数据。');
      }

      async function openAgentFromCurrentUser(){
        try{ setStatus('正在打开代理详情…'); }catch(e){}
        if(!currentUserId){ setStatus('请先在左侧列表选择一个用户'); return; }
        try{
          // switch to new agent page
          showPanel('p-agent');
          if($('agentDetailUserId')) $('agentDetailUserId').value = String(currentUserId);
          await loadAgentDetail();
        }catch(e){
          setStatus('打开代理详情失败：' + (e && e.message ? e.message : String(e||'')));
        }
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
        // Keep a snapshot so "默认(空)" can delete existing DB overrides.
        try { globalThis.__AI24X_ADMIN_CFG_ITEMS = items || {}; } catch(e0) {}
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

      async function loadAlipay(){
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
        put('alipay_app_id','ali_alipay_app_id');
        put('alipay_gateway','ali_alipay_gateway');
        put('alipay_notify_url','ali_alipay_notify_url');
        put('alipay_return_url','ali_alipay_return_url');
        put('alipay_merchant_private_key_path','ali_alipay_merchant_private_key_path');
        put('alipay_public_key','ali_alipay_public_key');
        $('ali_alipay_merchant_private_key_pem').value = '';
        var s = $('aliCurrentSummary');
        if(s){
          s.innerHTML =
            '<div class="card-title" style="margin-bottom:6px;">当前配置</div>' +
            renderItemsSummary(it, [
              {label:'AppID', key:'alipay_app_id'},
              {label:'网关', key:'alipay_gateway'},
              {label:'notify_url', key:'alipay_notify_url'},
              {label:'return_url', key:'alipay_return_url'},
              {label:'私钥路径', key:'alipay_merchant_private_key_path'},
              {label:'公钥', key:'alipay_public_key'},
              {label:'私钥 PEM', key:'alipay_merchant_private_key_pem'},
            ]) +
            '<p class="muted small" style="margin:10px 0 0;">敏感项已保存时不会在页面显示；需要更新时在下方表单填写后保存。</p>';
        }
      }

      async function saveAlipay(){
        var tasks = [];
        var simple = [
          'alipay_app_id',
          'alipay_gateway',
          'alipay_notify_url',
          'alipay_return_url',
          'alipay_merchant_private_key_path',
          'alipay_public_key'
        ];
        simple.forEach(function(k){
          var el = $('ali_'+k);
          var v = el ? String(el.value||'').trim() : '';
          tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:k, value:v})}));
        });
        var pem = String($('ali_alipay_merchant_private_key_pem').value||'').trim();
        tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'alipay_merchant_private_key_pem', value:pem})}));
        setStatus('正在保存支付宝支付配置…');
        await Promise.all(tasks);
        setStatus('支付宝支付配置已写入数据库');
        await loadAlipay();
      }

      async function loadBilling(){
        var d = await api('/api/admin/config');
        var it = d.items || {};
        function put(key, elId){
          var el = $(elId);
          if(!el) return;
          var v = it[key];
          if(v === undefined || v === null) { el.value = ''; return; }
          if(String(v) === '***') { el.value = ''; return; }
          el.value = String(v);
        }
        put('vip_title_trial','bill_vip_title_trial');
        put('vip_title_month','bill_vip_title_month');
        put('vip_title_year','bill_vip_title_year');
        put('price_vip_trial_fen','bill_price_vip_trial_fen');
        put('price_vip_month_fen','bill_price_vip_month_fen');
        put('price_vip_year_fen','bill_price_vip_year_fen');
        put('vip_trial_daily_cap','bill_vip_trial_daily_cap');
        put('vip_trial_weekly','bill_vip_trial_weekly');
        put('vip_daily_cap','bill_vip_daily_cap');
        put('vip_weekly','bill_vip_weekly');
        put('billing_dev_real_pay','bill_billing_dev_real_pay');
        put('billing_dev_amount_fen','bill_billing_dev_amount_fen');
        put('billing_pay_wechat_enabled','bill_billing_pay_wechat_enabled');
        put('billing_pay_alipay_enabled','bill_billing_pay_alipay_enabled');
        put('agent_title_growth','bill_agent_title_growth');
        put('price_agent_growth_fen','bill_price_agent_growth_fen');
        put('agent_upgrade_growth_enabled','bill_agent_upgrade_growth_enabled');
        put('agent_title_pro','bill_agent_title_pro');
        put('price_agent_pro_fen','bill_price_agent_pro_fen');
        put('agent_upgrade_pro_enabled','bill_agent_upgrade_pro_enabled');
        put('agent_upgrade_commission_enabled','bill_agent_upgrade_commission_enabled');
        put('partner_payout_mode','bill_partner_payout_mode');
      }

      async function saveBilling(){
        var tasks = [];
        function post(key, elId){
          var el = $(elId);
          var v = el ? String(el.value||'').trim() : '';
          tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:key, value:v})}));
        }
        post('vip_title_trial','bill_vip_title_trial');
        post('vip_title_month','bill_vip_title_month');
        post('vip_title_year','bill_vip_title_year');
        post('price_vip_trial_fen','bill_price_vip_trial_fen');
        post('price_vip_month_fen','bill_price_vip_month_fen');
        post('price_vip_year_fen','bill_price_vip_year_fen');
        post('vip_trial_daily_cap','bill_vip_trial_daily_cap');
        post('vip_trial_weekly','bill_vip_trial_weekly');
        post('vip_daily_cap','bill_vip_daily_cap');
        post('vip_weekly','bill_vip_weekly');
        post('billing_dev_real_pay','bill_billing_dev_real_pay');
        post('billing_dev_amount_fen','bill_billing_dev_amount_fen');
        post('billing_pay_wechat_enabled','bill_billing_pay_wechat_enabled');
        post('billing_pay_alipay_enabled','bill_billing_pay_alipay_enabled');
        post('agent_title_growth','bill_agent_title_growth');
        post('price_agent_growth_fen','bill_price_agent_growth_fen');
        post('agent_upgrade_growth_enabled','bill_agent_upgrade_growth_enabled');
        post('agent_title_pro','bill_agent_title_pro');
        post('price_agent_pro_fen','bill_price_agent_pro_fen');
        post('agent_upgrade_pro_enabled','bill_agent_upgrade_pro_enabled');
        post('agent_upgrade_commission_enabled','bill_agent_upgrade_commission_enabled');
        post('partner_payout_mode','bill_partner_payout_mode');
        setStatus('正在保存套餐与定价…');
        await Promise.all(tasks);
        setStatus('套餐与定价已写入数据库（下单立即生效）');
        await loadBilling();
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
        putVal('auth_local_enabled', (eff.auth_local_enabled === '1' || eff.auth_local_enabled === 1 || eff.auth_local_enabled === true) ? '1' : '0');
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
        // Juhe
        putVal('sms_juhe_key', eff.sms_juhe_key || '');
        putVal('sms_juhe_template_id', eff.sms_juhe_template_id || '');
        putVal('sms_juhe_sign', eff.sms_juhe_sign || '');
        putVal('sms_juhe_template', eff.sms_juhe_template || '');

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
        postIfChanged('auth_local_enabled', 'auth_local_enabled', (eff.auth_local_enabled === '1' || eff.auth_local_enabled === 1 || eff.auth_local_enabled === true) ? '1' : '0');
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

        // Juhe（聚合数据）
        postIfChanged('sms_juhe_key', 'sms_juhe_key', eff.sms_juhe_key);
        postIfChanged('sms_juhe_template_id', 'sms_juhe_template_id', eff.sms_juhe_template_id);
        postIfChanged('sms_juhe_sign', 'sms_juhe_sign', eff.sms_juhe_sign);
        postIfChanged('sms_juhe_template', 'sms_juhe_template', eff.sms_juhe_template);

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
        // If admin selects "默认(空)" and there is an existing DB override, delete it (set empty).
        try{
          var cur = '';
          try{ cur = String((globalThis.__AI24X_ADMIN_CFG_ITEMS||{}).paid_vip_only||''); }catch(e0){ cur = ''; }
          if(vo !== '' || cur !== ''){
            tasks.push(api('/api/admin/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key:'paid_vip_only', value: vo})}));
          }
        }catch(eV){}
        if(tasks.length===0){ setStatus('请至少修改一项后再保存（全部留空表示不写数据库）'); return; }
        setStatus('正在保存数据源配置…');
        await Promise.all(tasks);
        try { await loadConfig(); } catch(e0) {}
        try { await loadMarket(); } catch(e1) {}
        setStatus('已保存到数据库（已刷新显示）');
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
        var NAV_ACTIVE_GROUP_KEY = 'ai24x_admin_nav_active_group';
        function qsaLocal(sel){ try{ return Array.prototype.slice.call(document.querySelectorAll(sel)); }catch(e){ return []; } }
        function getGroupForPanel(panelId){
          try{
            var btn = document.querySelector('.nav-item[data-panel="'+panelId+'"]');
            if(!btn) return '';
            var g = btn.closest && btn.closest('.nav-group');
            return g ? String(g.getAttribute('data-group') || '') : '';
          }catch(e){ return ''; }
        }
        function groupDefaultPanel(groupId){
          // Pick the most frequently used panel per group.
          groupId = String(groupId || '');
          var pref = {
            'g-users': 'p-users',
            'g-billing': 'p-orders',
            'g-agent': 'p-agent',
            'g-sms': 'p-sms',
            'g-system': 'p-system',
            'g-market': 'p-market',
          };
          var pid = pref[groupId] || '';
          if(pid && document.getElementById(pid)) return pid;
          // Fallback: first subnav item in that group.
          try{
            var g = document.querySelector('.nav-group[data-group="'+groupId+'"]');
            if(!g) return 'p-users';
            var first = g.querySelector && g.querySelector('.nav-item[data-panel]');
            var p2 = first ? String(first.getAttribute('data-panel') || '') : '';
            if(p2 && document.getElementById(p2)) return p2;
          }catch(e){}
          return 'p-users';
        }
        function setActiveGroup(groupId){
          groupId = String(groupId || '');
          qsaLocal('.nav-l1[data-group-btn]').forEach(function(h){
            h.classList.toggle('active', h.getAttribute('data-group-btn') === groupId);
          });
          try{ localStorage.setItem(NAV_ACTIVE_GROUP_KEY, groupId); }catch(e){}
          renderSubnav(groupId);
          // Auto-enter a default panel for this group to avoid "click twice".
          try{
            var act = document.querySelector('.panel-page.active');
            var cur = act ? String(act.id || '') : '';
            if(getGroupForPanel(cur) !== groupId){
              showPanel(groupDefaultPanel(groupId));
            }
          }catch(e){}
        }
        function renderSubnav(groupId){
          var box = document.getElementById('subnav');
          if(!box) return;
          box.innerHTML = '';
          var g = document.querySelector('.nav-group[data-group="'+groupId+'"]');
          if(!g) return;
          var items = (g.querySelectorAll && g.querySelectorAll('.nav-item[data-panel]')) ? Array.prototype.slice.call(g.querySelectorAll('.nav-item[data-panel]')) : [];
          items.forEach(function(src){
            var pid = String(src.getAttribute('data-panel') || '');
            var title = (src.childNodes && src.childNodes.length) ? String(src.childNodes[0].textContent || '').trim() : (src.textContent || '').trim();
            var subtEl = src.querySelector ? src.querySelector('.subt') : null;
            var subt = subtEl ? String(subtEl.textContent || '').trim() : '';
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'subnav-item';
            b.setAttribute('data-panel', pid);
            b.innerHTML = '<span>'+esc(title)+'</span>' + (subt ? '<span class="subt">'+esc(subt)+'</span>' : '');
            b.onclick = function(){
              try{ showPanel(pid); }catch(e){ setStatus('切换失败：'+(e && e.message ? e.message : String(e))); }
            };
            box.appendChild(b);
          });
          syncSubnavActive();
        }
        function syncSubnavActive(){
          var cur = '';
          try{
            var act = document.querySelector('.panel-page.active');
            cur = act ? String(act.id || '') : '';
          }catch(e){}
          qsaLocal('#subnav .subnav-item[data-panel]').forEach(function(b){
            b.classList.toggle('active', b.getAttribute('data-panel') === cur);
          });
        }
        try{
          window.__ai24x_admin_syncSubnavActive = syncSubnavActive;
          window.__ai24x_admin_getGroupForPanel = getGroupForPanel;
          window.__ai24x_admin_setActiveGroup = setActiveGroup;
        }catch(e0){}
        function initMainNav(){
          qsaLocal('.nav-l1[data-group-btn]').forEach(function(h){
            h.addEventListener('click', function(){
              var gid = h.getAttribute('data-group-btn');
              setActiveGroup(gid);
            });
          });
        }
        initMainNav();
        var navBtns = qsa('.nav-item[data-panel]');
        for(var i=0;i<navBtns.length;i++){
          (function(btn){
            try{
              btn.onclick = function(){
                try{
                  var pid = btn.getAttribute('data-panel');
                  showPanel(pid);
                }catch(e){ setStatus('切换失败：'+(e && e.message ? e.message : String(e))); }
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
        var firstPanel = (hash && document.getElementById(hash)) ? hash : 'p-users';
        showPanel(firstPanel);
        var gid0 = getGroupForPanel(firstPanel);
        if(!gid0){
          try{ gid0 = String(localStorage.getItem(NAV_ACTIVE_GROUP_KEY) || ''); }catch(e){ gid0 = ''; }
        }
        if(!gid0) gid0 = 'g-users';
        setActiveGroup(gid0);
        syncSubnavActive();

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
        if($('btnLoadAlipay')) $('btnLoadAlipay').addEventListener('click', async function(){
          try{ await loadAlipay(); setStatus('已读取支付宝支付配置'); }catch(e){ setStatus('读取失败：'+e.message); }
        });
        if($('btnSaveAlipay')) $('btnSaveAlipay').addEventListener('click', async function(){
          try{ await saveAlipay(); }catch(e){ setStatus('保存支付宝支付失败：'+e.message); }
        });
        if($('btnLoadBilling')) $('btnLoadBilling').addEventListener('click', async function(){
          try{ await loadBilling(); setStatus('已读取套餐与定价'); }catch(e){ setStatus('读取套餐与定价失败：'+e.message); }
        });
        if($('btnSaveBilling')) $('btnSaveBilling').addEventListener('click', async function(){
          try{ await saveBilling(); }catch(e){ setStatus('保存套餐与定价失败：'+e.message); }
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
        if($('btnAgentRankLoad')) $('btnAgentRankLoad').addEventListener('click', async function(){
          try{ agentRankOffset = 0; await loadAgentRank(); }catch(e){ setStatus('加载代理排行榜失败：'+e.message); }
        });
        if($('btnAgentRankPrev')) $('btnAgentRankPrev').addEventListener('click', async function(){
          try{
            var lim = parseInt($('agentRankLimit').value, 10);
            if(isNaN(lim) || lim < 10) lim = 50;
            agentRankOffset = Math.max(0, agentRankOffset - lim);
            await loadAgentRank();
          }catch(e){ setStatus('加载代理排行榜失败：'+e.message); }
        });
        if($('btnAgentRankNext')) $('btnAgentRankNext').addEventListener('click', async function(){
          try{
            var lim = parseInt($('agentRankLimit').value, 10);
            if(isNaN(lim) || lim < 10) lim = 50;
            agentRankOffset = agentRankOffset + lim;
            await loadAgentRank();
          }catch(e){ setStatus('加载代理排行榜失败：'+e.message); }
        });
        if($('btnAgentDetailLoad')) $('btnAgentDetailLoad').addEventListener('click', async function(){
          try{ await loadAgentDetail(); }catch(e){ setStatus('加载代理详情失败：'+e.message); }
        });
        if($('btnLoadCommissionCfg')) $('btnLoadCommissionCfg').addEventListener('click', async function(){
          try{ await loadCommissionCfg(); setStatus('已读取返佣配置'); }catch(e){ setStatus('读取返佣配置失败：'+e.message); }
        });
        if($('btnSaveCommissionCfg')) $('btnSaveCommissionCfg').addEventListener('click', async function(){
          try{ await saveCommissionCfg(); }catch(e){ setStatus('保存返佣配置失败：'+e.message); }
        });
        if($('btnSetCityPartner')) $('btnSetCityPartner').addEventListener('click', async function(){
          try{ await setCityPartner(); }catch(e){ setStatus('保存城市合伙人失败：'+e.message); }
        });
        if($('btnLoadCityPartners')) $('btnLoadCityPartners').addEventListener('click', async function(){
          try{ await loadCityPartners(); }catch(e){ setStatus('刷新城市合伙人失败：'+e.message); }
        });
        if($('btnLoadCpApps')) $('btnLoadCpApps').addEventListener('click', async function(){
          try{ await loadCpApps(); }catch(e){ setStatus('刷新申请失败：'+e.message); }
        });
        if($('cpAppStatus')) $('cpAppStatus').addEventListener('change', function(){
          loadCpApps().catch(function(e){ setStatus('加载申请失败：'+e.message); });
        });
        if($('cpAppSearch')) $('cpAppSearch').addEventListener('keydown', function(e){
          if(e.key === 'Enter') loadCpApps().catch(function(e){ setStatus('加载申请失败：'+e.message); });
        });
        var cpAppBody = $('cpAppBody');
        if(cpAppBody) cpAppBody.addEventListener('click', function(ev){
          var t = ev.target;
          while(t && t !== cpAppBody && !(t.dataset && (t.dataset.approve || t.dataset.reject))) t = t.parentNode;
          if(!t || t === cpAppBody) return;
          var tr = t.closest ? t.closest('tr') : null;
          var appId = Number((tr && tr.dataset && tr.dataset.appId) || 0);
          if(!appId) return;
          var approve = !!t.dataset.approve;
          reviewCpApp(appId, approve, tr).catch(function(e){ setStatus('审核失败：'+e.message); });
        });
        try{ loadCpApps(); }catch(e){}
        if($('btnLoadEligible')) $('btnLoadEligible').addEventListener('click', async function(){
          try{ await loadEligibleCommissions(); }catch(e){ setStatus('刷新待结算失败：'+e.message); }
        });
        if($('btnMarkPaid')) $('btnMarkPaid').addEventListener('click', async function(){
          try{ await markAgentPaid(); }catch(e){ setStatus('旧流程执行失败：'+e.message); }
        });
        if($('btnRegenCommission')) $('btnRegenCommission').addEventListener('click', async function(){
          try{ await regenCommissionForOrder(); }catch(e){ setStatus('补单失败：'+e.message); }
        });
        if($('btnLoadPayoutReq')) $('btnLoadPayoutReq').addEventListener('click', async function(){
          try{ payoutOffset = 0; await loadPayoutRequests(); }catch(e){ setStatus('刷新提现申请失败：'+e.message); }
        });
        if($('btnExportPayoutAlipay')) $('btnExportPayoutAlipay').addEventListener('click', async function(){
          try{ await exportPayoutAlipayCsv(); }catch(e){ setStatus('导出失败：'+e.message); }
        });
        if($('btnPayoutPrev')) $('btnPayoutPrev').addEventListener('click', async function(){
          try{
            var lim = payoutPageLimit();
            payoutOffset = Math.max(0, payoutOffset - lim);
            await loadPayoutRequests();
          }catch(e){ setStatus('加载失败：'+e.message); }
        });
        if($('btnPayoutNext')) $('btnPayoutNext').addEventListener('click', async function(){
          try{
            var lim = payoutPageLimit();
            payoutOffset = payoutOffset + lim;
            await loadPayoutRequests();
          }catch(e){ setStatus('加载失败：'+e.message); }
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
        // SMS log viewer
        async function loadSmsLogs(){
          var p = ($('sms_log_phone') ? $('sms_log_phone').value : '').trim();
          var pur = $('sms_log_purpose') ? $('sms_log_purpose').value : '';
          var st = $('sms_log_status') ? $('sms_log_status').value : '';
          var params = new URLSearchParams({ limit: '50', offset: '0' });
          if(p) params.set('phone', p);
          if(pur) params.set('purpose', pur);
          if(st) params.set('status', st);
          var d = await api('/api/admin/sms_logs?' + params.toString());
          if(!d || !d.rows){ setStatus('返回数据异常'); return; }
          $('smsLogSummary').textContent = '共 ' + (d.total || 0) + ' 条';
          var tbody = $('smsLogTbody');
          tbody.innerHTML = d.rows.map(function(row){
            var ts = row.created_at ? row.created_at.slice(0,19).replace('T',' ') : '';
            return '<tr>' +
              '<td class="mono small">' + escT(ts) + '</td>' +
              '<td>' + escT(row.phone || '') + '</td>' +
              '<td>' + escT(row.purpose || '') + '</td>' +
              '<td>' + (row.provider === 'tencent' ? '腾讯' : row.provider === 'juhe' ? '聚合' : '106') + '</td>' +
              '<td>' + (row.status === 'ok' ? '<span class="pill" style="background:#166534;color:#86efac;">成功</span>' : '<span class="pill" style="background:#7f1d1d;color:#fca5a5;">失败</span>') + '</td>' +
              '<td class="small muted">' + escT(row.error_msg || '') + '</td>' +
              '<td class="mono small muted">' + escT(row.ip_address || '') + '</td>' +
            '</tr>';
          }).join('');
        }
        function escT(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
        if($('btnLoadSmsLogs')) $('btnLoadSmsLogs').addEventListener('click', function(){ loadSmsLogs().catch(function(e){ setStatus('加载失败：'+e.message); }); });
        if($('btnSearchSmsLogs')) $('btnSearchSmsLogs').addEventListener('click', function(){ loadSmsLogs().catch(function(e){ setStatus('查询失败：'+e.message); }); });
        // SMS tab switching
        document.querySelectorAll('.sms-tab').forEach(function(t){
          t.addEventListener('click', function(){
            document.querySelectorAll('.sms-tab').forEach(function(x){ x.classList.remove('active'); });
            t.classList.add('active');
            document.querySelectorAll('.sms-tab-content').forEach(function(x){ x.style.display = 'none'; });
            var panel = document.getElementById(t.getAttribute('data-tab'));
            if(panel) panel.style.display = 'block';
          });
        });
        // 诊断工具已移除（避免界面出现接口/代码字段名）
        $('btnLoadMarket').addEventListener('click', async function(){
          try{ await loadMarket(); }catch(e){ setStatus('刷新行情路由失败：'+e.message); }
        });
        if($('btnFbLoad')) $('btnFbLoad').addEventListener('click', function(){
          fbOffset = 0;
          loadFeedbackAdmin().catch(function(e){ setStatus('用户反馈：'+e.message); });
        });
        if($('btnFbPrev')) $('btnFbPrev').addEventListener('click', function(){
          try{
            var lim = fbPageLimit();
            fbOffset = Math.max(0, fbOffset - lim);
            loadFeedbackAdmin().catch(function(e){ setStatus('用户反馈：'+e.message); });
          }catch(e){ setStatus('用户反馈翻页失败：'+e.message); }
        });
        if($('btnFbNext')) $('btnFbNext').addEventListener('click', function(){
          try{
            var lim = fbPageLimit();
            if(fbOffset + lim < fbLastTotal) fbOffset += lim;
            loadFeedbackAdmin().catch(function(e){ setStatus('用户反馈：'+e.message); });
          }catch(e){ setStatus('用户反馈翻页失败：'+e.message); }
        });
        if($('btnFbSubmitReply')) $('btnFbSubmitReply').addEventListener('click', function(){
          submitFeedbackReply().catch(function(e){ setStatus('保存回复失败：'+e.message); });
        });
        if($('btnLoadNotices')) $('btnLoadNotices').addEventListener('click', function(){
          loadNoticesAdmin().catch(function(e){ setStatus('通告：'+e.message); });
        });
        if($('btnCreateNotice')) $('btnCreateNotice').addEventListener('click', function(){
          createNoticeAdmin().catch(function(e){ setStatus('发布失败：'+e.message); });
        });
        $('btnSearch').addEventListener('click', loadUsers);
        $('btnReloadLedger').addEventListener('click', loadLedger);
        $('btnReloadOps').addEventListener('click', loadOps);
        $('btnApplyQuota').addEventListener('click', applyQuota);
        if($('btnOpenReset')) $('btnOpenReset').addEventListener('click', function(){
          try{ openResetBox(); }catch(e){ setStatus('打开重置面板失败：'+(e && e.message ? e.message : String(e))); }
        });
        if($('btnRunReset')) $('btnRunReset').addEventListener('click', function(){
          runReset().catch(function(e){ setStatus('重置失败：'+e.message); });
        });
        if($('btnOpenAgentFromCur')) $('btnOpenAgentFromCur').addEventListener('click', function(){
          openAgentFromCurrentUser();
        });
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
    return s.replace("__ADMIN_BASE_JS__", json.dumps(admin_base, ensure_ascii=False)).replace("__ADMIN_UI_BUILD__", build)
