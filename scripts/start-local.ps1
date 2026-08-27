param(
  [switch]$ApiOnly,
  [switch]$NoSeed
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-EnvFile([string]$Path) {
  $result = @{}
  if (-not (Test-Path $Path)) { return $result }
  foreach ($line in Get-Content $Path) {
    if ($line -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
      $result[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
    }
  }
  return $result
}
function EnvOr([hashtable]$EnvMap, [string]$Name, [string]$Default) {
  if ($EnvMap.ContainsKey($Name) -and $EnvMap[$Name]) { return $EnvMap[$Name] }
  return $Default
}

if (-not (Test-Path ".env")) { throw "Missing .env. Run .\scripts\setup-local.ps1 once first." }
$cfg = Read-EnvFile (Join-Path $Root ".env")
$sshHost = EnvOr $cfg "SSH_HOST" "115.159.67.119"
$sshPort = EnvOr $cfg "SSH_PORT" "22"
$sshUser = EnvOr $cfg "SSH_USER" "ubuntu"
$keyPath = EnvOr $cfg "SSH_KEY_PATH" (Join-Path $env:USERPROFILE ".ssh\codexssh.pem")
$localPort = [int](EnvOr $cfg "SSH_LOCAL_PORT" "15432")
$remoteHost = EnvOr $cfg "SSH_REMOTE_HOST" "127.0.0.1"
$remotePort = EnvOr $cfg "SSH_REMOTE_PORT" "5432"
$keyPath = [Environment]::ExpandEnvironmentVariables($keyPath)
if (-not (Test-Path -LiteralPath $keyPath)) { throw "SSH private key not found: $keyPath. Set SSH_KEY_PATH in .env." }

$existing = Get-NetTCPConnection -LocalPort $localPort -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
  Write-Host "Starting SSH tunnel localhost:$localPort -> $sshHost`:$remotePort..."
  $sshArgs = @(
    "-N", "-i", $keyPath, "-o", "IdentitiesOnly=yes",
    "-o", "ExitOnForwardFailure=yes", "-o", "StrictHostKeyChecking=accept-new",
    "-L", "${localPort}:${remoteHost}:${remotePort}",
    "-p", $sshPort, "${sshUser}@${sshHost}"
  )
  $tunnel = Start-Process -FilePath "ssh.exe" -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
  Start-Sleep -Seconds 2
  $existing = Get-NetTCPConnection -LocalPort $localPort -State Listen -ErrorAction SilentlyContinue
  if (-not $existing) {
    if (-not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
    throw "SSH tunnel did not start. Run ssh manually once to accept the host key or inspect key permissions."
  }
  Write-Host "SSH tunnel started (PID $($tunnel.Id))."
} else { Write-Host "SSH tunnel already listening on localhost:$localPort." }

if (-not $NoSeed) {
  & ".venv\Scripts\python.exe" -m backend.scripts.seed_postgres
  if ($LASTEXITCODE -ne 0) { throw "Database check/seed failed." }
}

$apiListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $apiListener) {
  Write-Host "Starting FastAPI on http://127.0.0.1:8000..."
  Start-Process -FilePath (Join-Path $Root ".venv\Scripts\python.exe") -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
} else { Write-Host "FastAPI already listening on port 8000." }

if (-not $ApiOnly) {
  if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..."
    Push-Location frontend
    npm install
    Pop-Location
  }
  $webListener = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
  if (-not $webListener) {
    Write-Host "Starting Next.js on http://localhost:3000..."
    Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $Root "frontend") -WindowStyle Hidden | Out-Null
  } else { Write-Host "Next.js already listening on port 3000." }
}

Start-Sleep -Seconds 2
try {
  $health = Invoke-RestMethod "http://127.0.0.1:8000/api/health" -TimeoutSec 8
  Write-Host ("API health: " + ($health | ConvertTo-Json -Compress))
} catch { Write-Warning "API is still starting; check http://127.0.0.1:8000/api/health in a few seconds." }
Write-Host "CHATBI is ready: http://localhost:3000"
