# 副脑04 · 更新指令（用户错误双语 detail 不泄漏 · 需重启 core）

> 发令：2026-08-02 · 目标提交 `eee0cef`  
> 范围：`api/` 异常响应 + 静态 `web/js/api.js`（**需** `Restart-Service AI24X-core`）  
> **禁止**整文件覆盖 `api/.env`

## 问题

限购等接口 `detail` 为双语 dict 时，全局异常把 `str(dict)` 塞进 `error`，控制台出现：

`{'message_zh': '该优惠套餐…', 'message_en': '…', …}`

## 本包

| 项 | 说明 |
|----|------|
| API | `flatten_http_detail`：`error` 只给短句；另附结构化 `detail` |
| 前端 | `api.js` 优先读 `detail.message_zh/en`；兼容旧 `str(dict)`；禁漏 `message_zh` 键名 |
| 缓存 | 页面 `api.js?v=20260802h` |

## 执行

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
git log -1 --oneline

Restart-Service AI24X-core
Start-Sleep -Seconds 3
Get-Service AI24X-core

# 静态页已随仓库；确认 api.js 版本
curl.exe -sS https://www.ai24x.com/console.html | Select-String "api.js\?v="
```

## 验收回报主脑

1. 对已购入门包账号再下单入门档：前端提示为**纯中文/英文短句**（无 `message_zh` / 花括号）  
2. `AI24X-core` Running；回报 `git log -1 --oneline`
