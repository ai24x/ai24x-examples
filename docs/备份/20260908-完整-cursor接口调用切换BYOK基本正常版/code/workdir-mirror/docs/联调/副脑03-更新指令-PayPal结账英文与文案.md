# 副脑03 · PayPal 结账体验优化（英文 locale + 文案）

> 发令：2026-07-29  
> 内容：下单默认 `locale=en-US`、`landing_page=BILLING`、`NO_SHIPPING`；定价/说明页提示通常需登录 PayPal。  
> **不改** Client ID/Secret。Guest 中国商户限制无法单靠代码彻底解决。  
> 进程：NSSM `AI24X-core`（勿 pm2）。

## 执行

```powershell
Set-Location C:\ai24x01
git pull origin master
git log -1 --oneline

# 可选显式（代码已有默认，可不写）
# TOKEN_PAYPAL_LOCALE=en-US
# TOKEN_PAYPAL_LANDING_PAGE=BILLING
# notepad api\.env

Restart-Service AI24X-core
# 静态若由 Nginx 直出 web/，pull 后无需重启静态进程；硬刷新浏览器即可

curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
# 期望 paypal.locale=en-US，landing_page=BILLING
```

## 验收

1. 控制台再点 PayPal：结账页宜为英文（已登录中文买家账号仍可能中文）  
2. 定价页国际说明含「通常需登录 PayPal」  
3. 回报：`pay/status` 的 locale / landing_page  

## 回滚

```env
TOKEN_PAYPAL_LOCALE=zh-CN
TOKEN_PAYPAL_LANDING_PAGE=NO_PREFERENCE
```
然后 `Restart-Service AI24X-core`。
