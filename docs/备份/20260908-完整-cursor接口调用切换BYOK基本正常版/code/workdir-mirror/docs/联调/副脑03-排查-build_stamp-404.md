# 副脑03 · build_stamp 404 排查（请求已打到旧 FastAPI）

## 主脑已核实

- 本机 `18011`：`/api/public/build_stamp` → **200** + `20260727-resign-v2`
- 公网 `https://a.ai24x.com/api/public/billing/plans` → **200**（说明 `/api` 反代到行情官 API）
- 公网 `https://a.ai24x.com/api/public/build_stamp` → **404** `{"detail":"Not Found"}`（这是 **FastAPI 的 404**，不是 Nginx 静态 404）

结论：**Nginx 没指错域**；但 **8001 上跑的还是旧代码**（磁盘可能已 pull，进程未加载；或 PM2 cwd 不是你 pull 的那份仓库）。

---

## 请原样执行并回报输出

```powershell
Set-Location C:\ai24x01

git fetch origin
git checkout master
git pull origin master
git rev-parse --short HEAD
git log -1 --oneline

# 1) 磁盘有没有新路由？
Select-String -Path .\p\a1\api\server\app\main.py -Pattern "build_stamp|session_resign" 

# 2) PM2 实际 cwd / 脚本（关键）
pm2 list
pm2 show a-api-8001 | Select-String -Pattern "exec cwd|script path|status|pid|name|args"

# 3) 强制从仓库目录重启（不要只 restart 名字）
pm2 delete a-api-8001
Set-Location C:\ai24x01
pm2 start ecosystem.config.cjs --only a-api-8001
pm2 save
Start-Sleep -Seconds 3

# 4) 环回 + 公网
Invoke-RestMethod http://127.0.0.1:8001/api/public/build_stamp
Invoke-RestMethod https://a.ai24x.com/api/public/build_stamp
```

### 如何读

| 现象 | 含义 |
|------|------|
| 磁盘 `Select-String` 无匹配 | pull 失败 / 拉错目录，先修 git |
| 磁盘有，环回 8001 仍 404 | **跑的不是这份代码**（cwd 错 / 多份仓库 / 旧 pyc） |
| 环回 200，公网仍 404 | Nginx `proxy_pass` 不是 `127.0.0.1:8001` |
| 两边都 200 | 部署成功，再无痕登录验收 |

### 清 pyc 兜底（环回仍 404 时）

```powershell
Get-ChildItem C:\ai24x01\p\a1\api\server -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force
pm2 restart a-api-8001 --update-env
```

把上面 1～4 的输出贴回主脑（可打码路径中的用户名以外信息）。
