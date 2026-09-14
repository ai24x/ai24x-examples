# 行情官短信独立直发 · 变更说明 v1.0

> 2026-08-04 雷总拍板：行情官(a.ai24x.com) 短信独立直发，与 Token/主站(04) 彻底解耦
> 变更人：副脑03（运维CN） | 备份：`C:\bak\a1-api-pre-smslocal-20260804-153943`
> 交付包：本目录（`sms-local-deliver-20260804`）

---

## 一、背景

- 用户注册提示「短信服务暂不可用」：主站(04) `SMS_106_ENABLED` 未开 → 所有短信请求 503
- 且 106 网关账号无效（101 验证失败）；admin_config 已有 **腾讯云(tencent)/聚合数据(juhe)** 完整通道配置
- 雷总拍板：行情官短信本地直发，不再经过 04

## 二、改动清单

### 1. a1（行情官后端，所有节点）
| 文件 | 改动 |
|---|---|
| `p/a1/api/server/app/sms_local.py` | **新增**：本地直发（106/juhe/tencent 三通道同步客户端）+ 用户 OTP 内存存储 + 发送冷却 |
| `p/a1/api/server/app/main.py` | ① import sms_local；② `/api/auth/sms/send`：`sms_active_provider ∈ (local/juhe/tencent)` 时本地直发；③ `/api/auth/register`：本地直发模式下本地校验验证码，通过后带 `X-SMS-Internal-Key` 转发主站（主站跳过短信校验） |

### 2. 主站（token 平台后端 = 04 同源代码）
| 文件 | 改动 |
|---|---|
| `api/main.py` | `/v1/auth/register`：带有效 `X-SMS-Internal-Key` 视为子站已验证（跳过 `sms_106_enabled` 检查与 OTP 校验）；无 key 保持原逻辑 |

## 三、配置（a1 库 admin_config，03 已写入）

| key | value |
|---|---|
| `sms_active_provider` | `tencent`（local=106 / juhe / tencent 三选一） |
| `sms_106_endpoint/account/password/template` | 106 备用通道（当前 106 账号无效，不推荐） |
| `sms_tencent_secret_id/secret_key/sdk_app_id/sign/template_id` | 腾讯云通道（**已在库，当前生效**） |
| `sms_juhe_key/sign/template/template_id` | 聚合数据通道（模板未过审，暂不可用） |

## 四、测试结果（2026-08-04 全部通过）

| 项 | 结果 |
|---|---|
| 本地直发 tencent 通道 | ✅ 200 发送成功（测试实例 + 生产 8001 均验证） |
| 106 通道 | ❌ 101 验证失败（账号无效，备用） |
| juhe 通道 | ❌ 模板未过审（备用） |
| OTP 本地存储/校验 | ✅ 正确码通过 / 一次性消费 / 错误码拒绝 |
| 主站 register 信任跳过 | ✅ 无 key → 503 拦截；有 key → 200 创建 |
| 生产 `a.ai24x.com/api/auth/sms/send` | ✅ 200 验证码已发送 |

## 五、各节点更新步骤

### 03（本机）✅ 已完成
- a1：`sms_local.py` + `main.py` 已替换，`Restart-Service AI24X-a1-api` 已生效
- 主站(冷备 8002)：`api/main.py` 已替换，`Restart-Service AI24X-core` 已生效

### 04（新加坡生产主站）⚠️ 必须更新
1. 替换 `api/main.py`（本目录 `api/main.py`）
2. 重启主站服务（NSSM/对应服务）
3. 验证：`POST https://api.ai24x.com/v1/auth/register` 带 `X-SMS-Internal-Key` 返回 200/409（而非 400 验证码错误）
4. 注意：04 的 `SMS_INTERNAL_KEY` 须与 03 的 `AI24X_SMS_INTERNAL_KEY` 一致（原红线要求，未变）

### 01/02（如运行 a1/主站同源代码）
- 按第 1、2 项同步替换 + 重启

## 六、回滚

- a1 备份：`C:\bak\a1-api-pre-smslocal-20260804-153943\`（含 .env.bak）
- 回滚：还原 `app/main.py`（删除 `sms_local.py`）→ `Restart-Service AI24X-a1-api`
- 主站：还原 `api/main.py` → 重启
- 配置回滚：`admin_config.sms_active_provider = identity_proxy`（恢复转发主站模式）

## 七、安全说明

- 注册信任跳过仅对持 `X-SMS-Internal-Key`（内部密钥，未公开）的请求生效；无 key 的公共请求仍走严格校验
- 用户 OTP 存进程内存（5 分钟 TTL，一次性消费）；服务重启后未消费验证码失效（可接受）
- 生产 `identity_api_base` 保持 `https://api.ai24x.com`（未违反红线）
