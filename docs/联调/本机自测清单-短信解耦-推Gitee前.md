# 本机自测清单 · 行情官短信解耦（推 Gitee 前）

> 2026-08-04 · 流程：本机改码 → 本机验通 → 推 Gitee → 副脑只拉码+配置+重启

## A. 已自动跑过（本机）

| 项 | 结果 |
|---|---|
| AST 语法：`api/main.py`、a1 `main.py` / `sms_local.py` / `admin_ui.py` | ✅ |
| `sms_local` OTP：存/验/一次性消费/错误码/冷却 | ✅ |
| 信任跳过条件（有 key 匹配 / 不匹配 / 空 key） | ✅ |
| 代码点：`_trusted`、`send_local_sms`、`local` 下拉、缺密钥 fail-fast | ✅ 存在 |

## B. 本机可选（有环境再跑）

1. 起 a1 API（本机端口）→ `POST /api/auth/sms/send`（需配 `sms_active_provider=local` + 有效 `sms_106_*` 才真发）
2. 起 core API → 带/不带 `X-SMS-Internal-Key` 打 `POST /v1/auth/register`（手机路径）
3. 无真 106 账号时：只验「未配置返回明确失败」「OTP 本地逻辑」，不宣称现网通

## C. 推 Gitee 前人工确认

- [ ] 不把真实 `.env` / 密钥提交进仓库
- [ ] 提交范围仅：相关 py + 联调文档（作战卡 / 复制下发）
- [ ] 副脑指令改为：**拉指定提交 + 配置 + 重启**（禁止现场改业务代码）

## D. 推送后现网短验收（03/04）

1. 04：信任跳过上线；`SMS_106_ENABLED` 仍 false  
2. 03：`sms_active_provider=local`；106 移动号收到码  
3. 发码 → 注册 → 登录；`auth_users.id` = `ai24x_a_cn.users.id`  
4. www 手机注册仍关；老用户登录 OK  
