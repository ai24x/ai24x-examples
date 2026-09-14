# 副脑02 任务书：Poki 双人/热门小游戏榜竞品监控（2026-08-13）

> 派发：司令（Codex）｜ 目标：搭每日竞品监控，输出榜单日报，为矩阵选型/复制提供数据

## 背景
矩阵选型需要持续监控 Poki 热门玩法与微信小游戏爆款。先做 Poki 榜抓取。

## 任务步骤
1. 创建目录 C:\Users\Administrator\game\poki-monitor\，初始化 node 项目（npm init -y && npm i playwright）。
2. 安装 chromium（npx playwright install chromium）。
3. 编写脚本 monitor.js：
   - 打开 https://poki.com/zh/双人 与 https://poki.com/zh （或 https://poki.com/en/two-player 兜底）
   - 抓取页面游戏列表：游戏名 + 链接 + 热度排序（页面结构自己 inspect，取可见的游戏卡片标题与 href）
   - 输出 top30 到 C:\Users\Administrator\ops\poki-top-YYYYMMDD.md（Markdown 表格：排名/名称/链接）
4. 首次运行，生成今日报告。
5. 写回执 C:\Users\Administrator\ops\poki-monitor-回执.md：✅ 已抓取 N 款 / ⚠️ 问题项（如页面结构变化、反爬），并给出「可否每日定时」建议。

## 验收
- 今日报告落盘（含 top30）；回执说明抓取稳定性和定时可行性。
- 完成后通过主脑/飞书回执司令。

## 注意
- Windows 环境；禁止触碰生产服务；页面结构可能变化，灵活处理。
