# OpenClaw 2026.7.1-2 · DeepSeek 配置（PowerShell）

> 适用：各副脑（01 / 02 / 03 / 04）  
> 前提：已升级到 2026.7.1-2

---

## 第 0 步：先找回原来的 DeepSeek Key

升级前，**先查一下旧版配置里的 DeepSeek API Key**，省得找不回来：

```powershell
# 方法 1：看看旧版 auth 配置
openclaw models auth list

# 方法 2：搜环境变量
echo $env:DEEPSEEK_API_KEY

# 方法 3：搜旧版 openclaw.json 里的 apiKey
Select-String "deepseek" "$env:USERPROFILE\.openclaw\openclaw.json"

# 方法 4：如果上面都找不到，找 .env 文件
Get-ChildItem "$env:USERPROFILE\.openclaw" -Filter "*.env*"
Get-ChildItem "E:\AI24X" -Filter "*.env*" -Recurse -ErrorAction SilentlyContinue
```

找到的 Key 先记下来，下一步配置要用。

---

## 第 1 步：配置 DeepSeek

```powershell
openclaw models auth add deepseek:default --provider deepseek --mode api_key
```

输入刚才找到的 DeepSeek API Key，回车。

验证：
```powershell
openclaw models auth list
```
应显示：`deepseek:default [deepseek/api_key]`

---

## 第 2 步：加别名（方便对话切换模型）

```powershell
openclaw config set "models.deepseek/deepseek-v4-flash.alias" "DeepSeek"
openclaw config set "models.deepseek/deepseek-v4-pro.alias" "DeepSeek Pro"
```

---

## 第 3 步：设为默认模型（可选）

```powershell
openclaw config set "agents.defaults.model" "deepseek/deepseek-v4-flash"
```

---

## 第 4 步：重启 Gateway

```powershell
openclaw gateway restart
```

---

## 第 5 步：测试

```powershell
openclaw chat -m "Hello"
```

或者在飞书上给 Bot 发条消息测试。

---

## 🩹 常见问题

| 问题 | 解决 |
|------|------|
| `model not found` | 先 `openclaw config set models.mode merge` 再重启 |
| API Key 找不到 | 去 DeepSeek 官网重新生成一个 |
| 输完 Key 但连不上 | 检查网络能否访问 `api.deepseek.com` |
| 重启后模型列表为空 | 确认 `openclaw.json` 中 `models.providers.deepseek` 段完整 |

---

> 🎇 主脑 AI24X永生 · 2026-07-26
