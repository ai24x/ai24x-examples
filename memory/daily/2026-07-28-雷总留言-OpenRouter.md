# 2026-07-28 下午 · 雷总留言（自动已做 / 请你做）

## 已自动完成（推 Gitee）

- 规划 §四更新为 **v1.0.2**：OpenRouter 主路径 → 直连 DS/Qwen 兜底；P0/P1/P2 模型清单  
- 默认档位：L1=`qwen/qwen3.7-flash`，L2=`deepseek/deepseek-r1`，L3=`openai/gpt-4o-mini`  
- 联调文 + 烟测脚本：`docs/联调/OpenRouter聚合接入.md` · `api/scripts_openrouter_smoke.py`

## 请你做（约 20～40 分钟）

1. **OpenRouter**  
   - 注册 https://openrouter.ai/ 并充值小额（≥$5～10）  
   - 创建 API Key  

2. **本机 `api/.env` 行级追加**（禁止整文件覆盖）  
   ```
   TOKEN_LLM_UPSTREAM=openrouter
   OPENROUTER_API_KEY=sk-or-v1-...
   OPENROUTER_SITE_URL=https://www.ai24x.com
   OPENROUTER_APP_NAME=AI24X
   ```  

3. **重启并测**  
   ```
   pm2 restart core-8000 --update-env
   cd api
   python scripts_openrouter_smoke.py
   set OPENROUTER_SMOKE_LIVE=1
   python scripts_openrouter_smoke.py
   ```  
   期望 live 的 provider=`openrouter`，不是 stub。  

4. **顺手看一眼**  
   - PayPal 商户审核进度（过了再谈 Live，仍只开副脑04）  

## 先别做

- 生产写 Live PayPal / 开区路由  
- 直连十家官方 Key（等 OR 跑通再说）  
