@echo off
chcp 65001 >nul
echo ============================================
echo AI24X 01 营销任务执行器
echo 日期：%date%
echo ============================================
echo.
echo 任务1：GitHub 推送示例代码
echo 请用浏览器打开 https://github.com/ai24x/ai24x-examples
echo 上传以下文件到对应目录：
echo   %USERPROFILE%\ops\worker\github-ai24x-examples\README.md → 仓库根
echo   ...\python\README.md → python/
echo   ...\node\README.md → node/
echo   ...\curl\README.md → curl/
echo.
echo 任务2：dev.to 发布 DeepSeek 指南
echo 请用浏览器打开 https://dev.to
echo 登录 social@ai24x.com
echo 发布 %USERPROFILE%\ops\worker\devto-deepseek-guide.md
echo 标题：DeepSeek API Pricing in 2026
echo 标签：deepseek, api, pricing, llm, ai
echo.
echo 任务3：需求调研
echo 搜索以下三类求助，各找至少4条（共12条）：
echo   1. DeepSeek API payment failed / card declined
echo   2. MiMo API access / billing / getting started
echo   3. Qwen API setup / international endpoint / billing confusion
echo 每条记录：链接 + 时间 + 原话 + 是否已解决
echo.
echo 完成后请写回执到：
echo   %%USERPROFILE%%\ops\receipts\2026-09-14\receipt-20260914-01.md
echo.
echo ============================================
pause
