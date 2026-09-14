# -*- coding: utf-8 -*-
"""Open BYOK panel i18n + api-base lock + console.js EN strings."""
from pathlib import Path

ROOT = Path(r"E:/AI24X/ai24x-website/ai24x01")

# --- console.html BYOK chrome ---
html = ROOT / "p/open/web/console.html"
t = html.read_text(encoding="utf-8")
old = """          <!-- BYOK keys（用户自带 key） -->
          <div class="console-panel" id="panel-byok" data-console-panel="byok" role="tabpanel" hidden>
            <div class="console-panel-head">
              <h2 class="mt-0">BYOK keys · 自带 Key，即开即用</h2>
              <p class="sub" id="byok-fee-note">平台只收取网关服务费，不赚差价；你的 key 按你的原厂价消耗。相同请求命中缓存时不消耗额度。</p>
            </div>

            <div class="card" id="byok-status-card" style="display:none">
              <div class="stats-grid byok-stats-grid">
                <div class="stat-card">
                  <div class="stat-label">网关状态</div>
                  <div class="stat-value" id="byok-status-enabled">--</div>
                  <div class="stat-sub">BYOK_ENABLED</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label">免费档本月</div>
                  <div class="stat-value" id="byok-status-free">--</div>
                  <div class="stat-sub">BYOK 请求 / 上限</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label">请求缓存</div>
                  <div class="stat-value" id="byok-status-cache">--</div>
                  <div class="stat-sub">TTL / 进程内条目</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label">平台回退</div>
                  <div class="stat-value" id="byok-status-fallback">--</div>
                  <div class="stat-sub">自有 key 全失败时</div>
                </div>
              </div>
            </div>

            <div class="card">
              <div class="keys-toolbar">
                <h3 class="mt-0 mb-0">添加自有 Key</h3>
              </div>
              <div class="byok-form-grid mt-2">
                <label>
                  <span class="stat-label">Provider</span>
                  <select class="input" id="byok-provider">
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic (Messages API)</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="siliconflow">硅基流动 SiliconFlow</option>
                    <option value="together">Together AI</option>
                    <option value="moonshot">Moonshot Kimi</option>
                    <option value="zhipu">智谱 GLM</option>
                    <option value="qwen">阿里云百炼 DashScope</option>
                    <option value="xai">xAI Grok</option>
                    <option value="groq">Groq</option>
                    <option value="mistral">Mistral</option>
                    <option value="custom">自定义 OpenAI 兼容</option>
                  </select>
                </label>
                <label>
                  <span class="stat-label">名称（可选）</span>
                  <input class="input" id="byok-name" type="text" maxlength="64" placeholder="如：主力 DeepSeek / 备用 OpenAI" autocomplete="off" />
                </label>
                <label class="byok-form-wide">
                  <span class="stat-label">API Key（AES-256-GCM 加密存储，只显示前缀）</span>
                  <input class="input" id="byok-api-key" type="password" placeholder="sk-..." autocomplete="off" />
                </label>
                <label class="byok-form-wide">
                  <span class="stat-label">可服务模型（逗号分隔，留空=全部；如 gpt-4o, gpt-4o-mini / deepseek-chat）</span>
                  <input class="input" id="byok-models" type="text" placeholder="留空可服务该 Provider 任意模型" autocomplete="off" />
                </label>
                <label>
                  <span class="stat-label">自定义 Base URL（custom 必填）</span>
                  <input class="input" id="byok-base-url" type="text" placeholder="https://..." autocomplete="off" />
                </label>
                <label>
                  <span class="stat-label">优先级（越小越优先）</span>
                  <input class="input" id="byok-priority" type="number" min="0" max="999" value="100" />
                </label>
              </div>
              <div class="card-actions mt-2">
                <button type="button" class="btn" id="btn-byok-test">测试 Key（不发请求以外开销）</button>
                <button type="button" class="btn btn-primary" id="btn-byok-save">保存 Key</button>
                <span class="sub" id="byok-form-msg"></span>
              </div>
            </div>

            <div class="card">
              <div class="keys-toolbar">
                <h3 class="mt-0 mb-0">我的自有 Key</h3>
                <button type="button" class="btn" id="btn-byok-refresh-keys">刷新</button>
              </div>
              <div class="keys-table-wrap mt-2">
                <table class="keys-table" aria-label="BYOK keys">
                  <thead>
                    <tr>
                      <th>Provider</th>
                      <th>名称</th>
                      <th>Key（前缀）</th>
                      <th>模型</th>
                      <th>状态</th>
                      <th>延迟/成功率</th>
                      <th>最近使用</th>
                      <th class="keys-col-actions">操作</th>
                    </tr>
                  </thead>
                  <tbody id="byokKeysList"></tbody>
                </table>
              </div>
              <p class="sub mt-2">同一模型可挂多把 Key：平台按成功率 / 延迟 / 优先级自动选最优，故障自动切换，请求不中断。</p>
            </div>

            <div class="card">
              <div class="keys-toolbar">
                <h3 class="mt-0 mb-0">用量 &amp; 成本看板</h3>
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                  <select class="input" id="byok-usage-days" style="width:auto">
                    <option value="1">近 1 天</option>
                    <option value="7" selected>近 7 天</option>
                    <option value="30">近 30 天</option>
                  </select>"""

