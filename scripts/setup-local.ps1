param(
  [switch]$SkipInstall,
  [switch]$SkipSeed
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "CHATBI local setup: $Root"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "Creating Python virtual environment..."
  python -m venv .venv
}
if (-not $SkipInstall) {
  Write-Host "Installing backend dependencies..."
  & ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
  if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
}
if (-not (Test-Path ".env")) {
  Write-Host "No .env found. Configure the tunneled PostgreSQL connection now."
  & ".venv\Scripts\python.exe" -m backend.scripts.configure_local_env
  if ($LASTEXITCODE -ne 0) { throw "PostgreSQL configuration failed." }
}
if (-not $SkipSeed) {
  Write-Host "Applying CHATBI schema and seed data..."
  & ".venv\Scripts\python.exe" -m backend.scripts.seed_postgres
  if ($LASTEXITCODE -ne 0) { throw "PostgreSQL schema/seed failed. Is the SSH tunnel running?" }
}
Write-Host "Local setup complete. Run .\scripts\start-local.ps1 next."
