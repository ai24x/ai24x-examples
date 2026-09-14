# BYOK 统一走 api.ai24x.com —— 交接文案（给 Cursor）

> 交接人：司令（Codex）｜日期：2026-09-04｜状态：单入口已实测打通，待收尾

## 一、一句话目标
最终用户端对外**唯一 API 入口 = api.ai24x.com**（core Hub），一个 key 即可调用全部模型；open.ai24x.com 仅保留为 **Web 控制台/BYOK 密钥管理**，不再作为开发者 API 端点对外暴露。

## 二、现状诊断（已闭环，勿重复排查 401）
1. **历史 401 谜团已澄清**：平台 401 从未存在——是指挥官测试脚本把 Bearer 误写成 \*\*\*；repro 三次复测 key94/key78 裸 API 全 200（23:53/23:54/23:57）。
2. **02 的 401 = 配置错位，非平台故障**：02 把 baseUrl 指向 open.ai24x.com + 用 core Hub key（key94）→ open 只认自己库的 api_keys → 401 是预期结果。
3. **单入口 api.ai24x.com 已实测 200**：同 key94 调 core /v1/chat/completions → 200，响应含 ai24x.billing_mode="byok"。**无需 x-byok-project header**（该 header 仅用量归因，非触发条件）。
4. **open 当前对外 /v1 暴露**：nginx 整站反代 127.0.0.1:18080（open server 块 location /），无对 /v1/chat 的隔离——这是历史遗留，需收敛。

## 三、核心机制（已实现，勿重复开发）
- **core BYOK 桥自动触发**：auth_user_id 非空 + open 侧 byok_keys 有 active key 覆盖请求 model → 自动走 BYOK 路由且不扣平台钱包（api/services.py 170/520/820 行集成点）。
- **生产开关**：NSSM AI24X-core AppEnvironmentExtra 含 BYOK_BRIDGE_ENABLED=1 + OPEN_API_BASE=http://127.0.0.1:18080（不在 .env）。
- **open 侧账号映射**：platform_user_id = core auth_users.id（open uid 6=ityizu@foxmail.com 有 deepseek BYOK key，其余账号暂无）。

## 四、待办清单
### A. 02/openclaw 配置修正（P0）✅ 2026-09-04 已落地
- openclaw BYOK provider：baseUrl 改 **api.ai24x.com**，key 用 **core Hub key**（非 open 侧 key）。
- 核实 openclaw provider 是否支持自定义 headers——需要 x-byok-project 时再加；当前实测**不需要**，不加 header 已通。
- **落地回执**：`docs/营销/收发/回复/20260904-0918-02-openclaw迁api单入口-out.md`（key_id=105 专钥，非 key78；gateway 已重启）。

### B. open 对外 API 收敛（方案1 nginx 硬关）✅ 落地中 / 见 20260904-04更新
- **方案1（推荐，已拍板执行）**：nginx 对 open.ai24x.com 的 `/v1/chat/completions|chat/run|responses|models` 返回 **410 endpoint_moved**，引导改用 api.ai24x.com；保留 billing/byok/auth/admin/控制台静态。
- 脚本：`scripts/patch_open_nginx_close_model_api.ps1`（core→open 内桥走 127.0.0.1:18080，不受影响）。

### C. 文档与示例对齐（P1）✅ open 文案
- open `locales.js`：去掉「过渡期仍可用 open 工作区密钥」；产品矩阵标题改为 api.ai24x.com；`?v=20260904a`。
- 历史收发/备份文档不改。

## 五、涉及文件
- core 桥接：api/services.py（BYOK 集成点）
- 生产开关：NSSM AI24X-core AppEnvironmentExtra（BYOK_BRIDGE_ENABLED / OPEN_API_BASE）
- open 网关：p/open/（BYOK key 管理 + 控制台）
- nginx：C:\nginx\conf\nginx.conf（open 443 整站反代，收敛入口）
- 02 配置：openclaw provider 定义（baseUrl/key）

## 六、已实测证据
- key94（core Hub key）调 api.ai24x.com /v1/chat/completions → 200，billing_mode="byok"
- key94 调 open.ai24x.com /v1/chat/completions → 401（预期，open 不认 core key）
- 04 生产：core 8002 + open 18080，BYOK_BRIDGE_ENABLED=1


## 七、2026-09-04 实测更新（02 401 定论 + 决策点）
- **02 的 401 实为测试污染误判，非故障**：02 的 open key（sk-549edf，open api_keys id2，归属 ityizu@foxmail.com，name=subbrain-02-byok-20260901）调 open.ai24x.com /v1/chat/completions → **实测 200**，billing_mode=byok，走 ityizu 账号下 deepseek BYOK key（sk-e18ee active）。open 侧账号映射：uid 6=ityizu(platform 40)→有 deepseek byok key；其余账号暂无。
- **平台 BYOK 桥已就绪无需改代码**：core key（key94=ityizu core uid 40）调 api.ai24x.com → 200 billing_mode=byok。core 按 auth_user_id 自动匹配 open 侧账号 byok key，无 x-byok-project header 也触发。
- **open 站所有接入 guides 已统一 base_url=api.ai24x.com/v1**（openai-sdk/curl/openclaw/cursor/litellm/codex 等），产品文档层面单入口已对齐。
- **待雷总拍板的收敛决策**：
  - A（推荐）：02 内部通道从 open 端点迁到 api.ai24x.com + core Hub key（对外形态统一，但需换 key + 计费路径从 open 侧 byok_usage 变为 core BYOK 桥）。
  - B：02 维持 open key + open.ai24x.com（已工作），仅对外产品继续推 api.ai24x.com 单入口。
  - C：open 对外模型端点（/v1/chat/*、/v1/responses、/v1/models）是否硬收敛为仅内部（nginx 层），杜绝开发者误用 open key 产生 401 困惑——影响 open 现有能力，需雷总拍板。


## 八、02 迁移可行性已实测（可直接执行的配置方案）
- **验证**：ityizu core Hub key（key78 sk-ab7a2d…，core uid 40）调 api.ai24x.com /v1/chat/completions，model=deepseek-chat → **200，billing_mode=byok**。core 自动路由到 ityizu 在 open 侧的 deepseek BYOK key（sk-e18ee）。模型名 deepseek-chat/deepseek-reasoner 无需改。
- **02 迁移配置（openclaw.json ai24x-byok provider）**：
  - baseUrl: https://open.ai24x.com/v1  →  https://api.ai24x.com/v1
  - apiKey: 换成 ityizu 账号下的 core Hub key（key78 sk-ab7a2d… 已实测可用；建议为 02 新建专钥，勿与 04 共用 key78）
  - models / 计费：不变（core 自动识别 BYOK，不扣平台托管）
- **注意**：02 现有 open key（sk-549edf, ityizu）走 open.ai24x.com 当前实测 200 正常——迁移是产品收敛（统一 api.ai24x.com），非修 bug；迁移前备份 openclaw.json，回滚=恢复备份即可。
