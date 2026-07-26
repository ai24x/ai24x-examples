# 事故：pm2 restart 未加载新代码（build_stamp 404 / 登录已失效）

> 日期：2026-07-27  
> 环境：副脑03 生产（`a.ai24x.com` → `a-api-8001`）  
> 状态：已恢复（`delete` + `start ecosystem.config.cjs`）

## 现象

- 本机行情官登录正常；公网登录后「登录已失效，请重新登录。」
- 热修已推送（登录 JWT 重签、`/api/public/build_stamp`）
- 公网 `https://a.ai24x.com/api/public/billing/plans` → 200  
- 公网 `https://a.ai24x.com/api/public/build_stamp` → **404** `{"detail":"Not Found"}`（FastAPI 404，非 Nginx 静态页）
- 本机 `18011` 同路由 → 200 + `stamp=20260727-resign-v2`

## 事故核心（一句话）

**`pm2 restart <进程名>` 只按 PM2 里已保存的旧进程定义拉起进程，不会重新读取 `ecosystem.config.cjs` 的 cwd/参数；若历史进程 cwd/启动方式已漂移，git pull 后的新代码不会进正在对外服务的那个进程。**

表面上「已 pull + 已 restart」，实际公网仍跑旧 API → 新路由 404、登录仍验签失败。

## 为何容易误判

| 误判 | 实际 |
|------|------|
| restart = 加载新代码 | 多数情况只是重启**同一份旧定义** |
| pull 成功 = 线上已更新 | 只更新磁盘；进程未指向该目录则无效 |
| billing/plans 200 = API 已是最新 | 只能证明打到了某个 a1 API，不能证明是新 commit |
| 登录失效 = 数据库坏了 | 实为 JWT/旧进程；用户表可完全正常 |

## 正确处置（已验证）

```powershell
Set-Location C:\ai24x01
git pull origin master

pm2 delete a-api-8001
pm2 start ecosystem.config.cjs --only a-api-8001
pm2 save

Invoke-RestMethod http://127.0.0.1:8001/api/public/build_stamp
Invoke-RestMethod https://a.ai24x.com/api/public/build_stamp
# 期望 stamp = 20260727-resign-v2
```

副脑03 确认：问题在「restart 未重建 ecosystem 配置」；delete + start 后双端 stamp 正常。

## 防再发（副脑03 / 主脑发令固定口径）

1. **API 发版门禁（必做）**  
   - 有探针则先打：`/api/public/build_stamp`（或后续等价 stamp）  
   - **环回 8001 与公网域名都必须对上同一 stamp**，再宣布发版完成  

2. **何时不能只用 `pm2 restart`**  
   - 改过 `ecosystem.config.cjs`（cwd / args / 端口）  
   - 怀疑进程 cwd 不是当前仓库  
   - pull 后新路由/行为不出现  
   - → 使用：`pm2 delete <名>` + `pm2 start ecosystem.config.cjs --only <名>`  

3. **restart 适用**  
   - 仅改 `.env` 后：`pm2 restart <名> --update-env`（仍建议随后打 stamp / health）  
   - 确认 cwd 正确、仅需重载代码且用同一 ecosystem 启动过时，可用 restart；**有疑一律 delete+start**  

4. **发令文案避免**  
   - 只写「pull + restart」而不写验收探针  
   - 把本机进程名 `a1-api-18011` 误当成生产 `a-api-8001`  

## 相关

- 探针路由：`p/a1/api/server/app/main.py` → `GET /api/public/build_stamp`  
- 生产进程：`ecosystem.config.cjs` → `a-api-8001`（cwd `./p/a1/api/server`，端口 8001）  
- 登录失效根因（代码层）：identity JWT 与 a1 验签密钥漂移；已用登录重签缓解（仍须进程跑到新代码才生效）
