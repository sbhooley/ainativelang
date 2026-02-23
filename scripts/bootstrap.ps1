Param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
Write-Host "==> AINL bootstrap (Windows)"

& $PythonExe --version | Out-Null
& $PythonExe -m venv .venv
& .\.venv\Scripts\python -m pip install --upgrade pip
& .\.venv\Scripts\pip install -e ".[dev,web]"

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Activate: .\.venv\Scripts\Activate.ps1"
Write-Host "Validate: ainl-validate examples/blog.lang --emit ir"
