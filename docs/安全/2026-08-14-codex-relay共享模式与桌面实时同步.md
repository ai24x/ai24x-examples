# Codex Relay 共享模式打通（2026-08-14 司令落地）

## 目标
- 手机 Codex Relay ↔ 电脑 Codex 实时同步（手机发的消息，桌面端不用重启就能看到）。
- 解决「桌面 GUI 不实时刷新手机消息」「游戏开发收到任务不自动执行」两类问题。

## 结论（架构事实）
- 桌面官方 GUI 不支持直连共享 app-server（app.asar 无相关代码；GUI 自己起私有 stdio app-server）。
- 官方打通方式 = relay 共享模式 + 桌面终端 `codex resume --remote ws://127.0.0.1:8788`。
- 手机消息实际都已写入同一会话文件（`C:\Users\Admin\.codex\sessions\...`），桌面窗口只是不实时刷新。

## 启动/停止命令
- 启动（共享模式后台）：
  ```powershell
  node "C:\Users\Admin\AppData\Local\npm-cache\_npx\61cc710ad02b2d10\node_modules\codex-relay\dist\cli.js" --bg --shared-app-server
  # 等价：npx codex-relay@latest --bg --shared-app-server
  ```
- 停止：`npx codex-relay@latest stop`（需在 C:\Users\Admin 下运行；读 `%APPDATA%\codex-relay\server.pid`）。
- ⚠️ `--bg` 在 Windows 会误报「failed to start in background」：relay 用 `ps` 命令验证后台进程，Windows 没有 `ps`，报错但实际已启动。验证方式：`netstat -ano | findstr ":8787 :8788"` + `Get-Content %APPDATA%\codex-relay\server.pid`。

## 端口与进程
- 8787 = relay 服务器（手机 App 连这里，配对密钥/配对记录不变，重启不用重新扫码）。
- 8788 = 共享 app-server（`codex app-server --listen ws://127.0.0.1:8788`，由 relay 拉起）。
- 桌面实时同步命令：`codex resume --remote ws://127.0.0.1:8788`（可加 thread_id 直达）。

## 桌面快捷方式（已建）
- `C:\Users\Admin\Desktop\司令·实时同步（日常交流）.cmd`
- 内容：`codex resume --remote ws://127.0.0.1:8788 019ffab8-3bd9-71f2-b164-8ef78cafe31e`
- 日常交流 thread id：`019ffab8-3bd9-71f2-b164-8ef78cafe31e`

## 手机端
- 服务端重启后，手机 App 重新打开或下拉刷新即可重连（server-identity-key 与 auth.db 均保留）。
- 如手机 App 提示版本不匹配，可用 `npx codex-relay@1.4.0` 固定版本重试（当前用 1.4.7）。

## 游戏开发执行问题（已解决）
- 「游戏开发」会话（thread `019ffb9a-e3ca-75f3-b618-93f6e4b3a1f8`，cwd `p\game`，deepseek 直连）已执行任务：
  - DEV-20260813-01：A「别听它的」体验优化（12 条问题 + 12 项落地）✅
  - DEV-20260813-02：B/C/D/F 四原型 + A 基准 ✅
  - 回执：`p\game\开发任务\inbox\DEV-20260813-01-回执.md`、`DEV-20260813-02-回执.md`
- 原因：外部往会话文件追加消息不会自动触发 agent 执行；需在窗口内真正「发送」或用 CLI 触发（`codex exec resume <thread> "..."`）。

## 备注
- msedge.exe 弹窗（0x80000003）：桌面 GUI 是 Chromium 内核，web 运行库偶发崩溃弹窗，不影响会话数据；可忽略或重启 GUI。
