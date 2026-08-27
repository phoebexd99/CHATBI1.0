$ErrorActionPreference = "SilentlyContinue"
foreach ($port in @(3000, 8000, 15432)) {
  Get-NetTCPConnection -LocalPort $port -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
}
Write-Host "Stopped CHATBI local API, frontend, and SSH tunnel listeners (if present)."
