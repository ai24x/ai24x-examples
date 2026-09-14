# 副脑03 · 诊断：PayPal「商户凭证无效」

> 发令：2026-07-29  
> 现象：本机正常，生产下单返回「PayPal 商户凭证无效，请稍后重试或联系客服。」  
> 代码含义：调 PayPal OAuth 失败（常见 `invalid_client`）→ **Client ID/Secret 与 MODE 不匹配，或进程未读到正确 env**。  
> **禁止**回传完整 Secret；禁止整文件覆盖 `.env`。

## 最常见原因（按概率）

1. `PAYPAL_MODE=live` 但仍填 **Sandbox** 的 ID/Secret（或反过来）  
2. Live ID/Secret 拷错、多空格、带引号、被省略号 `…` 截断  
3. 改了 `.env` 但 **未重启** `AI24X-core`，或 NSSM 里另写了旧的 `PAYPAL_*` 覆盖了文件  
4. Webhook ID 对错不影响本句错误（本句是 **下单前 OAuth**）

---

## 诊断（PowerShell · 可给 OpenClaw）

```powershell
Set-Location C:\ai24x01   # 现网路径为准

# 1) 脱敏看 .env（不要贴完整密钥）
Select-String -Path api\.env -Pattern '^PAYPAL_MODE=|^PAYPAL_WEBHOOK_ID=|^TOKEN_PAYPAL_|^TOKEN_PAY_MOCK'
Select-String -Path api\.env -Pattern '^PAYPAL_CLIENT_ID=|^PAYPAL_CLIENT_SECRET=' | ForEach-Object {
  $k,$v = $_.Line.Split('=',2)
  $v = $v.Trim().Trim('"').Trim("'")
  $tail = if ($v.Length -ge 4) { $v.Substring($v.Length-4) } else { $v }
  "$k set=$([bool]$v) len=$($v.Length) tail=***$tail quote=$($_.Line -match '\"') ellipsis=$($v.Contains([char]0x2026))"
}

# 2) 进程实际读到的（环回 pay/status）
curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
curl.exe -sS https://api.ai24x.com/v1/billing/pay/status
# 记下：paypal.mode 是 live 还是 sandbox；ready/ui_ready

# 3) NSSM 是否另挂了环境变量覆盖 .env
nssm get AI24X-core AppEnvironmentExtra 2>$null
nssm get AI24X-core AppDirectory 2>$null
# 若 Extra 里有旧 PAYPAL_*，以 Extra 为准或删掉 Extra 中冲突项，只保留 .env

# 4) 本机对「当前 MODE」做一次 OAuth 探针（不打印 token）
python -c @"
import os, base64, urllib.request
from pathlib import Path
# 简易读 .env
env = {}
for line in Path(r'api/.env').read_text(encoding='utf-8', errors='replace').splitlines():
    s=line.strip()
    if not s or s.startswith('#') or '=' not in s: continue
    k,v=s.split('=',1); env[k.strip()]=v.strip().strip('\"').strip(\"'\")
mode=(env.get('PAYPAL_MODE') or 'sandbox').lower()
base='https://api-m.paypal.com' if mode in ('live','production','prod') else 'https://api-m.sandbox.paypal.com'
cid=env.get('PAYPAL_CLIENT_ID',''); sec=env.get('PAYPAL_CLIENT_SECRET','')
print('mode', mode, 'base', base, 'id_len', len(cid), 'sec_len', len(sec))
req=urllib.request.Request(base+'/v1/oauth2/token', data=b'grant_type=client_credentials', method='POST')
tok=base64.b64encode(f'{cid}:{sec}'.encode()).decode()
req.add_header('Authorization','Basic '+tok)
req.add_header('Content-Type','application/x-www-form-urlencoded')
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print('oauth_http', r.status, 'ok')
except Exception as e:
    body=getattr(e,'read',lambda:b'')()
    if callable(body): body=body()
    print('oauth_fail', type(e).__name__, str(e)[:200])
    print('body', (body or b'')[:300].decode('utf-8','replace'))
"@
```

### 如何解读探针

| 结果 | 处理 |
|------|------|
| `oauth_http 200 ok` 但网站仍报错 | 服务未加载新 env → `Restart-Service AI24X-core`；查 NSSM Extra |
| `body` 含 `invalid_client` | ID/Secret 错或 **MODE 与应用环境不一致** → 到 PayPal 开发者后台核对 **Live** 应用重新复制 |
| `mode live` + 本机 Sandbox 那套 len/tail | 立刻换成 Live 凭证 |

**Sandbox 与 Live 的 Client ID 完全不同**；本机测通 ≠ 生产可直接拷 Sandbox 密钥再设 `live`。

---

## 修复口径（行级）

```env
PAYPAL_MODE=live
PAYPAL_CLIENT_ID=<PayPal 后台 Live 应用的 Client ID>
PAYPAL_CLIENT_SECRET=<同一 Live 应用的 Secret>
PAYPAL_WEBHOOK_ID=15d01cd5-f9e1-4309-a09d-f9dc486e5634
TOKEN_PAYPAL_RETURN_URL=https://www.ai24x.com/console.html
TOKEN_PAYPAL_CANCEL_URL=https://www.ai24x.com/console.html
TOKEN_PAY_MOCK_ENABLED=false
```

```powershell
Restart-Service AI24X-core
Start-Sleep -Seconds 3
curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status
# 再跑上面 python OAuth 探针，须 oauth_http 200
```

若暂时没有可靠 Live 凭证：改回 `PAYPAL_MODE=sandbox` + Sandbox ID/Secret，生产先继续 Sandbox，回报主脑。

## 回报主脑（脱敏）

- `pay/status` 的 `mode` / ready  
- OAuth：`200` 还是 `invalid_client`  
- ID/Secret 的 **len + tail 末4**（不要完整值）  
- NSSM `AppEnvironmentExtra` 是否含 `PAYPAL_`  
