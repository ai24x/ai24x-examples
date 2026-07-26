# 副脑03 · 紧急：登录已失效（本站重签 JWT）

> 提交说明：登录/注册等 identity 成功后，用 **a1 自己的 `AI24X_JWT_SECRET`** 重签 token，再给前端。  
> 这样即使 core `SECRET_KEY` 与 a1 JWT 不一致，`/api/me` 也不会再 Invalid token。

```powershell
Set-Location C:\ai24x01
git pull origin master
git log -1 --oneline -- p/a1/api/server/app/main.py
# 期望近期提交含「重签」或 _session_from_identity_payload

pm2 restart a-api-8001 --update-env
pm2 save

# 验证文件里有重签函数
Select-String -Path p\a1\api\server\app\main.py -Pattern "_session_from_identity_payload" | Select-Object -First 1
```

验收：无痕窗口打开 `https://a.ai24x.com/` → 登录 → **已登录**，不应再「登录已失效」。

说明：仍建议日后把 `SECRET_KEY` 与 `AI24X_JWT_SECRET` 对齐；本修复不依赖立即对齐即可登录。