new = """          <!-- BYOK keys -->
          <div class="console-panel" id="panel-byok" data-console-panel="byok" role="tabpanel" hidden>
            <div class="console-panel-head">
              <h2 class="mt-0" data-i18n="page.console.byok.title">BYOK keys · bring your own keys</h2>
              <p class="sub" id="byok-fee-note" data-i18n="page.console.byok.feeNote">Gateway service fee only — your keys bill at provider rates. Cache hits do not spend quota.</p>
            </div>

            <div class="card" id="byok-status-card" style="display:none">
              <div class="stats-grid byok-stats-grid">
                <div class="stat-card">
                  <div class="stat-label" data-i18n="page.console.byok.statusLabel">Gateway</div>
                  <div class="stat-value" id="byok-status-enabled">--</div>
                  <div class="stat-sub" data-i18n="page.console.byok.statusSub">On / off</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label" data-i18n="page.console.byok.freeLabel">Free tier this month</div>
                  <div class="stat-value" id="byok-status-free">--</div>
                  <div class="stat-sub" data-i18n="page.console.byok.freeSub">BYOK requests / limit</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label" data-i18n="page.console.byok.cacheLabel">Request cache</div>
                  <div class="stat-value" id="byok-status-cache">--</div>
                  <div class="stat-sub" data-i18n="page.console.byok.cacheSub">TTL / in-memory entries</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label" data-i18n="page.console.byok.fallbackLabel">Platform fallback</div>
                  <div class="stat-value" id="byok-status-fallback">--</div>
                  <div class="stat-sub" data-i18n="page.console.byok.fallbackSub">When all your keys fail</div>
                </div>
              </div>
            </div>

            <div class="card">
              <div class="keys-toolbar">
                <h3 class="mt-0 mb-0" data-i18n="page.console.byok.addTitle">Add your key</h3>
              </div>
              <div class="byok-form-grid mt-2">
                <label>
                  <span class="stat-label">Provider</span>
                  <select class="input" id="byok-provider">
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic (Messages API)</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="siliconflow">SiliconFlow</option>
                    <option value="together">Together AI</option>
                    <option value="moonshot">Moonshot Kimi</option>
                    <option value="zhipu">Zhipu GLM</option>
                    <option value="qwen">DashScope (Qwen)</option>
                    <option value="xai">xAI Grok</option>
                    <option value="groq">Groq</option>
                    <option value="mistral">Mistral</option>
                    <option value="custom" data-i18n="page.console.byok.customOpt">Custom OpenAI-compatible</option>
                  </select>
                </label>
                <label>
                  <span class="stat-label" data-i18n="page.console.byok.nameLabel">Name (optional)</span>
                  <input class="input" id="byok-name" type="text" maxlength="64" placeholder="e.g. Primary DeepSeek" data-i18n-placeholder="page.console.byok.namePh" autocomplete="off" />
                </label>
                <label class="byok-form-wide">
                  <span class="stat-label" data-i18n="page.console.byok.keyLabel">API Key (encrypted at rest; prefix only shown)</span>
                  <input class="input" id="byok-api-key" type="password" placeholder="sk-..." autocomplete="off" />
                </label>
                <label class="byok-form-wide">
                  <span class="stat-label" data-i18n="page.console.byok.modelsLabel">Models (comma-separated; empty = all)</span>
                  <input class="input" id="byok-models" type="text" placeholder="Leave empty for any model" data-i18n-placeholder="page.console.byok.modelsPh" autocomplete="off" />
                </label>
                <label>
                  <span class="stat-label" data-i18n="page.console.byok.baseLabel">Custom base URL (required for custom)</span>
                  <input class="input" id="byok-base-url" type="text" placeholder="https://..." autocomplete="off" />
                </label>
                <label>
                  <span class="stat-label" data-i18n="page.console.byok.prioLabel">Priority (lower = first)</span>
                  <input class="input" id="byok-priority" type="number" min="0" max="999" value="100" />
                </label>
              </div>
              <div class="card-actions mt-2">
                <button type="button" class="btn" id="btn-byok-test" data-i18n="page.console.byok.testBtn">Test key</button>
                <button type="button" class="btn btn-primary" id="btn-byok-save" data-i18n="page.console.byok.saveBtn">Save key</button>
                <span class="sub" id="byok-form-msg"></span>
              </div>
            </div>

            <div class="card">
              <div class="keys-toolbar">
                <h3 class="mt-0 mb-0" data-i18n="page.console.byok.listTitle">My BYOK keys</h3>
                <button type="button" class="btn" id="btn-byok-refresh-keys" data-i18n="page.console.byok.refresh">Refresh</button>
              </div>
              <div class="keys-table-wrap mt-2">
                <table class="keys-table" aria-label="BYOK keys">
                  <thead>
                    <tr>
                      <th>Provider</th>
                      <th data-i18n="page.console.byok.colName">Name</th>
                      <th data-i18n="page.console.byok.colKey">Key prefix</th>
                      <th data-i18n="page.console.byok.colModels">Models</th>
                      <th data-i18n="page.console.byok.colStatus">Status</th>
                      <th data-i18n="page.console.byok.colLatency">Latency / success</th>
                      <th data-i18n="page.console.byok.colLast">Last used</th>
                      <th class="keys-col-actions" data-i18n="page.console.keys.col.actions">Actions</th>
                    </tr>
                  </thead>
                  <tbody id="byokKeysList"></tbody>
                </table>
              </div>
              <p class="sub mt-2" data-i18n="page.console.byok.listHint">Multiple keys per model: we pick by success / latency / priority and fail over automatically.</p>
            </div>

            <div class="card">
              <div class="keys-toolbar">
                <h3 class="mt-0 mb-0" data-i18n="page.console.byok.usageTitle">Usage &amp; cost</h3>
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                  <select class="input" id="byok-usage-days" style="width:auto">
                    <option value="1" data-i18n="page.console.byok.days1">Last 1 day</option>
                    <option value="7" selected data-i18n="page.console.byok.days7">Last 7 days</option>
                    <option value="30" data-i18n="page.console.byok.days30">Last 30 days</option>
                  </select>"""

