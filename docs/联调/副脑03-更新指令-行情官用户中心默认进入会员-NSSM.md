# 副脑03 更新指令 · 行情官用户中心默认进入「会员」栏目（修复默认跳「邀请推广」）

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee，拉码后 `git log -1` 应含「默认进入会员」「邀请码残留」「直达」

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 前台-默认栏目 | `account.html` 进入用户中心默认显示「会员」栏目，不再因 localStorage 残留邀请码（`ai24x_invite_code`）默认跳到「邀请推广」 |
| 前台-分享链接 | 仍保留：URL 显式带邀请参数（`?i=` / `?invite=` / `?inv=` / `?ref=`）时默认进「邀请推广」，方便分享链接场景 |
| 前台-hash 直达 | 补齐 `#vip` / `#invite` / `#agent` 直达支持（index/shell/partner 等入口链接沿用该约定） |

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
if (-not (git log -1 --oneline | Select-String '默认进入会员|邀请码残留|直达')) { Write-Host '!! 未拉到目标提交，先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 校验（纯前端改动，account.html 静态文件无需重启）===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'https://a.ai24x.com/account.html' -UseBasicParsing -TimeoutSec 10; Write-Host "account.html=$($r.StatusCode)（浏览器 Ctrl+F5 刷新生效）" } catch { Write-Host "account.html FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1 ===' -ForegroundColor Green
```

## 三、上线后人工动作

1. `https://a.ai24x.com/account.html` 登录后 Ctrl+F5：默认落在「会员」栏目（即使曾绑定/生成过邀请码）。
2. 首页「我的」入口、顶栏「我的」入口均默认进「会员」。
3. 分享链接 `account.html?i=XXX` 仍自动进「邀请推广」；`#invite` / `#vip` / `#agent` 直达正常。

## 四、回滚

```powershell
# 纯前端改动：还原上次备份的 web 目录即可；无数据库结构变更，无需回滚数据库
```