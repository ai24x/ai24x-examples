# 副脑03 · 诊断修复：a.ai24x.com「登录已失效」

> 发令：2026-07-27  
> 现象：本机 `127.0.0.1:18001` 登录正常；公网 `https://a.ai24x.com/…` 登录后提示 **「登录已失效，请重新登录。」**  
> 与邀请码 `?i=…` **无关**（该文案来自 `/api/me` 返回 401 后清 token）。

## 根因（高概率）

登录走主站身份 API，JWT 用 **core 的 `SECRET_KEY`** 签发；  
行情官 `/api/me` 用 **a1 的 `AI24X_JWT_SECRET`** 验签。  

**两把密钥在生产必须逐字相同。** 不一致 → 登录能拿到 token，紧接着 me 失败 →「登录已失效」。

本机正常是因为两边密钥已对齐；公网多半在更新后两边不一致，或 identity 指到了另一套 core。

---

## 一、只读核对（不要把密钥打到聊天里）

在副脑03 PowerShell：

```powershell
Set-Location C:\ai24x01

function KeyMeta($path, $name) {
  $line = Select-String -Path $path -Pattern ("^\s*" + [regex]::Escape($name) + "\s*=") |
    Where-Object { $_.Line -notmatch '^\s*#' } | Select-Object -First 1
  if (-not $line) { return [pscustomobject]@{ name=$name; ok=$false; len=0; tail='MISSING'; sha12='-' } }
  $v = ($line.Line -split '=',2)[1].Trim().Trim('"').Trim("'")
  $sha = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($v))).Replace('-','').Substring(0,12).ToLower()
  [pscustomobject]@{
    name=$name; ok=$true; len=$v.Length
    tail=('***' + $v.Substring([Math]::Max(0,$v.Length-4)))
    sha12=$sha
  }
}

$coreEnv = 'C:\ai24x01\api\.env'                 # 若实际路径不同请改
$a1Env   = 'C:\ai24x01\p\a1\api\server\.env'   # 若实际路径不同请改

# 确认文件存在
Test-Path $coreEnv; Test-Path $a1Env

$core = KeyMeta $coreEnv 'SECRET_KEY'
$a1   = KeyMeta $a1Env   'AI24X_JWT_SECRET'
$core; $a1
"MATCH_LEN_TAIL_SHA = $($core.sha12 -eq $a1.sha12 -and $core.len -eq $a1.len)"

# identity 指向（只看 URL，无密钥）
Select-String -Path $a1Env -Pattern '^\s*AI24X_IDENTITY_API_BASE\s*=' | ForEach-Object { $_.Line }

pm2 list
```

期望：

- `MATCH_… = True`
- `AI24X_IDENTITY_API_BASE` 指向本机正在跑的主站 API（常见 `http://127.0.0.1:8002` 或你们文档约定的 core 端口），且该进程用的就是上面的 `api\.env`

若 `MATCH=False` → 执行第二节。

---

## 二、修复（行级改 env，禁止整文件覆盖）

原则：**以主站 `api\.env` 的 `SECRET_KEY` 为准**，把 a1 的 `AI24X_JWT_SECRET` 改成完全相同。  
（若刚轮换过密钥：可把旧 a1 密钥放到 `AI24X_JWT_SECRET_PREV`，再把当前改成与 core 一致，减少旧会话抖动。）

```powershell
# 人工用记事本打开两份 .env，核对 SECRET_KEY 与 AI24X_JWT_SECRET 完全一致后保存
notepad C:\ai24x01\api\.env
notepad C:\ai24x01\p\a1\api\server\.env
```

然后：

```powershell
pm2 restart core-api-8002 --update-env
pm2 restart a-api-8001 --update-env
# 若进程名是 a1-api-18011 / core-8000 等，以 pm2 list 为准，两个都要 --update-env
pm2 list
```

再跑一遍第一节的 `MATCH_…`，必须为 `True`。

---

## 三、验收

1. 浏览器打开 `https://a.ai24x.com/index.html`（可带 `?i=BWPX3Z8B`），**Ctrl+F5**  
2. 清一次该站 Local Storage 里旧 token（或无痕窗口）  
3. 登录 → 应「登录成功 / 已登录」，**不应**再出现「登录已失效，请重新登录。」  
4. 回报主脑：`MATCH` 结果（仅 True/False + 两边 len/tail/sha12）+ 登录是否 OK  

---

## 不要做

- 不要用 Cursor/脚本 **Write 整份覆盖 `.env`**（易把密码写成省略号）  
- 不要为了「方便」把 JWT 改成 `iamlei`（那是 SMS 内部密钥，和登录 JWT 不是一回事）  
- 本次不必为这个现象再改前端代码
