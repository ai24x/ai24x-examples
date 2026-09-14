# Token 发版：Gitee 与副脑03（已降级 · 仅备份说明）

> **2026-08-04 起作废为「正式生产」口径。**  
> **正式国际 Token / www / api 生产 = 副脑04** → 请改用：  
> **[`Token发版-Gitee与副脑04.md`](./Token发版-Gitee与副脑04.md)**

## 现口径

| 角色 | 职责 |
|------|------|
| **副脑04** | `www.ai24x.com` + `api.ai24x.com` Token 聚合 **正式生产** |
| **副脑03** | `a.ai24x.com` 行情官生产；Token 站仅 **冷备份/灾备**（主脑明示才同步） |

下文保留历史步骤供灾备参考，**日常发版勿默认执行**。

---

# （历史）本机推 Gitee → 副脑03 更新（含新表）

## 原则
- **勿改** a1 支付回调 / `p/a1/**` 履约逻辑
- **勿提交** `api/.env`、密钥、证书 PEM
- 生产 API 进程（历史）：**`core-api-8002`** / NSSM `AI24X-core`
- `.env` 红线：禁止 Write 整文件覆盖 → `docs/联调/事故-Cursor写env密码被省略号替换.md`

## 备份机同步（仅主脑下令时）

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
# 按 03 机实际进程名重启；勿改公网 DNS
Restart-Service AI24X-core
# 或：pm2 restart core-api-8002 --update-env
```

a1 发版仍用：`docs/副脑03-生产环境更新指南-a1…`
