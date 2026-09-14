# 副脑03 更新指令 · 行情官用户中心精简为「会员 / 伙伴计划」两栏（邀请推广并入会员卡片）

> 发令：2026-08-05
> 进程管理：NSSM / Windows 服务（禁止 pm2）
> 前置：主脑本机已验通并推 Gitee，拉码后 `git log -1` 应含「精简」「并入会员」「1-2-3」

## 一、本包内容

| 模块 | 内容 |
|------|------|
| 前台-栏目精简 | `account.html` 顶部 Tab 由「会员 / 邀请推广 / 伙伴计划」精简为「会员 / 伙伴计划」两个；「邀请推广」内容并入「会员」卡片下方一起展示 |
| 前台-邀请关系 | 邀请码生成/复制/绑定等全部功能不变，只是不再单独占一个 Tab；`#invite` 入口自动落到「会员」栏（内容随会员卡片显示） |
| 前台-伙伴步骤 | 伙伴计划三步引导与分区标题改用数字「1 / 2 / 3」，不再用中文数字 |

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
if (-not (git log -1 --oneline | Select-String '精简|并入会员|1-2-3')) { Write-Host '!! 未拉到目标提交，先别继续，回报 git log -1' -ForegroundColor Red; exit 1 }

Write-Host '=== 2/3 校验（纯前端改动，account.html 静态文件无需重启）===' -ForegroundColor Cyan
try { $r = Invoke-WebRequest 'https://a.ai24x.com/account.html' -UseBasicParsing -TimeoutSec 10; Write-Host "account.html=$($r.StatusCode)（浏览器 Ctrl+F5 刷新生效）" } catch { Write-Host "account.html FAIL $($_.Exception.Message)" -ForegroundColor Red }
Write-Host '=== 完成。回执要求：git log -1 ===' -ForegroundColor Green
```

## 三、上线后人工动作

1. `https://a.ai24x.com/account.html` 登录后 Ctrl+F5：顶部只有「会员 / 伙伴计划」两个 Tab，默认「会员」，会员卡片下方即「邀请获取次数」内容。
2. 分享链接 `?i=XXX` 进入默认「会员」，邀请码自动绑定不受影响；`#invite` 入口同样落在「会员」栏。
3. 「伙伴计划」三步引导显示 1 / 2 / 3。

## 四、回滚

```powershell
# 纯前端改动：还原上次备份的 web 目录即可；无数据库结构变更，无需回滚数据库
```