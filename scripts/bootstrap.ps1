Param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
Write-Host "==> AINL bootstrap (Windows)"

& $PythonExe --version | Out-Null
& $PythonExe -m venv .venv
& .\.venv\Scripts\python -m pip install --upgrade pip
$extras = if ($env:AINL_PIP_EXTRAS) { $env:AINL_PIP_EXTRAS } else { "dev,web,mcp" }
$editable = ".[$extras]"
& .\.venv\Scripts\pip install -e $editable

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Activate: .\.venv\Scripts\Activate.ps1"
Write-Host "Validate: ainl-validate examples/blog.lang --emit ir"