if old not in t:
    raise SystemExit("BYOK block not found exactly")
t = t.replace(old, new, 1)

# api-base wrap
t = t.replace(
    """                <label data-i18n="page.console.apiurl">API Base</label>
                <input type="url" class="input" id="api-base" placeholder="https://api.ai24x.com" />""",
    """                <label data-i18n="page.console.apiurl">API Base</label>
                <input type="url" class="input" id="api-base" placeholder="https://api.ai24x.com" />
                <p class="sub" id="api-base-locked-hint" hidden data-i18n="page.console.apiurl.locked">Production uses the official API host (not editable).</p>""",
)
html.write_text(t, encoding="utf-8", newline="\n")
print("open console.html BYOK + api-base hint")

# --- console.js string fixes ---
js = ROOT / "p/open/web/js/console.js"
j = js.read_text(encoding="utf-8")
jreps = [
    ('en.textContent = r.enabled ? "已启用" : "已关闭";',
     'en.textContent = r.enabled ? tr("已启用", "On") : tr("已关闭", "Off");'),
    ('if (fb) fb.textContent = r.fallback_to_platform ? "开（兜底平台）" : "关（严格 BYOK）";',
     'if (fb) fb.textContent = r.fallback_to_platform ? tr("开（平台兜底）", "On (platform fallback)") : tr("关（严格 BYOK）", "Off (strict BYOK)");'),
    ("'<tr><td colspan=\"8\" class=\"sub\">还没有自有 Key。添加一把后，请求将优先走你的 Key（故障自动切换）。</td></tr>';",
     "'<tr><td colspan=\"8\" class=\"sub\">' + tr(\"还没有自有 Key。添加后将优先走你的 Key（故障自动切换）。\", \"No BYOK keys yet. Add one to route through your keys with auto failover.\") + '</td></tr>';"),
    (": '<span class=\"sub\">全部</span>';",
     ": '<span class=\"sub\">' + tr(\"全部\", \"All\") + '</span>';"),
    ("'<button type=\"button\" class=\"btn\" data-byok-test=\"' + k.id + '\">测试</button> ' +",
     "'<button type=\"button\" class=\"btn\" data-byok-test=\"' + k.id + '\">' + tr(\"测试\", \"Test\") + '</button> ' +"),
    ("(k.status === \"active\" ? \"停用\" : \"启用\") + \"</button> \" +",
     "(k.status === \"active\" ? tr(\"停用\", \"Disable\") : tr(\"启用\", \"Enable\")) + \"</button> \" +"),
    ("'<button type=\"button\" class=\"btn\" data-byok-del=\"' + k.id + '\">删除</button>' +",
     "'<button type=\"button\" class=\"btn\" data-byok-del=\"' + k.id + '\">' + tr(\"删除\", \"Delete\") + '</button>' +"),
    ('msgEl.textContent = e.message || "删除失败";',
     'msgEl.textContent = e.message || tr("删除失败", "Delete failed");'),
]
for a, b in jreps:
    if a not in j:
        print("JS MISS", a[:70])
    else:
        j = j.replace(a, b, 1)
        print("JS OK")

