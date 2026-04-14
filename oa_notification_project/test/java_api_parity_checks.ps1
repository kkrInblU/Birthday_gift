param(
  [string]$PythonBaseUrl = "http://127.0.0.1:8000",
  [string]$JavaBaseUrl = "http://127.0.0.1:8080",
  [string]$UserEmail = "3307180168@qq.com",
  [string]$NewsId = ""
)

function Invoke-ApiJson {
  param(
    [string]$Method,
    [string]$Url,
    [object]$Body = $null
  )

  if ($null -eq $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Url -ContentType "application/json"
  }

  return Invoke-RestMethod -Method $Method -Uri $Url -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10)
}

function Get-ObjectKeys {
  param([object]$Object)
  if ($null -eq $Object) { return @() }
  return ($Object.PSObject.Properties.Name | Sort-Object)
}

function Compare-KeySet {
  param(
    [string]$Name,
    [object]$PythonObject,
    [object]$JavaObject
  )

  $pythonKeys = Get-ObjectKeys $PythonObject
  $javaKeys = Get-ObjectKeys $JavaObject

  Write-Host ""
  Write-Host "[$Name]"
  Write-Host "Python keys: $($pythonKeys -join ', ')"
  Write-Host "Java   keys: $($javaKeys -join ', ')"

  $missingInJava = $pythonKeys | Where-Object { $_ -notin $javaKeys }
  $extraInJava = $javaKeys | Where-Object { $_ -notin $pythonKeys }

  if ($missingInJava.Count -eq 0 -and $extraInJava.Count -eq 0) {
    Write-Host "Key parity: OK" -ForegroundColor Green
    return
  }

  if ($missingInJava.Count -gt 0) {
    Write-Host "Missing in Java: $($missingInJava -join ', ')" -ForegroundColor Yellow
  }
  if ($extraInJava.Count -gt 0) {
    Write-Host "Extra in Java: $($extraInJava -join ', ')" -ForegroundColor Yellow
  }
}

$checks = @(
  @{
    Name = "GET /api/notifications"
    PythonUrl = "$PythonBaseUrl/api/notifications?limit=5"
    JavaUrl = "$JavaBaseUrl/api/notifications?limit=5"
  },
  @{
    Name = "GET /api/users/settings"
    PythonUrl = "$PythonBaseUrl/api/users/settings?userEmail=$UserEmail"
    JavaUrl = "$JavaBaseUrl/api/users/settings?userEmail=$UserEmail"
  },
  @{
    Name = "GET /api/subscriptions/departments"
    PythonUrl = "$PythonBaseUrl/api/subscriptions/departments?userEmail=$UserEmail"
    JavaUrl = "$JavaBaseUrl/api/subscriptions/departments?userEmail=$UserEmail"
  },
  @{
    Name = "GET /api/miniapp/subscribe/status"
    PythonUrl = "$PythonBaseUrl/api/miniapp/subscribe/status?userEmail=$UserEmail"
    JavaUrl = "$JavaBaseUrl/api/miniapp/subscribe/status?userEmail=$UserEmail"
  },
  @{
    Name = "GET /api/reminders"
    PythonUrl = "$PythonBaseUrl/api/reminders?userEmail=$UserEmail&limit=5"
    JavaUrl = "$JavaBaseUrl/api/reminders?userEmail=$UserEmail&limit=5"
  },
  @{
    Name = "GET /api/admin/crawler/config"
    PythonUrl = "$PythonBaseUrl/api/admin/crawler/config"
    JavaUrl = "$JavaBaseUrl/api/admin/crawler/config"
  },
  @{
    Name = "GET /api/admin/crawler/jobs"
    PythonUrl = "$PythonBaseUrl/api/admin/crawler/jobs?limit=5&page=1"
    JavaUrl = "$JavaBaseUrl/api/admin/crawler/jobs?limit=5&page=1"
  }
)

if ($NewsId) {
  $checks += @{
    Name = "GET /api/notification-detail"
    PythonUrl = "$PythonBaseUrl/api/notification-detail?newsId=$NewsId"
    JavaUrl = "$JavaBaseUrl/api/notification-detail?newsId=$NewsId"
  }
}

foreach ($check in $checks) {
  try {
    $py = Invoke-ApiJson -Method GET -Url $check.PythonUrl
    $ja = Invoke-ApiJson -Method GET -Url $check.JavaUrl

    Compare-KeySet -Name "$($check.Name) top-level" -PythonObject $py -JavaObject $ja

    if ($py.data -and $ja.data) {
      Compare-KeySet -Name "$($check.Name) data" -PythonObject $py.data -JavaObject $ja.data
      if ($py.data.items -and $ja.data.items -and $py.data.items.Count -gt 0 -and $ja.data.items.Count -gt 0) {
        Compare-KeySet -Name "$($check.Name) first-item" -PythonObject $py.data.items[0] -JavaObject $ja.data.items[0]
      }
    }
  } catch {
    Write-Host ""
    Write-Host "[$($check.Name)] request failed: $($_.Exception.Message)" -ForegroundColor Red
  }
}
