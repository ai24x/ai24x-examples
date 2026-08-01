# 副脑04 · 更新指令（首访默认英文 + 防闪中文）

> 发令：2026-08-02  
> 范围：**仅静态站 `web/`**（Nginx 静态；**不必**重启 `AI24X-core`）  
> **禁止**整文件覆盖 `api/.env`；本包**无需**改 `.env`  
> 远端：`git pull origin master`（或 `gitee master`）

## 本包要解决什么

| 项 | 说明 |
|----|------|
| 首访语言 | 无 `localStorage` / 无 `?lang=` 时 **固定英文**（不再跟浏览器 `zh` 自动切中文） |
| 手动切换 | 右上角语言下拉仍可切中文等；选过写入 `ai24x_lang` 后全站记住 |
| 防闪中文 | `i18n-boot.js` + `html.i18n-pending`：英文会话下进页先藏正文，`apply` 后再露 |
| 自测 | `?lang=zh` / `?lang=en` 仍可强制并写入 |

## 主要文件

- `web/js/i18n-boot.js`（新，`?v=20260802g`）
- `web/js/i18n.js` / `web/js/app.js` / `web/js/shell.js`
- `web/css/base.css`（`?v=20260802g`）
- 各页 HTML：`head` 内引入 boot；资源戳 `20260802g`

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望含：i18n / default English / FOUC 或「首访默认英文」

# 本包无需改 .env；勿动 DATABASE_URL
# 静态站：确认 Nginx/站点根已指向本仓 web（或你们现网同步方式）
# 不必 Restart-Service AI24X-core

# 抽查静态资源是否已是新戳
curl.exe -sS -o NUL -w "index=%{http_code}`n" https://www.ai24x.com/index.html
curl.exe -sS -o NUL -w "boot=%{http_code}`n" "https://www.ai24x.com/js/i18n-boot.js?v=20260802g"
curl.exe -sS -o NUL -w "i18n=%{http_code}`n" "https://www.ai24x.com/js/i18n.js?v=20260802g"
curl.exe -sS https://www.ai24x.com/index.html | Select-String -Pattern "i18n-boot\.js\?v=20260802g"
```

---

## 验收（回报主脑）

浏览器 **无痕窗口**（或先清掉 Local Storage 的 `ai24x_lang`），**Ctrl+F5**：

1. https://www.ai24x.com/ — 系统语言即使是中文，首屏也应是 **英文**  
2. 右上角切 **中文** → 全文中文；刷新仍中文  
3. 再清 `ai24x_lang` 或无痕重开 → 回到英文  
4. 英文下点菜单（价格 / 名模等）：**不应**再明显「闪一下中文再变英文」  
5. （可选）`https://www.ai24x.com/?lang=zh` → 中文并记住

## 不要做

- 不要为了本包去 `Restart-Service AI24X-core`（无 api 变更）
- 不要 `pm2 restart` core
- 不要 Write 整份 `.env`
- 不要动 `DATABASE_URL`

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
# 回退到本包提交之前的已知好提交后，静态会随 git 回退
# 例：git checkout <上一好提交> -- web/
# 或整仓 reset 到上一好提交（需主脑确认）
```
