# 副脑03 更新指令 · 行情官用户中心默认进入「会员」栏目（含分享链接 ?i= 不再跳转）

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee，拉码后 `git log -1` 应含「默认进入会员」「不再跳转」「直达」

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 前台-默认栏目 | `account.html` 进入用户中心**恒为「会员」栏目**：不再因 localStorage 残留邀请码跳「邀请推广」，也不因 URL 带 `?i=` 邀请参数跳「邀请推广」 |
| 前台-邀请关系 | 分享链接 `?i=XXX` 仍正常记录邀请关系：登录后自动绑定邀请码（`tryAutoInviteBind` 逻辑未改），仅不影响默认展示栏目 |
| 前台-hash 直达 | 保留 `#vip` / `#invite` / `#agent` 直达（index/shell/partner 等入口链接沿用该约定，点「邀请」仍进邀请栏目） |

## 二、执行（PowerShell · 整段复制给 OpenClaw）

```powershell
$ErrorActionPreference = 'Stop'
$repo = 'C:\ai24x01'

Write-Host '=== 1/3 拉码 ===' -ForegroundColor Cyan
Set-Location $repo
git checkout master
git pull gitee master
if (-not $?) { git pull origin master }
git log -1 --oneline
if (-not (git log -1 --oneline | Select-String '默认进入会员|不再跳转|直达')) { Write-Host '!! 未拉到目标提交，先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 校验（纯前端改动，account.html 静态文件无需重启）===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'https://a.ai24x.com/account.html' -UseBasicParsing -TimeoutSec 10; Write-Host "account.html=$($r.StatusCode)（浏览器 Ctrl+F5 刷新生效）" } catch { Write-Host "account.html FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1 ===' -ForegroundColor Green
```

## 三、上线后人工动作

1. `https://a.ai24x.com/account.html` 登录后 Ctrl+F5：默认落在「会员」卡片（含 `?i=BWPX3Z8B` 这类分享链接进入）。
2. 分享链接进入后，邀请码仍会自动绑定（邀请关系不丢），只是页面默认展示「会员」。
3. 首页「邀请」入口（`#invite`）、页脚「邀请奖励」（`#invite`）、「开通 VIP」（`#vip`）直达正常。

## 四、回滚

```powershell
# 纯前端改动：还原上次备份的 web 目录即可；无数据库结构变更，无需回滚数据库
```