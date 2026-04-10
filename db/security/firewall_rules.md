# AI24X海外节点防火墙规则

## 服务器信息
- **公网IP**: 43.160.246.30
- **内网IP**: 10.3.4.13
- **地域**: 新加坡
- **运营商**: 腾讯云国际

## 默认规则（最小权限原则）

### 入站规则（Ingress）
| 端口 | 协议 | 来源 | 动作 | 说明 |
|------|------|------|------|------|
| 22 | TCP | 管理IP白名单 | ALLOW | SSH管理（仅限管理员） |
| 80 | TCP | 0.0.0.0/0 | ALLOW | HTTP流量 |
| 443 | TCP | 0.0.0.0/0 | ALLOW | HTTPS流量 |
| 9090 | TCP | 管理IP白名单 | ALLOW | Prometheus监控 |
| 3000 | TCP | 管理IP白名单 | ALLOW | Grafana仪表盘 |
| 5432 | TCP | 127.0.0.1 | ALLOW | PostgreSQL（仅本地） |
| 6379 | TCP | 127.0.0.1 | ALLOW | Redis（仅本地） |
| 8000 | TCP | 127.0.0.1 | ALLOW | 后端应用（仅本地） |
| * | * | 0.0.0.0/0 | DENY | 默认拒绝所有其他入站 |

### 出站规则（Egress）
| 端口 | 协议 | 目标 | 动作 | 说明 |
|------|------|------|------|------|
| * | * | 0.0.0.0/0 | ALLOW | 允许所有出站连接 |

## 管理IP白名单
```
# 主脑（CEO）
115.223.183.83/32

# 副脑01（开发）
42.192.1.93/32

# 副脑02（前端）
118.89.111.23/32

# 副脑03（国内运维）
123.207.199.238/32

# 副脑04（本机）
43.160.246.30/32
10.3.4.13/32
```

## Windows防火墙配置脚本

### PowerShell脚本
```powershell
# 删除现有规则
Remove-NetFirewallRule -Name "AI24X-*" -ErrorAction SilentlyContinue

# 入站规则
# SSH（仅管理IP）
New-NetFirewallRule -Name "AI24X-SSH" `
    -DisplayName "AI24X SSH Management" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 22 `
    -RemoteAddress @("115.223.183.83", "42.192.1.93", "118.89.111.23", "123.207.199.238") `
    -Action Allow

# HTTP/HTTPS（公网）
New-NetFirewallRule -Name "AI24X-HTTP" `
    -DisplayName "AI24X HTTP" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 80 `
    -Action Allow

New-NetFirewallRule -Name "AI24X-HTTPS" `
    -DisplayName "AI24X HTTPS" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 443 `
    -Action Allow

# 监控端口（仅管理IP）
New-NetFirewallRule -Name "AI24X-Prometheus" `
    -DisplayName "AI24X Prometheus" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 9090 `
    -RemoteAddress @("115.223.183.83", "42.192.1.93", "118.89.111.23", "123.207.199.238") `
    -Action Allow

New-NetFirewallRule -Name "AI24X-Grafana" `
    -DisplayName "AI24X Grafana" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 3000 `
    -RemoteAddress @("115.223.183.83", "42.192.1.93", "118.89.111.23", "123.207.199.238") `
    -Action Allow

# 数据库端口（仅本地）
New-NetFirewallRule -Name "AI24X-PostgreSQL" `
    -DisplayName "AI24X PostgreSQL" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5432 `
    -RemoteAddress "127.0.0.1" `
    -Action Allow

New-NetFirewallRule -Name "AI24X-Redis" `
    -DisplayName "AI24X Redis" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 6379 `
    -RemoteAddress "127.0.0.1" `
    -Action Allow

# 应用端口（仅本地）
New-NetFirewallRule -Name "AI24X-Backend" `
    -DisplayName "AI24X Backend" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8000 `
    -RemoteAddress "127.0.0.1" `
    -Action Allow

# 默认拒绝所有其他入站
New-NetFirewallRule -Name "AI24X-Default-Deny" `
    -DisplayName "AI24X Default Deny" `
    -Direction Inbound `
    -Action Block

# 出站规则（允许所有）
New-NetFirewallRule -Name "AI24X-Outbound" `
    -DisplayName "AI24X Outbound" `
    -Direction Outbound `
    -Action Allow
```

