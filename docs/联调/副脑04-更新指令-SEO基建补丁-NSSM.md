# 副脑04 · 更新指令（SEO 基建补丁 · 静态站）

> 发令：2026-08-02 · 目标提交 \976207f\  
> 范围：**仅静态 `web/`**（不必重启 `AI24X-core`）  
> **禁止**整文件覆盖 `api/.env`  
> 本窗不做：裸域→www 的 Nginx 301、Search Console 开户（仍归 04 运营）

## 本包内容

| 项 | 说明 |
|----|------|
| 首页 | canonical、`og:title`/`og:image`/`og:description`、OpenAI-compatible + `/v1/chat/completions` |
| 资源 | `web/img/og-share.png`（1200×630） |
| sitemap | 公开页补全 + `lastmod`；URL 一律 `https://www.ai24x.com/...` |
| robots | 与 sitemap 交叉：console / token-admin 等 Disallow，不进 sitemap |
| 投流对齐 | pricing 无 localhost；广告页默认英文；console placeholder=`api.ai24x.com`（此前已合） |

## 执行

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline
# 期望：976207f（SEO P0）或更新

# 不必 Restart-Service AI24X-core

curl.exe -sS -o NUL -w "sitemap=%{http_code}`n" https://www.ai24x.com/sitemap.xml
curl.exe -sS -o NUL -w "og=%{http_code}`n" https://www.ai24x.com/img/og-share.png
curl.exe -sS https://www.ai24x.com/index.html | Select-String -Pattern "canonical|og:image|chat/completions"
curl.exe -sS https://www.ai24x.com/pricing.html | Select-String -Pattern "127\.0\.0\.1|localhost"
# 期望：pricing 无匹配

# Search Console：提交 https://www.ai24x.com/sitemap.xml（04 运营）
```

## 验收回报主脑

1. sitemap / og-share.png → **200**  
2. 首页含 canonical + og:image + completions  
3. pricing 无 127.0.0.1  
4. GSC 已提交 sitemap（若账号就绪）