# api-base lock
needle = '$("api-base").value = AI24X_API.getBase();'
if needle in j and "api-base-locked-hint" not in j[j.index(needle):j.index(needle)+400]:
    j = j.replace(
        needle,
        """$("api-base").value = AI24X_API.getBase();
    if (AI24X_API.isPublicAi24xHost && AI24X_API.isPublicAi24xHost()) {
      var baseEl = $("api-base");
      if (baseEl) {
        baseEl.readOnly = true;
        baseEl.disabled = true;
      }
      var hint = $("api-base-locked-hint");
      if (hint) hint.hidden = false;
    }""",
        1,
    )
    print("api-base lock added")
js.write_text(j, encoding="utf-8", newline="\n")

# --- open locales keys (append near auth or console) ---
loc = ROOT / "p/open/web/config/locales.js"
lt = loc.read_text(encoding="utf-8")
block_en = """
    "page.console.byok.title": "BYOK keys · bring your own keys",
    "page.console.byok.feeNote": "Gateway service fee only — your keys bill at provider rates. Cache hits do not spend quota.",
    "page.console.byok.statusLabel": "Gateway",
    "page.console.byok.statusSub": "On / off",
    "page.console.byok.freeLabel": "Free tier this month",
    "page.console.byok.freeSub": "BYOK requests / limit",
    "page.console.byok.cacheLabel": "Request cache",
    "page.console.byok.cacheSub": "TTL / in-memory entries",
    "page.console.byok.fallbackLabel": "Platform fallback",
    "page.console.byok.fallbackSub": "When all your keys fail",
    "page.console.byok.addTitle": "Add your key",
    "page.console.byok.customOpt": "Custom OpenAI-compatible",
    "page.console.byok.nameLabel": "Name (optional)",
    "page.console.byok.namePh": "e.g. Primary DeepSeek",
    "page.console.byok.keyLabel": "API Key (encrypted at rest; prefix only shown)",
    "page.console.byok.modelsLabel": "Models (comma-separated; empty = all)",
    "page.console.byok.modelsPh": "Leave empty for any model",
    "page.console.byok.baseLabel": "Custom base URL (required for custom)",
    "page.console.byok.prioLabel": "Priority (lower = first)",
    "page.console.byok.testBtn": "Test key",
    "page.console.byok.saveBtn": "Save key",
    "page.console.byok.listTitle": "My BYOK keys",
    "page.console.byok.refresh": "Refresh",
    "page.console.byok.colName": "Name",
    "page.console.byok.colKey": "Key prefix",
    "page.console.byok.colModels": "Models",
    "page.console.byok.colStatus": "Status",
    "page.console.byok.colLatency": "Latency / success",
    "page.console.byok.colLast": "Last used",
    "page.console.byok.listHint": "Multiple keys per model: we pick by success / latency / priority and fail over automatically.",
    "page.console.byok.usageTitle": "Usage & cost",
    "page.console.byok.days1": "Last 1 day",
    "page.console.byok.days7": "Last 7 days",
    "page.console.byok.days30": "Last 30 days",
    "page.console.apiurl.locked": "Production uses the official API host (not editable).",
"""
block_zh = """
    "page.console.byok.title": "BYOK keys · 自带 Key",
    "page.console.byok.feeNote": "平台只收网关服务费；你的 key 按原厂价计费。缓存命中不耗额度。",
    "page.console.byok.statusLabel": "网关状态",
    "page.console.byok.statusSub": "开 / 关",
    "page.console.byok.freeLabel": "免费档本月",
    "page.console.byok.freeSub": "BYOK 请求 / 上限",
    "page.console.byok.cacheLabel": "请求缓存",
    "page.console.byok.cacheSub": "TTL / 进程内条目",
    "page.console.byok.fallbackLabel": "平台回退",
    "page.console.byok.fallbackSub": "自有 key 全失败时",
    "page.console.byok.addTitle": "添加自有 Key",
    "page.console.byok.customOpt": "自定义 OpenAI 兼容",
    "page.console.byok.nameLabel": "名称（可选）",
    "page.console.byok.namePh": "如：主力 DeepSeek",
    "page.console.byok.keyLabel": "API Key（加密存储，只显示前缀）",
    "page.console.byok.modelsLabel": "可服务模型（逗号分隔，留空=全部）",
    "page.console.byok.modelsPh": "留空可服务该 Provider 任意模型",
    "page.console.byok.baseLabel": "自定义 Base URL（custom 必填）",
    "page.console.byok.prioLabel": "优先级（越小越优先）",
    "page.console.byok.testBtn": "测试 Key",
    "page.console.byok.saveBtn": "保存 Key",
    "page.console.byok.listTitle": "我的自有 Key",
    "page.console.byok.refresh": "刷新",
    "page.console.byok.colName": "名称",
    "page.console.byok.colKey": "Key 前缀",
    "page.console.byok.colModels": "模型",
    "page.console.byok.colStatus": "状态",
    "page.console.byok.colLatency": "延迟/成功率",
    "page.console.byok.colLast": "最近使用",
    "page.console.byok.listHint": "同一模型可挂多把 Key：按成功率/延迟/优先级自动选，故障切换。",
    "page.console.byok.usageTitle": "用量与成本",
    "page.console.byok.days1": "近 1 天",
    "page.console.byok.days7": "近 7 天",
    "page.console.byok.days30": "近 30 天",
    "page.console.apiurl.locked": "正式环境使用官方 API 地址（不可修改）。",
"""
if "page.console.byok.title" not in lt:
    # insert into zh dict after first page.console.keys.hint or similar
    marker_zh = '"page.console.keys.hint"'
    marker_en = None
    # find en section: second occurrence of keys.hint or "page.console.keys.create": "Create
    idx_zh = lt.find('"page.console.keys.hint"')
    if idx_zh < 0:
        idx_zh = lt.find('"auth.register.fail"')
    # insert before a stable key in zh
    insert_at = lt.find("\n", idx_zh)
    # Better: after zh block's page.console.chat if exists
    zh_anchor = '"page.console.keys.hint":'
    en_anchor = None
    # Find both zh and en anchors for keys.hint
    positions = []
    start = 0
    while True:
        i = lt.find('"page.console.keys.hint"', start)
        if i < 0:
            break
        positions.append(i)
        start = i + 1
    print("keys.hint positions", positions)
    if len(positions) >= 1 and "page.console.byok.title" not in lt:
        # insert after the line containing keys.hint for zh (first) and en (second)
        def insert_after_line(text, pos, block):
            endline = text.find("\n", pos)
            return text[: endline + 1] + block + text[endline + 1 :]

        if len(positions) >= 2:
            # insert en first from the end so indices stay valid for zh
            lt = insert_after_line(lt, positions[1], block_en)
            lt = insert_after_line(lt, positions[0], block_zh)
        else:
            lt = insert_after_line(lt, positions[0], block_zh + block_en)
        ROOT.joinpath("p/open/web/config/locales.js").write_text(lt, encoding="utf-8", newline="\n")
        print("open locales byok keys added")
