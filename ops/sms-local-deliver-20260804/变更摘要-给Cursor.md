# 变更摘要（供 Cursor 整理/更新程序库用）

> 目的：行情官(a.ai24x.com) 短信发送本地直发，不再依赖主站(04)。
> 状态：03 已部署生效；04 待更新；本摘要 + 文件在 `C:\bak\sms-local-deliver-20260804\`

## 改动文件

### 1. `p/a1/api/server/app/sms_local.py` —【新增】
本地短信直发模块（a1 用，同步版）：
- `send_sms_106_sync()`：106 网关（GET query 提交，状态码 100=成功）
- `send_sms_juhe_sync()`：聚合数据（POST v.juhe.cn/sms/send，error_code=0 成功）
- `send_sms_tencent_sync()`：腾讯云 SMS（TC3-HMAC-SHA256 签名，SendStatusSet[0].Code=="Ok"）
- `store_otp()/verify_and_consume_otp()`：用户验证码内存存储（300s TTL、一次性消费）
- `check_send_cooldown()/mark_sent()`：同号 60s 发送冷却
- `send_local_sms(cfg, mobile, purpose)`：入口——按 `cfg.sms_active_provider` 选通道（juhe/tencent/106），生成验证码→存 OTP→发送

### 2. `p/a1/api/server/app/main.py` —【修改 3 处】
- **import**：`from .sms_local import send_local_sms, verify_and_consume_otp as verify_local_otp`
- **`/api/auth/sms/send`（proxy_sms_send）**：开头新增本地直发分支
  ```
  if sms_active_provider ∈ (local, juhe, tencent):
      ok, msg = send_local_sms(...)   # 本地发码
      if not ok: 503; return ok
  # 否则走原有转发主站逻辑（identity_proxy 模式）
  ```
- **`/api/auth/register`**：新增本地短信模式处理
  ```
  local_sms = sms_active_provider ∈ (local, juhe, tencent)
  if local_sms and body.phone:
      本地校验验证码 verify_local_otp(...)   # 失败 400
      通过后 extra_headers = {"X-SMS-Internal-Key": cfg.sms_internal_key}
  data = _identity_post("/v1/auth/register", payload, extra_headers=extra)
  ```

### 3. `api/main.py` —【主站修改 1 处】（04 同源代码，**04 必须同步**）
- **`/v1/auth/register`（auth_register）**：新增内部密钥信任跳过
  ```
  _trusted = bool(settings.sms_internal_key) and
             (request.headers.get("X-SMS-Internal-Key") == settings.sms_internal_key)
  if not _trusted:
      检查 sms_106_enabled（原逻辑，false→503 手机号注册暂未开放）
      校验 OTP（原逻辑，失败→400 验证码错误）
  # _trusted 时跳过以上两项，直接建用户（子站已本地验码）
  ```

## 配置（已写入 ai24x_a_cn 库 admin_config，03 完成）
- `sms_active_provider = tencent`（当前生效通道；local=106 / juhe 备用）
- `sms_106_endpoint/account/password/template`（106 备用，账号当前无效）
- tencent/juhe 完整参数已存在于 admin_config（未变）

## 关键约束
- 主站 `SMS_INTERNAL_KEY`（api/.env）与 a1 `AI24X_SMS_INTERNAL_KEY`（a1 .env）必须一致（原红线，未变）
- 03 的 a1 已重启生效；主站 8002（冷备）已生效
- **04 未更新 → 注册提交仍 503「手机号注册暂未开放」**（04 旧代码无信任跳过）

## 回滚
- 备份：`C:\bak\a1-api-pre-smslocal-20260804-153943\`
- 还原 main.py + 删 sms_local.py + 重启；admin_config.sms_active_provider 改回 identity_proxy
