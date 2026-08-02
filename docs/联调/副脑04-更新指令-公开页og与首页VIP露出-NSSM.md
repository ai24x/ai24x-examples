# 副脑04 · 更新指令（公开页 og:image + 首页 VIP 露出 · 静态站）

> 发令：2026-08-02  
> 范围：**仅静态 `web/`**（不必重启 `AI24X-core`）  
> **禁止**整文件覆盖 `api/.env`  
> 承接：`50acf3b` SEO 基建验收后的 P1（次要页缺 og:image）+ 首页次要文案补 GPT/Claude

## 本包内容

| 项 | 说明 |
|----|------|
| 公开页 OG | pricing / product / models/* / guides/* / docs / help / refer / login / register / privacy / terms 等：统一 `og:image`=`https://www.ai24x.com/img/og-share.png` + og:title/url/twitter |
| 首页文案 | hero 主名单仍只列中国强模；tag4 / 三步开始 / 名模卡片次要露出 VIP 可点名 GPT / Claude / Gemini |
| 资源 | 仍用既有 `web/img/og-share.png`（无需新图） |

## 执行

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline
# 期望：含「公开页 og」或「VIP 露出」说明的提交（拉码后 HEAD）

# 不必 Restart-Service AI24X-core

curl.exe -sS https://www.ai24x.com/pricing.html | Select-String -Pattern "og:image"
curl.exe -sS https://www.ai24x.com/models/index.html | Select-String -Pattern "og:image"
curl.exe -sS https://www.ai24x.com/guides/index.html | Select-String -Pattern "og:image"
curl.exe -sS https://www.ai24x.com/index.html | Select-String -Pattern "VIP can name GPT|GPT / Claude"
# 期望：pricing/models/guides 均含 og:image；首页含 VIP + GPT/Claude 露出
```

## 验收回报主脑

1. pricing / models / guides 均含 `og:image` → `og-share.png`  
2. 首页可见 VIP 可点名 GPT / Claude（tag 或三步文案）  
3. **不必**重启 core；回报拉码后 `git log -1 --oneline`
