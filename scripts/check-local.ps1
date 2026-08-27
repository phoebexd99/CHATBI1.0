$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
Write-Host "--- listeners ---"
Get-NetTCPConnection -LocalPort 15432,8000,3000 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess,State | Format-Table
Write-Host "--- API health ---"
try { Invoke-RestMethod "http://127.0.0.1:8000/api/health" -TimeoutSec 5 | ConvertTo-Json } catch { Write-Warning $_ }
Write-Host "--- smoke query ---"
try { Invoke-RestMethod "http://127.0.0.1:8000/api/query" -Method Post -ContentType "application/json" -Body '{"question":"最近 30 天 GMV 是多少？"}' -TimeoutSec 30 | Select-Object answer,sql,rows,latency_ms | ConvertTo-Json -Depth 6 } catch { Write-Warning $_ }
