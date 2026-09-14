# 副脑03 · 更新指令（帮助中心 FAQ 间距）

> 发令：2026-08-01  
> **静态页更新**：`web/help.html` + `web/css/base.css`  
> **通常不必**重启 `AI24X-core`（无 API 变更）  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull gitee master`（若只有 origin：`git pull origin master`）

## 本包内容

| 项 | 说明 |
|----|------|
| 帮助中心 | FAQ 卡片纵向间距加大；「常见问题 / 还是不行」区块上边距加大 |
| CSS | `body[data-page=help]` 下 `.help-stack` / `.help-block-gap` |

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull gitee master
# 若 pull 失败：git pull origin master
git log -1 --oneline
# 期望含：help FAQ spacing / help.html

# 静态资源：无需 Restart-Service（若 CDN/Nginx 强缓存，用户 Ctrl+F5 即可）
# 可选自检：
curl.exe -sS -o NUL -w "help=%{http_code}`n" https://www.ai24x.com/help.html
curl.exe -sS -o NUL -w "css=%{http_code}`n" "https://www.ai24x.com/css/base.css?v=20260801d"
```

## 验收（回报主脑）

1. `git log -1 --oneline` = 本包提交  
2. https://www.ai24x.com/help.html **Ctrl+F5**：FAQ 卡片间距明显大于旧版（不再贴在一起）  
3. `help` / `css` HTTP **200**  

## 回滚

```powershell
Set-Location C:\ai24x01
git revert <本包提交hash> --no-edit
# 静态页随 git 回退即可；无需重启服务
```

## 不要做

- 不要为了本包去改 `.env`  
- 不要 `pm2 restart` / 不要无故 `Restart-Service AI24X-core`（本包不需要）  
