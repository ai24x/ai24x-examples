## 数据库迁移（PostgreSQL）目录规范

目标：让“新增字段/新增表/新增索引”变成**可追溯、可重复、可回滚**的固定流程，适配副脑01预演与副脑03生产发布。

### 约定
- 迁移文件放在本目录：`db/migrations/`
- 文件命名格式：
  - `YYYYMMDD-HHMMSS-<short>.sql`
  - 例：`20260501-090000-add-admin-config.sql`
- 每个迁移文件必须是 **幂等**（可重复执行不报错）
  - `CREATE TABLE IF NOT EXISTS ...`
  - `CREATE INDEX IF NOT EXISTS ...`
  - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`（PostgreSQL 9.6+ 可用；若版本不支持，需用 DO $$ ... 判断）

### 推荐迁移策略（丝滑升级）
采用 Expand → Deploy → Backfill → Switch →（可选 Contract）：
- **Expand**：只加字段/表/索引（向前兼容）
- **Deploy**：发布“兼容新旧结构”的代码
- **Backfill**：必要时补齐历史数据
- **Switch**：用 `admin_config`/feature flag 开启新逻辑
- **Contract**：最后再删除旧字段/旧逻辑（可推迟）

### 执行与记录
建议在数据库里维护 `schema_migrations` 表记录已执行迁移（后续由脚本自动维护）。

