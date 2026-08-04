# 事故备注：Cursor 全量 Write 改 `.env` 致密码被省略号替换

> 日期：2026-07-27  
> 机位：副脑03（Windows Server）  
> 影响：`core-api-8002` 连库失败，崩溃重启数十次后停机；手工恢复 `.env` 后恢复

---

## 现象（精简）

用 Cursor **Write 整文件覆盖** `C:\ai24x01\api\.env` 时，`DATABASE_URL` 里密码片段被写成 Unicode 省略号 `…`（例如 `ai24x_a_password_2026` → `ai24x_a_…2026`），触发 `UnicodeDecodeError` / 连库失败。

## 根因（推测，记两条）

1. **更可能**：工具链/红线对含 `password` 的敏感串做了脱敏展示或回写，把中间段换成 `…`  
2. **次可能**：编码/截断在「含 password 关键词」的长串上出错  

无论哪条，**全量 Write `.env` 都高风险**。

## 交接硬规则（够精简就这四条）

1. **禁止**用 Write / 整文件覆盖生产或预演机的 `api/.env`  
2. **只改需要的行**：用 **StrReplace / 行级 Edit**，或本机记事本 / `notepad` 手改  
3. 改完立刻自检：`DATABASE_URL=` 一行不得含 `…`（U+2026）或乱码；密码段应仍是可读 ASCII  
4. 再 `pm2 restart core-api-8002 --update-env`，确认 `pm2 describe` 不再疯狂重启  

## 恢复口令（出事时）

1. 从备份或已知正确内容恢复 `.env`（勿再让 Agent Write 全量）  
2. `pm2 restart core-api-8002 --update-env`  
3. 看 `pm2 logs core-api-8002 --lines 50` 无 UnicodeDecode / 连库错误  

## 相关入口

- 发版：`docs/联调/Token发版-Gitee与副脑04.md`（正式）；备份机说明见同目录 `…副脑03.md`  
- 手册：`docs/副脑统一操作手册.md`  
- Cursor 规则：`.cursor/rules/env-file-edit-safety.mdc`  

---

*副脑03 反馈已入库；更新交接时默认按「edit 改行、禁止 write 覆盖 .env」执行。*
