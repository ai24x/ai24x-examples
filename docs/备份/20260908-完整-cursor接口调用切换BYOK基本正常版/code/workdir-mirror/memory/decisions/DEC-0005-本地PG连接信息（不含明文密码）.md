# DEC-0005 本地 PostgreSQL 连接信息（不含明文密码）

日期：2026-04-17  
范围：主脑本机（Windows）用于 AI 行情官（`p/a/api/server`）联调

---

## 结论

- 本机已安装 PostgreSQL 15，并用于 AI 行情官的 **PG 模式**联调。
- **明文密码不入 Git**：仓库只记录连接口径与 DSN 模板；密码请保存在密码管理器/安全笔记中。

---

## 本机 PostgreSQL 信息（口径）

- **安装目录**：`C:\Program Files\PostgreSQL\15`
- **服务名**：`postgresql-x64-15`
- **监听端口**：`5432`

---

## AI 行情官使用的库与账号

- **超级用户**：`postgres`
- **应用用户**：`ai24x_a`
- **应用数据库**：`ai24x_a_pre`

---

## DSN 模板（两种写法）

### A) URL（注意密码需要 URL 编码）

```text
postgresql://ai24x_a:<PASSWORD_URLENCODED>@127.0.0.1:5432/ai24x_a_pre
```

示例：若密码包含 `@`，需写成 `%40`。

### B) 参数式（推荐给脚本/程序，避免 URL 编码问题）

```text
host=127.0.0.1 port=5432 dbname=ai24x_a_pre user=ai24x_a password=<PASSWORD>
```

---

## 代码侧配置位置

- AI 行情官后端环境变量文件：`p/a/api/server/.env`
  - `AI24X_DB_KIND=pgsql`
  - `AI24X_DATABASE_URL=...`

---

## 验收命令（连通性实锤）

### 1) 端口监听

```powershell
netstat -ano | findstr :5432
```

### 2) SQL 连接（psql）

```powershell
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -h 127.0.0.1 -p 5432 -U ai24x_a -d ai24x_a_pre -c "select 1;"
```

