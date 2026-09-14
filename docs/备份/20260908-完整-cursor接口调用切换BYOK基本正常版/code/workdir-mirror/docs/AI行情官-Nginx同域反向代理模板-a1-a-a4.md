# AI 行情官 Nginx 同域反向代理模板（a1 / a / a4）

目标：三台 Windows（副脑01/03/04）统一用 **同域** 跑通：

- 静态：`p/a/web`（直接由 Nginx 托管）
- API：`p/a/api/server`（FastAPI / Uvicorn 仅监听 `127.0.0.1:8001`，由 Nginx 反代）

当前口径：

- 副脑01（预演）：`a1.ai24x.com` → `127.0.0.1:8001`
- 副脑03（国内生产）：`a.ai24x.com` → `127.0.0.1:8001`
- 副脑04（国际生产）：`a4.ai24x.com` → `127.0.0.1:8001`

静态根目录（按仓库默认目录）：

- `C:/ai24x01/p/a/web`

---

## 1) 80 → 443 跳转（每个域名一段）

```nginx
server {
  listen 80;
  server_name a1.ai24x.com;
  return 301 https://$host$request_uri;
}
server {
  listen 80;
  server_name a.ai24x.com;
  return 301 https://$host$request_uri;
}
server {
  listen 80;
  server_name a4.ai24x.com;
  return 301 https://$host$request_uri;
}
```

---

## 2) HTTPS 同域静态 + API 反代（每个域名一段）

把下面 `server_name` 与证书路径替换为你的实际值即可。

```nginx
server {
  listen 443 ssl;
  server_name a1.ai24x.com;

  # ssl_certificate     <PATH_TO_CERT_PEM>;
  # ssl_certificate_key <PATH_TO_CERT_KEY>;

  root C:/ai24x01/p/a/web;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  # FastAPI
  location /api/ {
    proxy_pass http://127.0.0.1:8001/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location /docs {
    proxy_pass http://127.0.0.1:8001/docs;
  }

  location /health {
    access_log off;
    proxy_pass http://127.0.0.1:8001/health;
  }
}
```

对 `a.ai24x.com` / `a4.ai24x.com` 复制一份，改 `server_name` 和证书即可。

---

## 3) 验收（最短 3 条）

- [ ] `GET https://<domain>/health` 返回 200
- [ ] `GET https://<domain>/docs` 可打开
- [ ] 打开 `https://<domain>/demo.html` 能查询（白名单：指数 + 浪潮信息）

