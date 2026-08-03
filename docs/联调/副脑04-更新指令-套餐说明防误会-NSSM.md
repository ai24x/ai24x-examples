# 副脑04 · 更新指令（套餐说明防误会 · API+静态）

> 发令：2026-08-03 · **副脑04 = 对外生产**
> 目标提交：`0fc98bb`  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

## 本包

| 项 | 说明 |
|----|------|
| API | `token_plans` 文案 + 能力字段；套餐排序 Scale 优先 |
| 静态 | 控制台/价格页标签与「立刻能用 / 不要误会」；支付成功分 SKU；Key「使用说明」 |

## 执行

```powershell
Set-Location C:\ai24x01
git pull origin master
git log -1 --oneline
nssm restart AI24X-core
# 硬刷新 console.html / pricing.html
```

## 验收

1. 控制台套餐：Scale 靠前，有「推荐·可点名」等标签  
2. Pro 月卡可见「不要误会：单买不能打名模」  
3. 支付成功文案随套餐变化（月卡 ≠ 笼统「Token 已到账」）  
4. Key 按钮为「使用说明」，提示多 Key 共用、充值无需重建  

## 回滚

还原 `api/token_plans.py` + `web/js/api.js` + `web/js/console.js` + `web/pricing.html` + `web/console.html` + `web/config/locales.js` 后重启 core。
