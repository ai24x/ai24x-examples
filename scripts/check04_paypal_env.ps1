# 只读查询：04 生产 api\.env 的支付回跳配置（不输出任何密钥/secret）
$ErrorActionPreference = "Stop"
$envFile = 'C:\ai24x01\api\.env'
if (-not (Test-Path $envFile)) {
    Write-Output "ENV_NOT_FOUND:$envFile"
    exit 1
}
$keys = @(
    'TOKEN_PAYPAL_RETURN_URL',
    'TOKEN_PAYPAL_CANCEL_URL',
    'PAYPAL_MODE',
    'TOKEN_PAYPAL_LOCALE',
    'TOKEN_PAYPAL_LANDING_PAGE',
    'TOKEN_ALIPAY_RETURN_URL',
    'TOKEN_ALIPAY_WAP_RETURN_URL',
    'TOKEN_ALIPAY_NOTIFY_URL',
    'TOKEN_WECHAT_NOTIFY_URL',
    'TOKEN_PAY_ENABLED',
    'CREEM_RETURN_URL'
)
Get-Content $envFile | ForEach-Object {
    foreach ($k in $keys) {
        if ($_ -match "^$k=(.*)$") {
            Write-Output "$k=$($Matches[1])"
        }
    }
}