### 批处理脚本（简化版）
```batch
@echo off
echo Configuring AI24X firewall rules...

REM 删除现有规则
netsh advfirewall firewall delete rule name="AI24X-SSH" >nul 2>&1
netsh advfirewall firewall delete rule name="AI24X-HTTP" >nul 2>&1
netsh advfirewall firewall delete rule name="AI24X-HTTPS" >nul 2>&1
netsh advfirewall firewall delete rule name="AI24X-Prometheus" >nul 2>&1
netsh advfirewall firewall delete rule name="AI24X-Grafana" >nul 2>&1
netsh advfirewall firewall delete rule name="AI24X-PostgreSQL" >nul 2>&1
netsh advfirewall firewall delete rule name="AI24X-Redis" >nul 2>&1
netsh advfirewall firewall delete rule name="AI24X-Backend" >nul 2>&1

REM 入站规则
REM SSH（仅管理IP）
netsh advfirewall firewall add rule name="AI24X-SSH" dir=in action=allow protocol=TCP localport=22 remoteip=115.223.183.83,42.192.1.93,118.89.111.23,123.207.199.238

REM HTTP/HTTPS（公网）
netsh advfirewall firewall add rule name="AI24X-HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="AI24X-HTTPS" dir=in action=allow protocol=TCP localport=443

REM 监控端口（仅管理IP）
netsh advfirewall firewall add rule name="AI24X-Prometheus" dir=in action=allow protocol=TCP localport=9090 remoteip=115.223.183.83,42.192.1.93,118.89.111.23,123.207.199.238
netsh advfirewall firewall add rule name="AI24X-Grafana" dir=in action=allow protocol=TCP localport=3000 remoteip=115.223.183.83,42.192.1.93,118.89.111.23,123.207.199.238

REM 数据库端口（仅本地）
netsh advfirewall firewall add rule name="AI24X-PostgreSQL" dir=in action=allow protocol=TCP localport=5432 remoteip=127.0.0.1
netsh advfirewall firewall add rule name="AI24X-Redis" dir=in action=allow protocol=TCP localport=6379 remoteip=127.0.0.1

REM 应用端口（仅本地）
netsh advfirewall firewall add rule name="AI24X-Backend" dir=in action=allow protocol=TCP localport=8000 remoteip=127.0.0.1

echo Firewall configuration complete!
```

## 腾讯云安全组建议

### 入站规则（安全组）
| 协议 | 端口 | 来源 | 策略 | 说明 |
|------|------|------|------|------|
| TCP | 22 | 管理IP白名单 | 允许 | SSH管理 |
| TCP | 80 | 0.0.0.0/0 | 允许 | HTTP |
| TCP | 443 | 0.0.0.0/0 | 允许 | HTTPS |
| TCP | 9090 | 管理IP白名单 | 允许 | Prometheus |
| TCP | 3000 | 管理IP白名单 | 允许 | Grafana |
| TCP | 5432 | 拒绝所有 | 拒绝 | PostgreSQL |
| TCP | 6379 | 拒绝所有 | 拒绝 | Redis |
| TCP | 8000 | 拒绝所有 | 拒绝 | 后端应用 |

### 出站规则（安全组）
| 协议 | 端口 | 目标 | 策略 | 说明 |
|------|------|------|------|------|
| 全部 | 全部 | 0.0.0.0/0 | 允许 | 允许所有出站 |

## 安全审计与监控

### 日志配置
1. **Windows事件日志**：启用安全审计
2. **Nginx访问日志**：记录所有访问
3. **应用日志**：记录业务操作
4. **数据库日志**：记录SQL查询

### 监控指标
1. **网络流量**：异常连接检测
2. **端口扫描**：检测扫描行为
3. **暴力破解**：登录失败监控
4. **资源使用**：CPU、内存、磁盘监控

### 告警规则
1. **端口扫描**：同一IP在短时间内连接多个端口
2. **暴力破解**：同一IP多次登录失败
3. **DDoS攻击**：流量异常增长
4. **服务异常**：服务进程停止

## 应急响应

### 安全事件响应流程
1. **检测**：监控系统发现异常
2. **分析**：确定事件类型和影响范围
3. **遏制**：隔离受影响系统
4. **清除**：移除恶意代码或后门
5. **恢复**：恢复服务运行
6. **总结**：记录事件并改进

### 联系人清单
| 角色 | 姓名 | 联系方式 | 职责 |
|------|------|----------|------|
| 应急负责人 | 主脑 | 飞书群 | 总体指挥 |
| 技术负责人 | 副脑04 | 飞书群 | 技术处理 |
| 安全负责人 | 副脑03 | 飞书群 | 安全分析 |

## 更新记录
- **2026-04-10**：创建初始防火墙规则文档
- **2026-04-10**：添加Windows防火墙脚本
- **2026-04-10**：添加腾讯云安全组建议

---

*注意：实际部署前请根据网络环境调整规则。定期审查和更新安全规则。*