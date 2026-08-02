# 副脑04 · 更新指令（接入案例 Lobe/OpenClaw + PayPal 中英文提示 · 静态为主）

> 发令：2026-08-02 · 目标提交 `a49d604`  
> 范围：主要 `web/`（**一般不必**重启 `AI24X-core`）  
> **禁止**整文件覆盖 `api/.env`；**禁止**提交任何 `.env.bak*`

## 本包内容

| 项 | 说明 |
|----|------|
| 接入案例 | 新页 `guides/lobechat.html`；重写 `guides/openclaw.html`；guides 首页置顶；sitemap 含 lobechat |
| 控制台 | PayPal「正在创建订单」按界面语言中/英（非中文一律英） |
| 安全 | 主仓 `.gitignore` 已覆盖 `*.bak` / `.env.*`（04 本地仍须删掉已有密钥 bak） |
| 规划 | `/v1/responses` 仅排期，**本包不含**代码 |

## 执行前：工作区纪律（P0）

```powershell
Set-Location C:\ai24x01
# 1) 密钥 bak / 临时文件：移出仓库或删除（勿 git add）
#    api/.env.bak* 、*.bak-og-* 、temp\ 等
Get-ChildItem -Recurse -Force -Include *.bak,*.bak-*,*.env.bak* -ErrorAction SilentlyContinue |
  Select-Object -First 30 FullName

# 2) pricing / models/index / guides/index 若有本地未推改动：
#    先 git diff 发给科设；未回复前不要 commit 这三页
git status --short
```

## 拉码与验收

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline
# 期望：含「接入案例」或 lobechat / PayPal 文案 的提交

# 一般不必 Restart-Service AI24X-core

curl.exe -sS -o NUL -w "lobechat=%{http_code}`n" https://www.ai24x.com/guides/lobechat.html
curl.exe -sS -o NUL -w "openclaw=%{http_code}`n" https://www.ai24x.com/guides/openclaw.html
curl.exe -sS https://www.ai24x.com/guides/index.html | Select-String -Pattern "lobechat|LobeChat"
curl.exe -sS https://www.ai24x.com/console.html | Select-String -Pattern "console\.js\?v=20260802i|api\.js\?v=20260802i"
curl.exe -sS https://www.ai24x.com/sitemap.xml | Select-String -Pattern "lobechat"
```

**人工**：英文界面控制台点 PayPal → 提示应为 `Creating PayPal order…`（非中文句）。

## 并行业务验收（回报主脑）

1. lobechat / openclaw → **200**；guides 首页有 LobeChat  
2. PayPal 英文提示 OK  
3. 工作区无 `.env.bak` 出现在 `git status`  
4. （持续）协调 **PayPal Live 真付小额** 一笔 → 回跳加额 → 订单 paid  

## 不做

- 本包不做 `/v1/responses`  
- 不把 B 类运维私有 conf / `database_config.txt` 推回 Gitee  
- 不整文件 Write `.env`
