# Google / Apple 一键登录配置与验收（2026-08-16）

> 状态：代码已上线（feat(core): Google/Apple 一键登录 + feat(markets): 登录区按钮）
> 凭据全部走环境变量，本文件不含任何密钥值。

## 一、环境变量清单（仅 .env，勿进 git/ops/群）
| 变量 | 说明 |
| --- | --- |
| GOOGLE_OAUTH_CLIENT_ID | Google OAuth 客户端 ID |
| GOOGLE_OAUTH_CLIENT_SECRET | Google OAuth 客户端密钥 |
| APPLE_TEAM_ID | Apple Developer Team ID（10 位） |
| APPLE_SERVICE_ID | Sign in with Apple 的 Service ID（形如 com.xxx.signin） |
| APPLE_KEY_ID | 生成的 Sign in with Apple 密钥 Key ID |
| APPLE_PRIVATE_KEY | .p8 私钥内容（含 -----BEGIN 头）或文件路径；多行内容可用 \n 转义为单行 |
| OAUTH_REDIRECT_BASE | 可选；redirect_uri 前缀覆盖，默认 https://www.ai24x.com；本机测试设 http://127.0.0.1:8000 |

## 二、Redirect URI 清单（需在 Google / Apple 后台精确登记）
- 生产 Google：https://www.ai24x.com/v1/auth/google/callback
- 生产 Apple：https://www.ai24x.com/v1/auth/apple/callback
- 本机测试 Google：http://127.0.0.1:8000/v1/auth/google/callback
- 本机测试 Apple：http://127.0.0.1:8000/v1/auth/apple/callback

## 三、Apple 凭据获取步骤
1. Apple Developer → Certificates, Identifiers & Profiles → Identifiers → 新建 Service ID（填写描述 + Identifier，如 com.ai24x.markets.signin）
2. 勾选 Sign in with Apple → Configure：选择 Primary App ID（或 Any App ID），记下 Service ID
3. 回到 Identifiers → Keys → 新建 Key → 勾选 Sign in with Apple → 选择该 Service ID → 下载 .p8（仅下载一次）
4. 记录 Key ID；TEAM_ID 在 Apple Developer 账号页面右上角
5. 将 .p8 内容写入生产 .env 的 APPLE_PRIVATE_KEY（建议文件路径方式，文件放服务器非 web 目录）

## 四、接口语义
- GET /v1/auth/providers → {"google": bool, "apple": bool}（凭据是否配置；不含密钥）
- GET /v1/auth/google/login?next= → 302 Google；callback 换 token + userinfo → 按 email upsert 用户 → 签发与 /v1/auth/login 一致令牌 → 302 回 next 并种 .ai24x.com cookie（本地为 host-only）
- GET /v1/auth/apple/login?next= → 302 Apple；callback 换 token + 校验 id_token（iss/aud/exp）→ 同上
- 凭据缺失：providers=false；login/callback → 503 {"code":-1,"msg":"config_missing"}
- 安全：state 随机 + 服务端内存校验（10 分钟过期）；email 缺失/未验证/被冻结 → 302 next 带 oauth_error 提示；密钥不进日志/响应
- 前端：login.html 与 markets app.html 启动时拉 providers，按可用性显示按钮；回跳 #oauth=1 由前端写 localStorage 并清理 hash

## 五、生产验收清单
- [ ] 04 配置 .env 六项变量（Google 两件套 + Apple 四件套）后重启 core，/health 正常
- [ ] GET /v1/auth/providers 返回 {"google":true,"apple":true}
- [ ] www login.html 显示 Google/Apple 按钮；markets app.html 未登录态显示按钮
- [ ] Google 新邮箱登录 → 自动建号 → 跳 next 后已登录；再用同邮箱密码登录老账号 → 绑定同一账号
- [ ] Google 取消授权 → 回跳不报错（回到登录页）
- [ ] Apple 登录 → 需雷总用 iPhone 实测（Sign in with Apple 弹窗、隐藏邮箱转发、回跳登录成功）
- [ ] markets 登录区按钮 → 登录后返回 app.html 自动识别登录态（PRO 徽章/自选可用）
- [ ] 私钥安全性复核：rg 项目内无 client_secret/private_key 明文

## 六、备注
- Apple 回调用 response_mode=query（GET）；生产可进一步做 id_token JWKS 验签（当前校验 iss/aud/exp）
- 若未来接入更多 OAuth 提供商，在 oauth_social.py 按 google/apple 同构扩展即可
