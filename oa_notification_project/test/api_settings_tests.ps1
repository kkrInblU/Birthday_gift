$ApiBaseUrl = "http://127.0.0.1:8000"
$UserEmail = "3307180168@qq.com"

Write-Host "== 1. 查询当前用户刷新周期设置 ==" -ForegroundColor Cyan
Invoke-RestMethod `
  -Method GET `
  -Uri "$ApiBaseUrl/api/users/settings?userEmail=$UserEmail"

Write-Host ""
Write-Host "== 2. 更新用户刷新周期为 5 分钟 ==" -ForegroundColor Cyan
Invoke-RestMethod `
  -Method POST `
  -Uri "$ApiBaseUrl/api/users/settings" `
  -ContentType "application/json" `
  -Body '{"userEmail":"3307180168@qq.com","refreshIntervalMinutes":5}'

Write-Host ""
Write-Host "== 3. 再次查询，确认设置已生效 ==" -ForegroundColor Cyan
Invoke-RestMethod `
  -Method GET `
  -Uri "$ApiBaseUrl/api/users/settings?userEmail=$UserEmail"

Write-Host ""
Write-Host "== 4. 更新用户刷新周期为 30 分钟 ==" -ForegroundColor Cyan
Invoke-RestMethod `
  -Method POST `
  -Uri "$ApiBaseUrl/api/users/settings" `
  -ContentType "application/json" `
  -Body '{"userEmail":"3307180168@qq.com","refreshIntervalMinutes":30}'

Write-Host ""
Write-Host "== 5. 最终查询 ==" -ForegroundColor Cyan
Invoke-RestMethod `
  -Method GET `
  -Uri "$ApiBaseUrl/api/users/settings?userEmail=$UserEmail"
