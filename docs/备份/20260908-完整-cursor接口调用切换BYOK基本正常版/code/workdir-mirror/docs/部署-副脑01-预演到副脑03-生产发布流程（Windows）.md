## 部署流程：副脑01 预演 → 副脑03 国内生产 →（主站完成后）副脑04 国际生产（Windows / 统一路径 C:\ai24x01）

适用目标：

- **副脑01**：预演发布（验证“拉取代码 + 依赖 + 迁移 + 重启 + 验收”闭环）
- **副脑03**：国内生产发布（对外公网服务，只部署“已在副脑01通过”的版本）
- **副脑04**：国际生产发布（主站/域名体系就绪后再启用，与副脑03同流程）

约定：

- **主脑本地工作区**：`E:\AI24X\ai24x-website\ai24x01`
- **副脑01/03/04 部署目录**：统一 `C:\ai24x01`
- 配置（`.env` 等）**不入库**，放在机器本地
- 生产只部署 **prod tag**，预演只部署 **rc tag**

---

## 0) 一次性准备（三台机器都要做：副脑01/03/04）

### 0.1 安装/确认工具

- Git
- Python（与主脑一致）
- Node（如你有前端构建需求；纯静态可不装）
- PM2（建议全局安装）

### 0.2 首次克隆（副脑01 / 副脑03 / 副脑04 各做一次）

在 PowerShell 执行：

```powershell
cd C:\
git clone <你的Gitee仓库地址> ai24x01
cd C:\ai24x01
```

### 0.3 环境文件（不入库）

建议在三台机器分别准备：

- `C:\ai24x01\api\.env`（主站 API，如使用）
- `C:\ai24x01\p\a\api\server\.env`（AI 行情官 API，如使用）

你仓库里保留 `.env.example` 作为模板，真实 `.env` 只在服务器本地。

---

## 1) 版本策略（主脑侧发布动作）

### 1.1 预演版本（rc tag）

当你认为“可以上预演环境”时，在主脑打 tag：

- `rc-YYYYMMDD-N`（例：`rc-20260417-1`）

### 1.2 生产版本（prod tag）

当 **副脑01 预演验证通过** 后，再在主脑打生产 tag：

- `prod-YYYYMMDD-N`（例：`prod-20260417-1`）

**强规则**：prod tag 必须指向“同一个通过的 commit”（不能生产再改代码）。

---

## 2) 副脑01：预演发布步骤（部署 rc tag）

在副脑01 PowerShell 执行（建议整段复制）：

```powershell
Set-Location C:\ai24x01

# 1) 拉取最新 tag
git fetch --tags

# 2) 切到预演版本（替换为实际 rc tag）
git checkout rc-20260417-1

# 3) 后端依赖（按你实际服务决定跑哪一个）
# 主站 api（如启用）
# python -m venv .venv
# .\.venv\Scripts\Activate.ps1
# pip install -r api\requirements.txt

# AI 行情官 API（如启用）
# python -m venv p\a\api\server\.venv
# p\a\api\server\.venv\Scripts\Activate.ps1
# pip install -r p\a\api\server\requirements.txt

# 4) 数据库迁移（如果你已经有迁移脚本，就在这里执行）
# 说明：预演环境也必须跑迁移，用来验证迁移可重复、可成功

# 5) PM2 重启/热更新（按你实际 PM2 配置文件）
# pm2 start ecosystem.local.js --only <process-name>
# pm2 reload <process-name>
# pm2 save
```

### 2.1 预演验收清单（必须跑）

最小验收（建议 5 分钟内完成）：

- 页面：`/index.html`、`/account.html`、`/demo.html` 能打开
- 查询：常用标的能查询，`day/week/month` 切换正常
- 周线：左侧时间窗口合理（约两年），MA 不缺段
- 快速点击：不应频繁报错（偶发失败可接受，但不能不可用）

预演通过后，记录：

- rc tag
- 通过时间
- 是否包含数据库变更（有/无）

---

## 3) 副脑03：国内生产发布步骤（部署 prod tag）

在副脑03 PowerShell 执行（建议整段复制）：

```powershell
Set-Location C:\ai24x01

# 0) 发布前备份（至少：数据库 + .env + Nginx/PM2 配置）
# 先按 docs/备份-日常方案.md 的思路做最小快照

# 1) 拉取最新 tag
git fetch --tags

# 2) 切到生产版本（替换为实际 prod tag）
git checkout prod-20260417-1

# 3) 更新依赖（同预演）

# 4) 跑数据库迁移（生产必须先备份再迁移）

# 5) PM2 reload（优先 reload，必要时 restart）
# pm2 reload <process-name>
# pm2 save
```

### 3.1 生产验收（更短、更硬）

- 首页/行情页能打开
- 查询一个常用标的成功
- 观察 1～2 分钟日志无异常尖峰（5xx/traceback）

---

## 4) 回滚（必须提前准备）

### 4.1 代码回滚（最快）

```powershell
Set-Location C:\ai24x01
git fetch --tags
git checkout prod-上一个版本tag
pm2 reload <process-name>
```

### 4.2 数据回滚（兜底）

- 如果迁移不可逆：用发布前的数据库备份恢复
- 建议后续把迁移设计成“向前兼容”（先加字段/表，再切代码；避免 hard break）

---

## 5) 后续升级为“一键”（下一步）

当本流程跑顺 2～3 次后，再做两件事：

- 把第 2/3 节命令封装成：
  - `scripts\deploy_rc.ps1`（副脑01）
  - `scripts\deploy_prod_cn.ps1`（副脑03）
  - `scripts\deploy_prod_intl.ps1`（副脑04）
- 进一步升级为：
  - 主脑打 tag → Gitee webhook → 副脑01 自动预演
  - 副脑01 通过后 → 主脑打 prod tag → 副脑03 自动生产
  - 副脑03 稳定后 →（主站/域名体系就绪）副脑04 自动国际生产

---

## 6) 副脑04：国际生产发布（与副脑03相同，后续启用）

副脑04 执行步骤与副脑03一致：

- 发布前先备份（PG + 配置）
- `git fetch --tags` → `git checkout prod-...`
- 依赖（如有变更再装）
- 迁移（如有，生产先备份再迁移）
- `pm2 reload`
- 最小验收（首页/行情页 + 常用标的查询 + 观察日志）

