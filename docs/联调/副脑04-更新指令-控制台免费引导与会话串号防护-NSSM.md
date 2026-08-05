# 副脑04 · 更新指令（控制台免费引导 + 会话串号防护 · 静态为主）

> 发令：2026-08-03 · **副脑04 = 对外生产**  
> 进程：静态 `web/` 拉码即生效（硬刷新）；若本包含 `api/main.py` 注册礼接线则 **NSSM `AI24X-core` 必须重启**  
> **禁止**整文件 Write 覆盖 `api/.env`  
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

---

## 本包内容

| 项 | 说明 |
|----|------|
| 注册欢迎礼 | `grant_signup_bonus` 在注册成功路径调用（一次性 5000 token） |
| 会话串号 | 控制台比对邮箱；**有 JWT 时默认不带 X-API-Key**；后端余额接口优先 JWT；不一致先清 Key 再试 |
| 免费引导 | 非 VIP 显示欢迎卡 + 今日 shared 剩余；Playground 默认 `shared`；文案区分 VIP 日赠 vs 免费共享 |

---

## 执行（PowerShell）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline

# 若 pull 含 api/main.py（注册礼）：
Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 8

# 静态硬刷新验证
curl.exe -sS -o NUL -w "console=%{http_code}`n" "https://www.ai24x.com/console.html"
```

---

## 验收

1. **干净浏览器**（或清 `localStorage` 的 `ai24x_auth_*`）用新邮箱注册 → 钱包有约 5000 欢迎礼、`plan=free`  
2. 控制台概览：套餐「免费档」；出现免费共享引导；Playground 默认 `shared`  
3. 若故意把旧 VIP 号 JWT 与另一邮箱 UI 混用 → 应提示不一致并退出（正常登录不会触发）  
4. **禁止**用 `lei@itxin.com` VIP 主号会话当「新用户」样板  

---

## 回滚

```powershell
git log -5 --oneline
git checkout <上一好 SHA> -- web/js/console.js web/console.html web/config/locales.js api/main.py
Restart-Service AI24X-core   # 仅当回滚了 api
```
