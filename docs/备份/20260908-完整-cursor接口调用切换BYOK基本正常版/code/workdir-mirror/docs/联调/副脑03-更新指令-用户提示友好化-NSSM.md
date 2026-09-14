# 副脑03 · 更新指令（用户提示友好化）

> 发令：2026-07-31  
> **进程管理：NSSM / Windows 服务（禁止 pm2）**  
> 勿整文件覆盖 `.env`；本包无 env 变更。

## 本包内容

| 项 | 说明 |
|----|------|
| 主站 `api/` | 注册/短信/登录等 `detail` 改用户口吻；配置缺失不再露密钥/env 名 |
| a1 代理 | `_identity_post/_get` 整形 FastAPI 校验错误，去掉 `Value error,` 与运维泄漏 |
| 前端 | `index.html` / `account.html` 错误兜底；注册前端先校验 6 位数字验证码 |
| SW | 静态缓存 **v29**（用户需 Ctrl+F5 或等 SW 更新） |

## 执行（PowerShell · 可整段给 OpenClaw）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull gitee master
# 若远端名为 origin：git pull origin master
git log -1 --oneline
# 期望含：用户提示友好 / user-facing auth copy

Get-Service AI24X-core, AI24X-a1-api, AI24X-a1-web | Format-Table Name, Status
Restart-Service AI24X-core
Restart-Service AI24X-a1-api
# 静态：拉代码后一般立刻生效；可选
# Restart-Service AI24X-a1-web

Start-Sleep -Seconds 3
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
try { (Invoke-WebRequest "http://127.0.0.1:8001/health" -UseBasicParsing).StatusCode } catch { $_.Exception.Message }
```

## 验收

1. https://a.ai24x.com/ （**Ctrl+F5**）打开注册  
2. 不填验证码点注册 → 友好短句（如「请填写验证码」），**无** JSON / `Value error` / `identity_api` / 密钥字样  
3. 填非 6 位点注册 → 「请填写短信里的 6 位数字验证码」类口吻  
4. 获取验证码正常时仍显示「验证码已发送」等业务句  
5. 回报：`git log -1`、两服务 health、验收是否通过  

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
# 记下本包提交 hash 后：
git revert <本包提交hash> --no-edit
# 或按文件回退到上一版后：
Restart-Service AI24X-core
Restart-Service AI24X-a1-api
```