else:
    print("open locales already has byok")

# also open auth.closed
lt2 = ROOT.joinpath("p/open/web/config/locales.js").read_text(encoding="utf-8")
lt2 = lt2.replace(
    "Sign-up / sign-in are not open in this environment.",
    "Sign-up / sign-in are temporarily unavailable.",
)
lt2 = lt2.replace(
    "当前环境<strong>暂未开放</strong>注册与登录",
    "注册与登录<strong>暂时不可用</strong>，请稍后再试",
)
# scrub token-admin open if same key
ta = ROOT / "p/open/web/token-admin.html"
if ta.exists():
    tt = ta.read_text(encoding="utf-8")
    if "iamlei888" in tt:
        tt = tt.replace(
            "密钥不正确或已失效。本机用 api/.env 的 ADMIN_API_KEY 或短信内部密钥 iamlei888；",
            "密钥不正确或已失效。本机请用 api/.env 的 ADMIN_API_KEY（或已配置的短信内部密钥）；",
        )
        # also shorter variants
        tt = tt.replace("短信内部密钥 iamlei888", "已配置的短信内部密钥")
        ta.write_text(tt, encoding="utf-8", newline="\n")
        print("open token-admin scrubbed")

ROOT.joinpath("p/open/web/config/locales.js").write_text(lt2, encoding="utf-8", newline="\n")
print("done open byok batch")
