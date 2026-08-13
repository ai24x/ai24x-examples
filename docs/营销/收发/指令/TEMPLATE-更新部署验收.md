# 【指令模板】更新部署验收（主通道 v2 · 司令直连 04 · PowerShell 优先）

> 三通道：
> ① 主通道 v2（老板说「04更新」后，最快）：司令 提交→双推 gitee→写指令 md→跑 `scripts\deploy04.ps1 <指令.md>`（scp 到 04 + ssh 驱动 04 的 openclaw，--timeout 600）→ 04 完成部署+验收+飞书群回执。**跳过主脑中转**，主脑不参与部署（只留记忆/飞书）。
> ② 备用（主脑在线、想留痕）：司令用 `openclaw agent --agent main --message-file <指令.md> --json --timeout 600`（勿用 300，链路长易超时 abort）。
> ③ 备用（主脑失联/老板想手动）：司令给「复制即发」PowerShell，老板私信副脑04，她跑完私信回执清单。

## 关键环境事实（已核实 2026-08-08）
- 04 生产仓库：C:\ai24x01（AI24X-core 实跑，nssm AppDirectory=C:\ai24x01\api）
- 04 生产 core health 端口 = **8002**（本地开发才是 8000）→ 校验脚本用 8002
- 04 SSH：Administrator@43.160.246.30（本机密钥免密，直连 3-6s 秒通）
- 双远端：gitee=ai24x/ai24x01.git、origin=ai24x/ai24x-website.git（都要推，04 从 gitee 拉）

## 副脑04 执行脚本（整段复制运行）
```powershell
# === AI24X 更新部署验收 · 目标 <COMMIT> ===
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"           # 04 生产仓库根目录
$SRV  = "AI24X-core"
$EXP  = "<COMMIT-12位或前缀>"   # 期望 HEAD（每次更新只改这一行；比较统一前缀匹配）

Set-Location $REPO
git pull
$HEAD = (git rev-parse --short=12 HEAD).Trim()
"HEAD=$HEAD"
if ($HEAD -notlike "$EXP*") { Write-Host "!! HEAD 不匹配，期望前缀 $EXP 实际 $HEAD" -ForegroundColor Red; exit 1 }
Restart-Service $SRV -Force
$ok = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 5
    try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -TimeoutSec 10; $ok = $true; break } catch {}
}
if (-not $ok) { Write-Host "!! /health 未就绪" -ForegroundColor Red; exit 1 }
"health=$($h.status) commit=$($h.commit)"
if ($h.commit -notlike "$EXP*") { Write-Host "!! 服务未生效，commit=$($h.commit)" -ForegroundColor Red; exit 1 }
Write-Host "=== 部署成功 ✅ ===" -ForegroundColor Green
```

## 完成后群回执（固定步骤，主通道必做）
- 用 04 应用发指挥部群：
  `python api\feishu_notify.py --config <openclaw.json> --group "【AI24X 部署回执】<COMMIT> 部署成功：HEAD=<COMMIT>、health 200、<关键结论>，可公网测试 https://www.ai24x.com" --at`
- 把 ✅ 已完成项 / ⚠️ 问题项 清单一并发群里（若雷总要私信，再补发私信一份）。

## 回执时机规则（2026-08-08 老板定）
- 验收全部 PASS → 立即发指挥部群回执（老板收 ✅/⚠️ 清单）。
- 有任一问题项/失败 → 先回传司令（openclaw 回传即可），**不发群不惊动老板**；司令处理后给下一步（修复/回滚/放行），成功后再由司令确认发群回执。
- P0/生产不可用例外：司令边处理边第一时间同步老板，不隐瞒。

## 回执格式（统一）
- ✅ 已完成项：HEAD / health / commit 校验 / 群回执
- ⚠️ 问题项：逐条列出（无则写「无」）

## 回滚预案
- `git revert <COMMIT>` + 重启 core（或恢复对应 .bak + 重启）

## 排查备忘（2026-08-08 事故复盘）
- 现象：主通道 `openclaw agent --agent main --timeout 300` 整 run 在 300s 被 abort，看似失败。
- 根因①：主脑中转这跳是纯 LLM 中转（写文件→scp→ssh 驱动 04），scp 遇瞬时网络挂起即拖死整条链；
- 根因②：--timeout 300 太紧，链路一卡就 abort；实际主脑 abort 前已把任务传给 04 并驱动，04 侧继续执行完成，只是结果回不来 → 误判失败。
- 教训：部署这类确定性工作别走多层 LLM 中转；直连 04（deploy04.ps1）为默认；主脑中转仅作备用且 --timeout 提到 600。
- 短哈希校验统一用**前缀匹配**：`$EXP` 填 12 位或 7 位前缀，比较一律 `-notlike "$EXP*"`（`-ne` 严格比较 7 位 vs 12 位必误报；2026-08-13 03/04 两处现场踩坑后定稿）。
## 公网验收（部署后必做 · 2026-08-09 司令补充）
1. 04 本机 8002 health OK 后，必须再验公网：
   - `https://api.ai24x.com/health` → commit 字段必须 = 期望 HEAD
   - `https://www.ai24x.com/<本次改动页面>` → 含关键新标记（如注册验证码：reg-captcha-group / locales.js?v=20260809b）
2. 回执中必须附公网证据（health commit + 页面标记），雷总一眼确认「已更新上去」。

## 验收清单纪律（2026-08-09 补充）
- `scripts_token_smoke.py` 是本地专用（BASE=127.0.0.1:8000），生产验收清单不得包含该项；生产侧以「公网验收 + 接口实测」为准（曾因放 smoke 进生产清单导致误报 FAIL + 多一轮往返）。
- 拉取前先 `git ls-remote origin master` 连续两次一致再 `git pull`，避免拉取途中远端引用变动（曾导致 shallow clone 兜底混乱）。
- 改密码/凭证后：04 的 gitee 走 credential store（勿把 token 内嵌 URL，失效会导致 git 挂起弹登录）。

## 副脑03（AI行情官 a1）环境差异（2026-08-10 定，老板提醒）
- 03 主机：Administrator@123.207.199.238 · 仓库 C:\ai24x01 · 服务 AI24X-a1-api（NSSM，端口 **8001**，域名 a.ai24x.com）· 库 ai24x_a_cn（PG 127.0.0.1:5432）。
- ⚠️ **03 无 D 盘**：pg_dump 备份路径写 `C:\backup\ai24x_a\`（勿写 D:\backup，实测 03 落 C 盘）。
- ⚠️ **a1 /health 无 commit 字段**：验收以「进程新建时间 + 行为验收」确认，勿要求 commit 字段。
- 派发：`powershell -File scripts\deploy03.ps1 <指令.md>`（与 04 同构，仅主机/服务/端口不同）。

## 短哈希纪律（2026-08-10 补充）
- 模板脚本用 `git rev-parse --short=12`，/health 的 commit 也是 12 位：指令中 `$EXP` 必须写 **12 位短哈希**（或校验用前缀匹配），写 7 位会导致 HEAD 比较失败（实测 5f43117 vs 5f4311725dbe，04 已改 --short=7 + 前缀匹配重跑通过）。
