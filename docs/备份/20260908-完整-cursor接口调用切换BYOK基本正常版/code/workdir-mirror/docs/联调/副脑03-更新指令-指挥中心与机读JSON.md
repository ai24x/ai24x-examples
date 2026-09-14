# 副脑03 · 更新指令（指挥中心三模板 + 机读 JSON + OpenClaw 记忆卡）

> 发令时间：2026-07-27  
> 目标：拉最新 `master`，让公网可访问指挥中心页面与机读数据；**不动** a1 支付 / `.env` / 行情官履约。  
> 主脑已推 Gitee；你只需 pull + 确认静态路径生效。

## 本次上线目的

1. **人读**：`https://www.ai24x.com/ai24x.html`（内部作战沙盘，三套模板可切换；**勿**设为 www 默认首页）  
2. **机读**：`https://www.ai24x.com/ops/ai24x-command.json`（OpenClaw / 各副脑拉岗位与链接；**不含密钥**）  
3. 文档：`docs/联调/OpenClaw-认人认岗记忆卡.md`、`docs/规划/主脑副脑岗位与国际Token供给-1.0.md`（仓库内，不必对公网暴露）

## 改动范围（与你相关的静态）

| 路径 | 说明 |
|------|------|
| `web/ai24x.html` | 指挥中心 v3.9 · 墨金 / 主站蓝白 / 智能体矩阵 |
| `web/ops/ai24x-command.json` | 副脑协同机读数据 |
| `docs/联调/OpenClaw-认人认岗记忆卡.md` | 认人认岗粘贴卡（存档） |
| `docs/规划/主脑副脑岗位与国际Token供给-1.0.md` | 岗位唯一口径 |

**不要**：改 `api/.env`、改 a1 回调、`pm2 delete` 行情官、动微信/支付宝商户配置。  
**本次若仅静态**：可不重启 `core-api-8002` / `a-api-8001`。

---

## 执行步骤（PowerShell，仓库根目录）

```powershell
cd <你的仓库根目录>

# 1) 只拉 origin/master（禁止换分支；有本地脏改先 stash 或确认无关）
git fetch origin
git checkout master
git pull origin master

# 2) 确认关键文件已在当前 HEAD
git rev-parse --short HEAD
git log -1 --oneline
Test-Path web/ai24x.html
Test-Path web/ops/ai24x-command.json
Select-String -Path web/ai24x.html -Pattern "v3.9.0" -SimpleMatch
Select-String -Path web/ops/ai24x-command.json -Pattern "AI24X国际token" -SimpleMatch

# 3) 确认 www 静态根目录指向仓库 web/（或你现有同步目录已含上述文件）
#    若 www 是拷贝发布：把 web/ai24x.html 与 web/ops/ 整目录同步到静态根

# 4) 一般纯静态无需重启；若有独立静态进程可按需：
# pm2 restart <你的主站静态进程名>
pm2 list
```

---

## 验收（更新后回复主脑）

1. 浏览器打开（可无痕 / Ctrl+F5）：  
   - `https://www.ai24x.com/ai24x.html` → 能看到顶部「模板风格」、版本 **v3.9.0**  
   - `https://www.ai24x.com/ops/ai24x-command.json` → **HTTP 200**，JSON 可解析，含 `brains` / `feishu`  
2. 回报：  
   - `git rev-parse --short HEAD`  
   - 上述两个 URL 是否 200  
   - （可选）`curl -sI https://www.ai24x.com/ops/ai24x-command.json | Select-String HTTP`

## 回滚（若异常）

```powershell
# 仅回退这两处静态（提交号以你 pull 前的 HEAD 为准，或问主脑）
git checkout HEAD~1 -- web/ai24x.html web/ops/ai24x-command.json
# 若用拷贝发布，把旧文件同步回静态根即可
```

## 注意

- 指挥中心页 **noindex**，勿挂进主导航、勿当 `index`。  
- JSON **无门禁**但无密钥；仍勿把生产密码写进任何公开文件。  
- 禁止整文件 Write 生产 `.env`。  
- 各副脑认人认岗：用仓库内 `docs/联调/OpenClaw-认人认岗记忆卡.md`，记忆源指向上述 JSON URL。
