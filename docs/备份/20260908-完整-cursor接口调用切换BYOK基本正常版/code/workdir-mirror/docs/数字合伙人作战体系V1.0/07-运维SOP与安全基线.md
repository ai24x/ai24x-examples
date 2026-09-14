# 07 · 运维 SOP 与安全基线

> 版本：V1.0 · 2026-08-03 · AI24X 实战沉淀
> 解决的问题：生产环境怎么管才不出事（服务、备份、回滚、安全）

---

## 一、服务管理总览

### Windows 服务（NSSM 注册，替代 PM2）

| 服务名 | 可执行 | 端口 | 说明 |
|--------|--------|------|------|
| nginx | nginx.exe | 80/443 | 反向代理 + SSL |
| AI24X-core | python uvicorn | 127.0.0.1:8000 | 核心后端（FastAPI） |
| AI24X-a1-web | python http.server | 127.0.0.1:18001 | a1 静态页面 |
| AI24X-a1-api | python uvicorn | 127.0.0.1:18011 | a1 API |
| postgresql-x64-15 | postgres | 5432 | 数据库（原生服务） |
| OpenClaw | node | 127.0.0.1:18789 | 主脑网关 |

> ⚠️ 03 用 Nginx 直管，不用 PM2；04 用 NSSM 注册 Windows 服务。**PM2 只在本地开发用**（ecosystem.local.config.js）。

### 服务启停命令

```powershell
# 查状态
Get-Service nginx, AI24X-core, AI24X-a1-web, AI24X-a1-api, postgresql-x64-15
# 单独重启
net stop AI24X-core && net start AI24X-core
# Nginx 热重载（不重启）
& "<nginx安装目录>\nginx.exe" -s reload
# 配置语法检查
& "<nginx安装目录>\nginx.exe" -t
```

### 全量重启顺序（按依赖）

```
PostgreSQL（最先）→ Nginx → AI24X-core → a1-web → a1-api（最后）
```

---

## 二、健康检查清单

```powershell
# 1) 服务状态
Get-Service *AI24X*,nginx,postgres* | Format-Table Name,Status

# 2) 端口监听
Get-NetTCPConnection -LocalPort 80,443,5432,8000,18001,18011 -State Listen

# 3) Web 健康端点（期望 200）
curl.exe -s -o /dev/null -w "Core: %{http_code}\n" https://your-domain.com/health
curl.exe -s -o /dev/null -w "API: %{http_code}\n" https://api.your-domain.com/health

# 4) 磁盘空间（C盘可用 <10GB 警告，<5GB 紧急）
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N="FreeGB";E={[math]::Round($_.Free/1GB,2)}}

# 5) 数据库连通
& "<PostgreSQL安装目录>\15\bin\psql.exe" -U postgres -d ai24x -c "SELECT 1;"
```

---

## 三、备份与恢复

### 完整备份
```powershell
powershell -ExecutionPolicy Bypass -File "<项目根目录>\scripts\backup\run_full_backup_ok_label.ps1"
```
备份到 `<备份归档目录>\ai24x01-{timestamp}-OK版\`，含 code/ + databases/*.sql

### 数据库独立备份/恢复
```powershell
# 导出
& "<PostgreSQL安装目录>\15\bin\pg_dump.exe" -U postgres -d ai24x -F p > "<备份目录>\ai24x-$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
# 恢复
& "<PostgreSQL安装目录>\15\bin\psql.exe" -U postgres -d ai24x -f "<备份目录>\ai24x-20260727_115841.sql"
```

### 回滚铁律
1. 改前先备份（scp 拉本地或 cp xxx.bak）
2. **无回滚路径不改**
3. 回滚后必须健康检查

---

## 四、安全基线（审计发现并修复）

### 高危项（已发现）
1. **SSL 私钥权限过宽**：任何本地用户可读 → 修复为仅 SYSTEM + Administrators
   ```powershell
   icacls "<nginx安装目录>\conf\ssl\ai24x-key.pem" /inheritance:r
   icacls "<nginx安装目录>\conf\ssl\ai24x-key.pem" /grant "SYSTEM:(R)"
   icacls "<nginx安装目录>\conf\ssl\ai24x-key.pem" /grant "BUILTIN\Administrators:(R)"
   ```
2. **.env 文件权限过宽**：含数据库密码/API Key → 修复为仅管理员可读
3. **PostgreSQL 监听 0.0.0.0**：应改 `listen_addresses = '127.0.0.1'`（防火墙虽拦，双保险）
4. **bak/ 历史 .env 副本**：备份中凭证过时仍敏感 → 备份前剥离 .env

### 已实现的防护 ✅
- 防火墙：默认 BlockInbound（仅 80/443 放行）
- SSL：TLSv1.2/1.3 + HSTS 1年 + 强密码套件
- 安全头：X-Content-Type-Options / X-Frame-Options / X-XSS-Protection / Referrer-Policy / Permissions-Policy
- 敏感路径拦截：.git/.env/.sql/.bak 等 403
- 限流：general 10r/s、api 30r/s、auth 5r/s、静态 50r/s、20连接/IP

### 可补充（P1）
- CSP 头（需严格测试）
- 日志轮转（Nginx 日志无轮转，C盘风险）
- Fail2Ban 式 IP 拦截

---

## 五、OpenClaw Gateway 重启操作手册（重点！）

> ⚠️ **禁止使用**：`openclaw gateway restart` / `openclaw gateway stop`
> （WebSocket 方式有活跃连接时会超时卡死！）

### 标准重启流程（直接操作 Windows 服务，100% 不卡死）
```powershell
taskkill /f /fi "IMAGENAME eq node.exe"
timeout 3
schtasks /run /tn "OpenClaw Gateway"
```

### 查看状态
```powershell
openclaw gateway status
```

### 异常修复
```powershell
openclaw doctor --fix
openclaw gateway start
```

---

## 六、生产环境配置监测（升级信号）

| 信号 | 阈值 | 动作 |
|------|------|------|
| 内存使用率 | 持续 >80% | 报雷总申请升级 |
| CPU 使用率 | 持续 >70% | 同上 |
| C盘可用 | <20% | 先清日志/备份，仍低则扩容 |
| 04 执行层变重 | 调研/抓取变重 | 04 优先升 4核16G |
| A1 流量起量 | 行情官访问起量 | 03 升 4核16G |

监测：每月1日 09:30 生产体检 cron + 晨间汇总自动带 03/04 资源快照。

---

## 七、常见故障排查速查

| 问题 | 原因 | 排查 |
|------|------|------|
| 502 Bad Gateway | Nginx 连不上后端 | 查 AI24X-core 服务 + 8000 端口 + nginx error.log |
| 429 Too Many Requests | 触发限流 | 查 access.log 来源 IP；正常流量需扩限流 |
| 数据库连接失败 | PG 未启动/连接池满 | 查服务 + 5432 + pg_log |
| SSL 即将过期 | 证书到期 | `openssl x509 -in cert.pem -noout -dates`；wacs --renew |
| C盘空间不足 | 日志/备份堆积 | cleanmgr + 清理临时文件 + 日志轮转 |

---

*🎇 我命由我不由天，热爱每一天！*
*—— AI24X 指挥中心 · 运维 SOP 与安全基线 V1.0*
