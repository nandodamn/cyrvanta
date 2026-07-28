$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
$node = "C:\Users\ferna\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$docker = "C:\Program Files\Docker\Docker\resources\bin"

if (-not (Test-Path $python)) { throw "Python virtual environment is missing." }
$env:Path = "$node;$docker;$env:Path"
$env:npm_config_cache = "C:\tmp\cyrvanta-npm-cache"

& $python -m ruff check (Join-Path $repo "backend")
if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }
& $python -m mypy (Join-Path $repo "backend\src")
if ($LASTEXITCODE -ne 0) { throw "mypy failed." }
& $python -m pytest (Join-Path $repo "backend\tests") -q
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }

Push-Location (Join-Path $repo "frontend")
try {
  npm run format:check
  if ($LASTEXITCODE -ne 0) { throw "Frontend formatting check failed." }
  npm run lint
  if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
  npm test
  if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
  Pop-Location
}

Push-Location $repo
try {
  docker compose --profile core config --quiet
  if ($LASTEXITCODE -ne 0) { throw "Compose validation failed." }
  $health = Invoke-RestMethod "http://localhost:8080/api/v1/health"
  if ($health.status -ne "ok") { throw "API health failed." }
  $headers = (& curl.exe -s -D - -o NUL "http://localhost:8080/healthz") -join "`n"
  if ($headers -notmatch "(?i)X-Content-Type-Options:\s*nosniff") {
    throw "Reverse-proxy security headers are missing."
  }
  if ($headers -notmatch "(?i)Content-Security-Policy:.*object-src 'none'") {
    throw "Content Security Policy is incomplete."
  }
  if ($headers -notmatch "(?i)Permissions-Policy:\s*camera=\(\)") {
    throw "Permissions Policy is missing."
  }
} finally {
  Pop-Location
}

Write-Host "CYRVANTA_ACCEPTANCE_OK"
