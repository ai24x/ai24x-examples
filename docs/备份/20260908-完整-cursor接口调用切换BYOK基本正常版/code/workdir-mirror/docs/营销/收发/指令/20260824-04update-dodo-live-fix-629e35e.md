【更新部署验收】Dodo live 支付修复 + open 支付宝恢复 · 司令 2026-08-24

目标提交：629e35e（已双推 gitee + origin）
涉及文件：.gitignore / api/token_plans.py / p/open/api/a1_pay_credentials.py /
p/open/api/token_plans.py / p/open/api/data/token_plans_override.json（移除跟踪）/ p/markets/scripts/_qa_dodo_live_fix_20260824.js（QA）

背景：Dodo 切 live 后 open 站下单报「服务暂时不可用」（商品 ID 还是 test 环境）+ 支付宝按钮丢失（open .env 缺私钥、复用 a1 凭证路径算错）；www 站 Starter 促销限购误伤已购用户。

======================== 一、更新代码 ========================
1) 备份并还原本批文件（幂等，防 04 本地脏改动冲突）：
$paths = @('api/token_plans.py','p/open/api/a1_pay_credentials.py','p/open/api/token_plans.py','.gitignore')
foreach ($p in $paths) {
  if (Test-Path $p) {
    $bak = 'C:\Users\Administrator\ops\bak-20260824-dodofix-' + ($p -replace '[\\/]','_')
    Copy-Item $p $bak -Force -ErrorAction SilentlyContinue
    git checkout -- $p -ErrorAction SilentlyContinue
  }
}
2) git fetch --all
3) git merge-base --is-ancestor 629e35e origin/master; if ($LASTEXITCODE -ne 0) { git merge-base --is-ancestor 629e35e gitee/master; if ($LASTEXITCODE -ne 0) { Write-Output 'FATAL: target commit not found'; exit 1 } }
4) git pull
5) git log --oneline -1  -> 应包含 629e35e；git diff --quiet 629e35e HEAD -- api/token_plans.py p/open/api/a1_pay_credentials.py p/open/api/token_plans.py .gitignore; if ($LASTEXITCODE -ne 0) { Write-Output 'FATAL: paths mismatch'; exit 1 }

======================== 二、生产补丁（.env + 覆盖文件） ========================
补丁脚本已放在 C:\Users\Administrator\ops\open_pay_fix_20260824.ps1（本次随派发 scp 过去）
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\ops\open_pay_fix_20260824.ps1
预期输出：PATCH_OK backup=C:\Users\Administrator\ops\.bak-open-pay-fix-<时间戳>
补丁内容：
- open .env：ALIPAY_MERCHANT_PRIVATE_KEY_PATH=core 同款证书路径（C:\ai24x01\api\certs\alipay_merchant_private.pem，已验证存在）；DODO_PRODUCT_BYOK_MONTH/YEAR = live ID
- open 覆盖文件：token_plans_override.json 与 byok_plans_override.json 写入 8 个 live 商品 ID（保留原价字段）
- core .env：DODO_PRODUCT_MARKETS_* 同步 live ID（卫生项，覆盖文件已优先）

======================== 三、重启服务 ========================
Restart-Service AI24X-open-api -Force
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 8

======================== 四、验收 ========================
1) open 本机 /v1/billing/plans：pay.alipay_ready=true、pay.dodo_ready=true、dodo_mode=live
   (Invoke-RestMethod -Uri 'http://127.0.0.1:18080/v1/billing/plans' -UseBasicParsing).pay | ConvertTo-Json -Depth 3
2) open 覆盖文件 live ID 抽查：
   Select-String -Path C:\ai24x01\p\open\api\data\token_plans_override.json -Pattern 'pdt_0Nm4miLZyMCVqx6jdyN0i'（Starter）
   Select-String -Path C:\ai24x01\p\open\api\data\byok_plans_override.json -Pattern 'pdt_0Nm4miBINZnpO7cqiN4CA'（BYOK 月）
3) www /v1/billing/plans：token_pack_10k promo_max_purchases 为空/0；pay.alipay_ready=true、dodo_ready=true
4) 公网 health commit：https://open.ai24x.com/health 与 https://www.ai24x.com/health 均含 629e35e
5) 公网冒烟（04 从新加坡节点）：
   open console https://open.ai24x.com/console.html#billing 选择任一套餐 -> 弹窗应出现 支付宝/Alipay 与 Dodo 按钮
   www console https://www.ai24x.com/console.html#billing 选择 Starter -> 应可正常创建 Dodo 收银台（不再提示限购）

======================== 五、回执 ========================
按模板回执：✅ 已完成项（HEAD/补丁输出/服务重启/5 项验收逐条）/ ⚠️ 问题项（无则写「无」），发指挥部群。
