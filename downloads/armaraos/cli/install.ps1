# ArmaraOS installer for Windows — installs CLI + AINL (both required)
# Usage: irm https://ainativelang.com/install.ps1 | iex
#
# Environment variables:
#   $env:ARMARAOS_INSTALL_DIR  — custom install directory
#   $env:ARMARAOS_VERSION      — specific version tag
#   $env:ARMARAOS_AUTO_PYTHON  — set to 0 to skip winget Python install (default: 1)
#   $env:ARMARAOS_SKIP_AUTO_LAUNCH — set to 1 to skip auto start + dashboard (default: 0)
#   $env:ARMARAOS_DAEMON_START_TIMEOUT — seconds to poll /api/health after spawn (default: 45)
#   $env:ARMARAOS_INSTALL_DAEMON_BUDGET — max seconds for the whole launch phase (default: 120)
#   $env:ARMARAOS_INSTALL_DAEMON_GRACE_SEC — final recheck after main wait (default: 15)
#   $env:ARMARAOS_SKIP_INSTALL_REPAIR — set to 1 to skip repair+retry during launch (default: 0)
#
# Legacy: OPENFANG_INSTALL_DIR, OPENFANG_VERSION

$ErrorActionPreference = 'Stop'

$DownloadBase = if ($env:ARMARAOS_DOWNLOAD_BASE) { $env:ARMARAOS_DOWNLOAD_BASE.TrimEnd('/') } else { "https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli" }
$DefaultInstallDir = Join-Path $env:USERPROFILE ".armaraos\bin"
$InstallDir =
    if ($env:ARMARAOS_INSTALL_DIR) { $env:ARMARAOS_INSTALL_DIR }
    elseif ($env:OPENFANG_INSTALL_DIR) { $env:OPENFANG_INSTALL_DIR }
    else { $DefaultInstallDir }

$Script:InstallScriptRevision = '20260610.3'

function Write-Banner {
    Write-Host ""
    Write-Host "  ArmaraOS Installer" -ForegroundColor Cyan
    Write-Host "  ==================" -ForegroundColor Cyan
    Write-Host "  Script revision: $Script:InstallScriptRevision" -ForegroundColor DarkGray
    Write-Host ""
}

function Refresh-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($machine -and $user) { $env:Path = "$machine;$user" }
    elseif ($user) { $env:Path = $user }
    elseif ($machine) { $env:Path = $machine }
}

function Add-UserPathEntry {
    param([string]$Dir)
    if (-not $Dir -or -not (Test-Path $Dir)) { return }
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($current -like "*$Dir*") { return }
    [Environment]::SetEnvironmentVariable("Path", "$Dir;$current", "User")
    Refresh-SessionPath
    Write-Host "  Added $Dir to user PATH." -ForegroundColor Green
}

function Test-Python310Plus {
    param([string]$PyCmd)
    if (-not $PyCmd) { return $false }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $PyCmd -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
    finally { $ErrorActionPreference = $prev }
}

# AINL is tested on 3.10-3.13; 3.14+ often lacks wheels and breaks pip installs.
function Test-PythonVersionSupported {
    param([string]$PyCmd)
    if (-not $PyCmd) { return $false }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $PyCmd -c "import sys; v=sys.version_info; raise SystemExit(0 if (3, 10) <= v[:2] < (3, 14) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
    finally { $ErrorActionPreference = $prev }
}

function Get-HostCpuArch {
    if ($script:ArmaraosHostCpuArch) { return $script:ArmaraosHostCpuArch }
    $arch = ""
    try { $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() } catch {}
    if (-not $arch) { try { $arch = $env:PROCESSOR_ARCHITECTURE } catch {} }
    if (-not $arch -and [IntPtr]::Size -eq 8) { $arch = "X64" }
    switch ("$arch".ToUpper().Trim()) {
        { $_ -in "ARM64", "AARCH64", "ARM" } { $script:ArmaraosHostCpuArch = "aarch64"; return "aarch64" }
        default { $script:ArmaraosHostCpuArch = "x86_64"; return "x86_64" }
    }
}

function Test-WindowsArm64Host {
    return (Get-HostCpuArch) -eq "aarch64"
}

function Test-PythonIsNativeArm64 {
    param([string]$PyCmd)
    $resolved = Resolve-PythonExecutable $PyCmd
    if (-not $resolved) { return $false }
    if ($resolved -match '(?i)([\\/]|-)arm64([\\/]|$)') { return $true }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $resolved -c "import platform; m=platform.machine().lower(); raise SystemExit(0 if m in ('arm64','aarch64') else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
    finally { $ErrorActionPreference = $prev }
}

function Test-PythonAinlCompatible {
    param([string]$PyCmd)
    if (-not (Test-PythonVersionSupported $PyCmd)) { return $false }
    if ((Test-WindowsArm64Host) -and (Test-PythonIsNativeArm64 $PyCmd) -and $env:ARMARAOS_ALLOW_ARM64_PYTHON -ne '1') {
        return $false
    }
    return $true
}

function Get-PythonVersionLabel {
    param([string]$PyCmd)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        return (& $PyCmd -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null | Select-Object -First 1)
    } catch { return "unknown" }
    finally { $ErrorActionPreference = $prev }
}

function Invoke-PipInstall {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string[]]$PipArguments
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $lines = New-Object System.Collections.Generic.List[string]
    try {
        & $Python -m pip @PipArguments 2>&1 | ForEach-Object {
            [void]$lines.Add($_.ToString())
        }
        return @{
            Ok  = ($LASTEXITCODE -eq 0)
            Log = ($lines -join [Environment]::NewLine)
        }
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Resolve-PythonExecutable {
    param($Py)
    if ($null -eq $Py) { return $null }
    if ($Py -is [System.Array]) {
        foreach ($item in $Py) {
            $resolved = Resolve-PythonExecutable ([string]$item)
            if ($resolved -and (Test-PythonAinlCompatible $resolved)) { return $resolved }
        }
        return $null
    }
    $Py = "$Py".Trim()
    if (-not $Py) { return $null }
    if (Test-Path -LiteralPath $Py) { return $Py }
    $cmd = Get-Command $Py -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    return $Py
}

function Find-PythonFromRegistry {
    $paths = @()
    foreach ($root in @(
            "HKCU:\Software\Python\PythonCore",
            "HKLM:\Software\Python\PythonCore",
            "HKLM:\Software\WOW6432Node\Python\PythonCore"
        )) {
        if (-not (Test-Path $root)) { continue }
        foreach ($verKey in Get-ChildItem $root -ErrorAction SilentlyContinue) {
            if ($verKey.PSChildName -notmatch '^3\.(1[0-3])') { continue }
            $props = Get-ItemProperty -Path "$($verKey.PSPath)\InstallPath" -ErrorAction SilentlyContinue
            if ($props.'(default)') {
                $paths += (Join-Path $props.'(default)' "python.exe")
            }
        }
    }
    foreach ($py in $paths) {
        if ((Test-Path -LiteralPath $py) -and (Test-PythonAinlCompatible $py)) { return $py }
    }
    return $null
}

function Find-PythonViaLauncher {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { return $null }
    foreach ($ver in @("-3.12", "-3.11", "-3.10")) {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $resolved = (& py $ver -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
        } finally {
            $ErrorActionPreference = $prev
        }
        if ($resolved -and (Test-PythonAinlCompatible $resolved)) { return $resolved.Trim() }
    }
    return $null
}

function Find-Python {
    # Our x64 bundle (Windows ARM) before winget's native ARM64 Python312-arm64.
    $armaraosPy = Join-Path $env:USERPROFILE ".armaraos\python312\python.exe"
    if ((Test-Path -LiteralPath $armaraosPy) -and (Test-PythonAinlCompatible $armaraosPy)) { return $armaraosPy }

    foreach ($ver in @("312", "311", "310")) {
        $localPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$ver\python.exe"
        if ((Test-Path -LiteralPath $localPy) -and (Test-PythonAinlCompatible $localPy)) { return $localPy }
    }

    $fromReg = Find-PythonFromRegistry
    if ($fromReg) { return $fromReg }

    $fromLauncher = Find-PythonViaLauncher
    if ($fromLauncher) { return $fromLauncher }

    foreach ($name in @("python3.12", "python3.11", "python3.10")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $resolved = Resolve-PythonExecutable $name
            if ($resolved -and (Test-PythonAinlCompatible $resolved)) { return $resolved }
        }
    }
    return $null
}

function Wait-ForCompatiblePython {
    param([int]$TimeoutSec = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        Refresh-SessionPath
        $py = Find-Python
        if ($py) { return $py }
        Start-Sleep -Seconds 3
    }
    return $null
}

function Find-UnsupportedPython {
    foreach ($name in @("python3", "python")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            if ((Test-Python310Plus $name) -and -not (Test-PythonAinlCompatible $name)) {
                return $name
            }
        }
    }
    return $null
}

function Find-IncompatibleArm64Python {
    if (-not (Test-WindowsArm64Host)) { return $null }
    foreach ($ver in @("312", "311", "310")) {
        $localPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$ver-arm64\python.exe"
        if ((Test-Path -LiteralPath $localPy) -and (Test-PythonVersionSupported $localPy) -and (Test-PythonIsNativeArm64 $localPy)) {
            return $localPy
        }
    }
    return $null
}

function Reset-AinlVenvIfWrongArch {
    $venvDir = Get-AinlVenvDir
    $venvPy = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPy)) { return }
    if ((Test-WindowsArm64Host) -and (Test-PythonIsNativeArm64 $venvPy)) {
        Write-Host "  Removing ARM64 AINL venv (x64 Python required on Windows ARM)..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
    }
}

function Test-PythonExternallyManaged {
    param([string]$PyCmd)
    if (-not $PyCmd) { return $false }
    try {
        & $PyCmd -c "import sysconfig, pathlib; p=pathlib.Path(sysconfig.get_path('stdlib'))/'EXTERNALLY-MANAGED'; raise SystemExit(0 if p.is_file() else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Get-AinlVenvDir {
    if ($env:ARMARAOS_AINL_VENV) { return $env:ARMARAOS_AINL_VENV }
    return Join-Path $env:USERPROFILE ".armaraos\ainl-venv"
}

function Get-AinlHomeDir {
    if ($env:ARMARAOS_HOME) { return $env:ARMARAOS_HOME }
    if ($env:OPENFANG_HOME) { return $env:OPENFANG_HOME }
    return Join-Path $env:USERPROFILE ".armaraos"
}

function Write-AinlBinCache {
    param([string]$AinlExe)
    $homeDir = Get-AinlHomeDir
    if (-not (Test-Path $homeDir)) { New-Item -ItemType Directory -Path $homeDir -Force | Out-Null }
    $cache = Join-Path $homeDir ".armaraos-ainl-bin"
    # ASCII works on Windows PowerShell 5.1+ (paths are ASCII-safe on Windows).
    Set-Content -Path $cache -Value $AinlExe -Encoding ASCII
}

function Test-AinlCliRunnable {
    param([string]$AinlExe)
    if (-not $AinlExe -or -not (Test-Path $AinlExe)) { return $false }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $AinlExe --version 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
    finally { $ErrorActionPreference = $prev }
}

function Ensure-AinlCliReady {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptsDir,
        [Parameter(Mandatory = $true)][string]$AinlExe
    )
    Add-UserPathEntry $ScriptsDir
    Refresh-SessionPath
    Write-AinlBinCache $AinlExe
    if (Test-AinlCliRunnable $AinlExe) { return $true }
    # Second pass: PATH can lag until session refresh on some Windows builds.
    Refresh-SessionPath
    Start-Sleep -Milliseconds 400
    return (Test-AinlCliRunnable $AinlExe)
}

function Install-AinlViaVenv {
    param([string]$BasePy)
    Reset-AinlVenvIfWrongArch
    $venvDir = Get-AinlVenvDir
    $venvPy = Join-Path $venvDir "Scripts\python.exe"
    Write-Host "  Using isolated AINL environment at $venvDir" -ForegroundColor Cyan
    if (-not (Test-Path $venvPy)) {
        Write-Host "  Creating AINL virtualenv..." -ForegroundColor Cyan
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $BasePy -m venv $venvDir 2>&1 | Out-Null
        } finally {
            $ErrorActionPreference = $prev
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Error: could not create venv at $venvDir" -ForegroundColor Red
            exit 1
        }
        $venvPy = Join-Path $venvDir "Scripts\python.exe"
    }
    Write-Host "  Installing ainativelang[mcp] into venv..." -ForegroundColor Cyan
    $result = Invoke-PipInstall -Python $venvPy -PipArguments @('install', '--prefer-binary', '-q', 'ainativelang[mcp]')
    if (-not $result.Ok) {
        [void](Invoke-PipInstall -Python $venvPy -PipArguments @('install', '--upgrade', 'pip'))
        $result = Invoke-PipInstall -Python $venvPy -PipArguments @('install', '--prefer-binary', 'ainativelang[mcp]')
    }
    if (-not $result.Ok) {
        Write-Host "  pip install failed:" -ForegroundColor Red
        Write-Host $result.Log -ForegroundColor Red
        exit 1
    }
    $scriptsDir = Join-Path $venvDir "Scripts"
    $ainl = Join-Path $scriptsDir "ainl.exe"
    if (-not (Test-Path $ainl)) {
        Write-Host "  Error: AINL not found in venv at $ainl" -ForegroundColor Red
        exit 1
    }
    Add-UserPathEntry $scriptsDir
    if (-not (Ensure-AinlCliReady -ScriptsDir $scriptsDir -AinlExe $ainl)) {
        Write-Host "  Error: AINL installed but ainl.exe is not runnable at $ainl" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Registering AINL MCP server for ArmaraOS..." -ForegroundColor Cyan
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $ainl install-mcp --host armaraos 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Warning: ainl install-mcp returned exit code $LASTEXITCODE (re-run after install if MCP is missing)." -ForegroundColor Yellow
        }
    } finally {
        $ErrorActionPreference = $prev
    }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $verLine = (& $ainl --version 2>&1 | Select-Object -First 1) } catch { $verLine = "ainl" }
    finally { $ErrorActionPreference = $prev }
    Write-Host "  AINL ready in venv ($verLine)" -ForegroundColor Green
}

function Test-AinlCronShim {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        $head = Get-Content -LiteralPath $Path -TotalCount 30 -ErrorAction Stop
        $text = ($head -join "`n")
        return ($text -match 'REAL_AINL=' -or $text -match '--enable-adapter\s+http')
    } catch { return $false }
}

function Remove-LegacyArmaraosBinAinlShim {
    $homeDir = Get-AinlHomeDir
    $shim = Join-Path $homeDir 'bin\ainl'
    if (-not (Test-AinlCronShim $shim)) { return }
    $backup = Join-Path $homeDir 'bin\ainl.cron-shim.bak'
    if (Test-Path -LiteralPath $backup) {
        $backup = Join-Path $homeDir "bin\ainl.cron-shim.$([int][double]::Parse((Get-Date -UFormat %s))).bak"
    }
    Move-Item -LiteralPath $shim -Destination $backup -Force
    Write-Host "  Removed legacy ~/.armaraos/bin/ainl cron shim (saved as $(Split-Path -Leaf $backup))" -ForegroundColor Yellow
}

function Resolve-RepairAinlExecutable {
    $homeDir = Get-AinlHomeDir
    $venvAinl = Join-Path (Get-AinlVenvDir) 'Scripts\ainl.exe'
    if (Test-Path -LiteralPath $venvAinl) { return $venvAinl }
    $cache = Join-Path $homeDir '.armaraos-ainl-bin'
    if (Test-Path -LiteralPath $cache) {
        $cached = (Get-Content -LiteralPath $cache -TotalCount 1 -ErrorAction SilentlyContinue).Trim()
        if ($cached -and (Test-Path -LiteralPath $cached) -and -not (Test-AinlCronShim $cached)) {
            return $cached
        }
    }
    $cmd = Get-Command ainl -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source) -and -not (Test-AinlCronShim $cmd.Source)) {
        return $cmd.Source
    }
    return $null
}

function Repair-AinlLayout {
    $homeDir = Get-AinlHomeDir
    if (-not (Test-Path $homeDir)) { New-Item -ItemType Directory -Path $homeDir -Force | Out-Null }
    Remove-LegacyArmaraosBinAinlShim
    $ainl = Resolve-RepairAinlExecutable
    if (-not $ainl) {
        Write-Host '  AINL layout repair: no runnable ainl found (skipping MCP refresh)' -ForegroundColor Yellow
        return $false
    }
    Write-AinlBinCache $ainl
    if (-not (Test-AinlCliRunnable $ainl)) {
        Write-Host "  AINL layout repair: ainl at $ainl failed --version" -ForegroundColor Yellow
        return $false
    }
    Write-Host '  Refreshing AINL MCP registration...' -ForegroundColor Cyan
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $ainl install-mcp --host armaraos 2>&1 | Out-Null
    } finally { $ErrorActionPreference = $prev }
    $verLine = try { (& $ainl --version 2>&1 | Select-Object -First 1) } catch { 'ainl' }
    Write-Host "  AINL layout OK ($verLine)" -ForegroundColor Green
    return $true
}

function Test-WingetBenignExit {
    param([int]$Code)
    # 0 = ok; others = already installed / no update needed (winget still exit non-zero).
    return $Code -in @(0, -1978335189, -1978335135, -1978335134, -1978334963)
}

function Install-PythonViaWinget {
    param([string]$Reason = "missing")

    if ($env:ARMARAOS_AUTO_PYTHON -eq '0') { return $null }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $null }
    Write-Host ""
    if ($Reason -eq "unsupported") {
        Write-Host "  Python 3.14+ is on PATH but AINL needs 3.10-3.13 - trying winget for Python 3.12..." -ForegroundColor Yellow
    } else {
        Write-Host "  No compatible Python on PATH - trying winget for Python 3.12..." -ForegroundColor Yellow
    }
    $wingetExit = 0
    try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & winget install Python.Python.3.12 `
            --accept-package-agreements `
            --accept-source-agreements `
            --disable-interactivity `
            -h 2>&1 | Out-Null
        $wingetExit = $LASTEXITCODE
        if (-not (Test-WingetBenignExit $wingetExit)) {
            & winget install Python.Python.3.12 `
                --accept-package-agreements `
                --accept-source-agreements 2>&1 | Out-Null
            $wingetExit = $LASTEXITCODE
        }
        $ErrorActionPreference = $prev
    } catch {
        Write-Host "  winget install failed: $_" -ForegroundColor Yellow
        return $null
    }

    Write-Host "  Waiting for Python 3.12 (up to 2 min)..." -ForegroundColor Cyan
    $installed = Wait-ForCompatiblePython -TimeoutSec 120
    if ($installed) {
        Write-Host "  Python ready: $(Get-PythonVersionLabel $installed)" -ForegroundColor Green
        return $installed
    }
    if (Test-WingetBenignExit $wingetExit) {
        Write-Host "  winget reported Python may already be installed, but it was not found on disk." -ForegroundColor Yellow
    } else {
        Write-Host "  winget exited with code $wingetExit." -ForegroundColor Yellow
    }
    return $null
}

function Get-PythonInstallerArchCandidates {
    # On Windows ARM, AINL/MCP deps (cryptography, etc.) need x64 wheels under emulation.
    return @("amd64")
}

function Install-PythonViaOfficialInstaller {
    $version = if ($env:ARMARAOS_PYTHON_VERSION) { $env:ARMARAOS_PYTHON_VERSION.Trim() } else { "3.12.9" }
    $targetDir = Join-Path $env:USERPROFILE ".armaraos\python312"

    Write-Host ""
    Write-Host "  Downloading Python $version from python.org..." -ForegroundColor Cyan

    foreach ($arch in (Get-PythonInstallerArchCandidates)) {
        $installerName = "python-$version-$arch.exe"
        $url = "https://www.python.org/ftp/python/$version/$installerName"
        $dest = Join-Path $env:TEMP "armaraos-$installerName"
        try {
            Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
        } catch {
            Write-Host "  Could not download $url" -ForegroundColor Yellow
            continue
        }

        if (Test-Path -LiteralPath $targetDir) {
            Remove-Item -Recurse -Force $targetDir -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

        $installArgs = @(
            "/quiet",
            "InstallAllUsers=0",
            "Include_test=0",
            "Include_pip=1",
            "Include_launcher=1",
            "PrependPath=0",
            "TargetDir=$targetDir"
        )
        Write-Host "  Installing Python $version ($arch) to $targetDir ..." -ForegroundColor Cyan
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $proc = Start-Process -FilePath $dest -ArgumentList $installArgs -Wait -PassThru
        } finally {
            $ErrorActionPreference = $prev
        }
        Remove-Item -Force $dest -ErrorAction SilentlyContinue

        $py = Join-Path $targetDir "python.exe"
        if ((Test-Path -LiteralPath $py) -and (Test-PythonAinlCompatible $py)) {
            Write-Host "  Python ready: $(Get-PythonVersionLabel $py)" -ForegroundColor Green
            return $py
        }
        Write-Host "  Installer $arch finished (exit $($proc.ExitCode)) but python.exe was not found at $py" -ForegroundColor Yellow
    }
    return $null
}

function Ensure-CompatiblePython {
    $py = Find-Python
    if ($py) {
        Write-Host "  Found compatible Python on PATH." -ForegroundColor Green
        return $py
    }

    $armPy = Find-IncompatibleArm64Python
    if ($armPy) {
        Write-Host "  Native ARM64 Python ($(Get-PythonVersionLabel $armPy)) cannot install AINL deps (no prebuilt wheels)." -ForegroundColor Yellow
        Write-Host "  Installing x64 Python 3.12 for AINL (Windows x64 emulation, same as ArmaraOS CLI)..." -ForegroundColor Yellow
        $py = Install-PythonViaOfficialInstaller
        if ($py) { return $py }
    }

    $unsupported = Find-UnsupportedPython
    if ($unsupported) {
        $ver = Get-PythonVersionLabel $unsupported
        Write-Host "  Found Python $ver but AINL needs 3.10-3.13." -ForegroundColor Yellow
        $py = Install-PythonViaWinget -Reason "unsupported"
    } else {
        $py = Install-PythonViaWinget -Reason "missing"
    }

    if (-not $py) { $py = Find-Python }
    if (-not $py) { $py = Install-PythonViaOfficialInstaller }
    if (-not $py) { $py = Find-Python }
    return $py
}

function Show-PythonHelp {
    param([string]$UnsupportedVersion = "")

    Write-Host ""
    if ($UnsupportedVersion) {
        Write-Host "  Python $UnsupportedVersion is too new - AINL needs Python 3.10 through 3.13." -ForegroundColor Red
    } else {
        Write-Host "  Install incomplete: Python 3.10-3.13 is required for AINL (ainativelang[mcp])." -ForegroundColor Red
    }
    Write-Host "  ArmaraOS requires AINL - finish setup after Python is ready, then re-run this installer." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Easiest options on Windows:" -ForegroundColor Yellow
    Write-Host "    * Desktop .msi (bundled Python): https://ainativelang.com/armaraos"
    Write-Host "    * Official installer (auto): re-run irm https://ainativelang.com/install.ps1 | iex"
    Write-Host "    * Manual: https://www.python.org/downloads/ (install 3.12.x, then re-run)"
    Write-Host ""
    Write-Host "  Then open a new PowerShell and re-run:" -ForegroundColor Cyan
    Write-Host "    irm https://ainativelang.com/install.ps1 | iex"
    Write-Host ""
}

function Install-Ainl {
    param([string]$Py)

    Write-Host ""
    Write-Host "  Installing AINL (ainativelang[mcp])..." -ForegroundColor Cyan

    if (-not (Test-PythonAinlCompatible $Py)) {
        $ver = Get-PythonVersionLabel $Py
        Write-Host "  Error: Python $ver is not supported - AINL needs 3.10 through 3.13." -ForegroundColor Red
        Show-PythonHelp -UnsupportedVersion $ver
        exit 1
    }

    $pyVer = Get-PythonVersionLabel $Py
    Write-Host "  Using Python $pyVer ($Py)" -ForegroundColor Green
    Install-AinlViaVenv -BasePy $Py
}

function Get-ConfigApiListen {
    $default = "127.0.0.1:50051"
    $config = Join-Path (Get-ArmaraosHomeDir) "config.toml"
    if (-not (Test-Path -LiteralPath $config)) { return $default }
    foreach ($line in Get-Content -LiteralPath $config -ErrorAction SilentlyContinue) {
        if ($line -match '^\s*api_listen\s*=\s*"([^"]+)"') {
            return $Matches[1].Replace('0.0.0.0', '127.0.0.1')
        }
    }
    return $default
}

function Get-DaemonBaseUrl {
    $default = "http://$(Get-ConfigApiListen)"
    $dj = Join-Path $env:USERPROFILE ".armaraos\daemon.json"
    if (-not (Test-Path $dj)) { return $default }
    try {
        $info = Get-Content $dj -Raw | ConvertFrom-Json
        $addr = [string]$info.listen_addr
        if (-not $addr) { return $default }
        $addr = $addr.Replace("0.0.0.0", "127.0.0.1")
        return "http://$addr"
    } catch {
        return $default
    }
}

function Get-DaemonStartTimeoutSec {
    $raw = if ($env:ARMARAOS_DAEMON_START_TIMEOUT) { $env:ARMARAOS_DAEMON_START_TIMEOUT } else { "45" }
    $n = 0
    if ([int]::TryParse("$raw".Trim(), [ref]$n) -and $n -gt 0) { return $n }
    return 45
}

function Get-InstallDaemonBudgetSec {
    $raw = if ($env:ARMARAOS_INSTALL_DAEMON_BUDGET) { $env:ARMARAOS_INSTALL_DAEMON_BUDGET } else { "120" }
    $n = 0
    if ([int]::TryParse("$raw".Trim(), [ref]$n) -and $n -gt 0) { return $n }
    return 120
}

function Get-InstallDaemonGraceSec {
    $raw = if ($env:ARMARAOS_INSTALL_DAEMON_GRACE_SEC) { $env:ARMARAOS_INSTALL_DAEMON_GRACE_SEC } else { "15" }
    $n = 0
    if ([int]::TryParse("$raw".Trim(), [ref]$n) -and $n -ge 0) { return $n }
    return 15
}

function Get-ArmaraosHomeDir {
    if ($env:ARMARAOS_HOME) { return $env:ARMARAOS_HOME }
    if ($env:OPENFANG_HOME) { return $env:OPENFANG_HOME }
    return Join-Path $env:USERPROFILE ".armaraos"
}

function Get-DaemonJsonInfo {
    $dj = Join-Path (Get-ArmaraosHomeDir) "daemon.json"
    if (-not (Test-Path -LiteralPath $dj)) { return $null }
    try { return (Get-Content -LiteralPath $dj -Raw | ConvertFrom-Json) } catch { return $null }
}

function Test-ArmaraosProcessRunning {
    foreach ($name in @('armaraos', 'openfang')) {
        if (Get-Process -Name $name -ErrorAction SilentlyContinue) { return $true }
    }
    return $false
}

function Test-PortListening {
    param([int]$Port = 4200)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        return [bool]$conn
    } catch {
        $pattern = ":$Port\s"
        return [bool](netstat -an 2>$null | Select-String -Pattern $pattern -Quiet)
    }
}

function Get-ArmaraosLogTail {
    param([int]$Lines = 6)
    $homeDir = Get-ArmaraosHomeDir
    foreach ($rel in @('logs\daemon.log', 'logs\tui.log', 'tui.log')) {
        $p = Join-Path $homeDir $rel
        if (Test-Path -LiteralPath $p) {
            return @(Get-Content -LiteralPath $p -Tail $Lines -ErrorAction SilentlyContinue)
        }
    }
    return @()
}

function Get-DaemonListenPort {
    param([string]$Base = $(Get-DaemonBaseUrl))
    if ($Base -match ':(\d+)(?:/|$)') { return [int]$Matches[1] }
    return 4200
}

function Diagnose-DaemonLaunch {
    param(
        [string]$Exe,
        [string]$Base = $(Get-DaemonBaseUrl)
    )
    $findings = New-Object System.Collections.Generic.List[string]
    $hints = New-Object System.Collections.Generic.List[string]
    $port = Get-DaemonListenPort -Base $Base

    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe)) {
        [void]$findings.Add("CLI binary not found at the install path")
        [void]$hints.Add("Re-run the installer; check Windows Security / antivirus quarantine for armaraos.exe")
        return @{ Findings = $findings; Hints = $hints; LogTail = @() }
    }

    $ver = Invoke-ExternalWithTimeout -FilePath $Exe -ArgumentList @('--version') -TimeoutSec 12
    if ($ver.TimedOut) {
        [void]$findings.Add("armaraos --version timed out (antivirus may be scanning the new binary)")
        [void]$hints.Add("Allow $Exe in Windows Security / Defender, then run: armaraos --version")
    } elseif (-not $ver.Ok) {
        [void]$findings.Add("armaraos --version failed (exit $($ver.ExitCode))")
        [void]$hints.Add("Antivirus or permissions may block the binary — add an exclusion for $(Split-Path $Exe -Parent)")
    }

    $healthy = Test-DaemonHealthy -Base $Base
    $procRunning = Test-ArmaraosProcessRunning
    $portListen = Test-PortListening -Port $port

    if ($healthy) {
        [void]$findings.Add("Daemon is healthy at $Base")
        [void]$hints.Add("Open dashboard: armaraos dashboard")
        return @{ Findings = $findings; Hints = $hints; LogTail = @() }
    }

    if ($procRunning -and -not $healthy) {
        [void]$findings.Add("ArmaraOS process is running but /api/health did not respond yet")
        [void]$hints.Add("Wait a few seconds, then: armaraos status")
        [void]$hints.Add("If stuck: armaraos stop  then  armaraos start --yolo --detach")
    } elseif (-not $procRunning -and $portListen) {
        [void]$findings.Add("Port $port is in use by another program")
        [void]$hints.Add("Stop the other service or change api_listen in ~/.armaraos/config.toml")
    } elseif (-not $procRunning) {
        [void]$findings.Add("No armaraos process detected")
        [void]$hints.Add("Start manually: armaraos start --yolo --detach")
        [void]$hints.Add("If nothing starts, run: armaraos doctor --repair")
        [void]$hints.Add("First boot can take 30-60s under antivirus scan — that is normal")
    }

    $info = Get-DaemonJsonInfo
    if ($info -and $info.pid) {
        $alive = Get-Process -Id ([int]$info.pid) -ErrorAction SilentlyContinue
        if (-not $alive) {
            [void]$findings.Add("Stale daemon.json (PID $($info.pid) is not running)")
            [void]$hints.Add("Run: armaraos stop  then  armaraos start --yolo --detach")
        }
    }

    $logTail = Get-ArmaraosLogTail
    if ($logTail.Count -gt 0) {
        [void]$findings.Add("Log file present under $(Join-Path (Get-ArmaraosHomeDir) 'logs')")
    } else {
        [void]$findings.Add("No daemon log yet — boot may not have started")
    }

    return @{ Findings = $findings; Hints = $hints; LogTail = $logTail }
}

function Write-DaemonLaunchReport {
    param(
        [ValidateSet('success', 'failed', 'skipped')]
        [string]$Status,
        [hashtable]$Diagnosis = @{}
    )
    Write-Host ""
    Write-Host "  ── Daemon launch ──" -ForegroundColor Cyan
    switch ($Status) {
        'success' {
            Write-Host "  Status: RUNNING" -ForegroundColor Green
            Write-Host "  Dashboard: $((Get-DaemonBaseUrl).TrimEnd('/'))/" -ForegroundColor Green
        }
        'failed' {
            Write-Host "  Status: NOT READY (install finished — CLI + AINL are installed)" -ForegroundColor Yellow
            if ($Diagnosis.Findings -and $Diagnosis.Findings.Count -gt 0) {
                Write-Host "  Detected:" -ForegroundColor DarkCyan
                foreach ($f in $Diagnosis.Findings) {
                    Write-Host "    • $f" -ForegroundColor Gray
                }
            }
            if ($Diagnosis.Hints -and $Diagnosis.Hints.Count -gt 0) {
                Write-Host "  Next steps:" -ForegroundColor DarkCyan
                $n = 1
                foreach ($h in ($Diagnosis.Hints | Select-Object -Unique)) {
                    Write-Host "    $n. $h" -ForegroundColor Yellow
                    $n++
                }
            }
            if ($Diagnosis.LogTail -and $Diagnosis.LogTail.Count -gt 0) {
                Write-Host "  Recent log:" -ForegroundColor DarkCyan
                foreach ($line in $Diagnosis.LogTail) {
                    Write-Host "    $line" -ForegroundColor DarkGray
                }
            }
            Write-Host "  Logs: $(Join-Path (Get-ArmaraosHomeDir) 'logs\daemon.log')" -ForegroundColor DarkGray
        }
        'skipped' {
            Write-Host "  Status: SKIPPED (ARMARAOS_SKIP_AUTO_LAUNCH=1)" -ForegroundColor Gray
        }
    }
    Write-Host ""
}

function Test-DaemonHealthy {
    param([string]$Base = $(Get-DaemonBaseUrl))
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $uri = "$($Base.TrimEnd('/'))/api/health"
        $r = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Wait-DaemonHealthy {
    param(
        [string]$Base,
        [int]$TimeoutSec = 45,
        [Nullable[datetime]]$Deadline = $null,
        [string]$Label = "daemon"
    )
    $deadline = if ($Deadline) { $Deadline.Value } else { (Get-Date).AddSeconds($TimeoutSec) }
    $started = Get-Date
    $lastProgress = -5
    while ((Get-Date) -lt $deadline) {
        $checkBase = Get-DaemonBaseUrl
        if (Test-DaemonHealthy -Base $checkBase) {
            $elapsed = [Math]::Max(1, [int]((Get-Date) - $started).TotalSeconds)
            Write-Host "  $Label ready after ${elapsed}s ($checkBase)" -ForegroundColor Green
            return $true
        }
        $elapsed = [int]((Get-Date) - $started).TotalSeconds
        $left = [Math]::Max(0, [int]($deadline - (Get-Date)).TotalSeconds)
        if ($elapsed - $lastProgress -ge 5) {
            $lastProgress = $elapsed
            Write-Host "  Waiting for $Label... ${elapsed}s elapsed (${left}s left, checking $($checkBase.TrimEnd('/'))/api/health)" -ForegroundColor DarkCyan
        }
        Start-Sleep -Seconds 1
    }
    $finalBase = Get-DaemonBaseUrl
    Write-Host "  Timed out waiting for $Label ($($finalBase.TrimEnd('/'))/api/health)" -ForegroundColor Yellow
    return $false
}

function Invoke-ExternalWithTimeout {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int]$TimeoutSec = 60
    )
    if (-not (Test-Path -LiteralPath $FilePath)) {
        return @{ Ok = $false; TimedOut = $false; ExitCode = 127 }
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = ($ArgumentList | ForEach-Object {
        if ($_ -match '\s|"') { '"' + ($_.Replace('"', '\"')) + '"' } else { $_ }
    }) -join ' '
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    if (-not $proc) {
        return @{ Ok = $false; TimedOut = $false; ExitCode = 1 }
    }
    $ms = [Math]::Max(1000, $TimeoutSec * 1000)
    if (-not $proc.WaitForExit($ms)) {
        try { $proc.Kill() } catch { }
        return @{ Ok = $false; TimedOut = $true; ExitCode = -1 }
    }
    return @{ Ok = ($proc.ExitCode -eq 0); TimedOut = $false; ExitCode = $proc.ExitCode }
}

function Start-DaemonDetachedProcess {
    param([Parameter(Mandatory = $true)][string]$Exe)
    # Do not wait on `armaraos start --detach` — it polls health internally for up to 45s.
    Start-Process -FilePath $Exe -ArgumentList @('start', '--yolo', '--detach') -WindowStyle Hidden | Out-Null
}

function Repair-ConfigTomlWindowsPaths {
    $configPath = Join-Path (Join-Path $env:USERPROFILE ".armaraos") "config.toml"
    if (-not (Test-Path -LiteralPath $configPath)) { return $false }

    $raw = [System.IO.File]::ReadAllText($configPath)
    $endsWithNewline = $raw.EndsWith("`n") -or $raw.EndsWith("`r`n")
    $lines = $raw -split "`r?`n", -1
    $keys = @('command', 'path', 'root', 'cwd')
    $changed = $false
    $out = New-Object System.Collections.Generic.List[string]

    foreach ($line in $lines) {
        $trim = $line.Trim()
        if ($trim -notmatch '=' -or $trim -notmatch '"') {
            [void]$out.Add($line)
            continue
        }
        $key = ($trim -split '=', 2)[0].Trim()
        if ($keys -notcontains $key) {
            [void]$out.Add($line)
            continue
        }
        $eqIdx = $line.IndexOf('=')
        if ($eqIdx -lt 0) {
            [void]$out.Add($line)
            continue
        }
        $afterEq = $line.Substring($eqIdx + 1).TrimStart()
        if (-not $afterEq.StartsWith('"')) {
            [void]$out.Add($line)
            continue
        }
        $valueStart = $line.IndexOf('"', $eqIdx)
        if ($valueStart -lt 0) {
            [void]$out.Add($line)
            continue
        }
        $endRel = $line.Substring($valueStart + 1).LastIndexOf('"')
        if ($endRel -lt 0) {
            [void]$out.Add($line)
            continue
        }
        $valueEnd = $valueStart + 1 + $endRel
        $inner = $line.Substring($valueStart + 1, $endRel)
        if ($inner -notmatch '\\') {
            [void]$out.Add($line)
            continue
        }
        $fixedInner = $inner -replace '\\', '/'
        $changed = $true
        [void]$out.Add($line.Substring(0, $valueStart + 1) + $fixedInner + $line.Substring($valueEnd))
    }

    if (-not $changed) { return $false }

    $joined = ($out -join "`n")
    if ($endsWithNewline -and -not $joined.EndsWith("`n")) {
        $joined += "`n"
    }
    [System.IO.File]::WriteAllText($configPath, $joined)
    Write-Host ""
    Write-Host "  Repaired Windows path escaping in config.toml (MCP command paths)" -ForegroundColor Yellow
    return $true
}

function Invoke-ArmaraosDoctorRepair {
    param(
        [string]$Exe,
        [int]$TimeoutSec = 60
    )
    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe)) { return $false }
    $env:ARMARAOS_NONINTERACTIVE = "1"
    $result = Invoke-ExternalWithTimeout -FilePath $Exe -ArgumentList @('doctor', '--repair') -TimeoutSec $TimeoutSec
    if ($result.TimedOut) {
        Write-Host "  Warning: armaraos doctor --repair timed out after ${TimeoutSec}s (continuing install)." -ForegroundColor Yellow
        return $false
    }
    return [bool]$result.Ok
}

function Repair-ArmaraosInstall {
    param([string]$Exe)

    $ofHome = Join-Path $env:USERPROFILE ".armaraos"
    foreach ($sub in @("data", "agents", "logs")) {
        $p = Join-Path $ofHome $sub
        if (-not (Test-Path $p)) {
            New-Item -ItemType Directory -Path $p -Force | Out-Null
        }
    }
    $config = Join-Path $ofHome "config.toml"
    if (-not (Test-Path $config)) {
        Write-Host "  Repair: first-time setup (armaraos init --quick)..." -ForegroundColor Yellow
        Invoke-ExternalWithTimeout -FilePath $Exe -ArgumentList @('init', '--quick') -TimeoutSec 60 | Out-Null
    }
    Repair-ConfigTomlWindowsPaths | Out-Null
    Invoke-ArmaraosDoctorRepair -Exe $Exe -TimeoutSec 60 | Out-Null
    Invoke-ExternalWithTimeout -FilePath $Exe -ArgumentList @('stop') -TimeoutSec 15 | Out-Null
    Start-Sleep -Seconds 1
}

function Start-ArmaraosDaemon {
    param(
        [string]$Exe,
        [Nullable[datetime]]$Deadline = $null
    )

    $budgetDeadline = if ($Deadline) { $Deadline.Value } else { (Get-Date).AddSeconds((Get-InstallDaemonBudgetSec)) }
    $base = Get-DaemonBaseUrl

    if (Test-DaemonHealthy -Base $base) {
        Write-Host "  Daemon already healthy at $base" -ForegroundColor Green
        return $true
    }

    Write-Host ""
    Write-Host "  Starting ArmaraOS daemon (background, non-blocking)..." -ForegroundColor Cyan
    Write-Host "  (First boot can take up to $((Get-InstallDaemonBudgetSec))s — progress updates every 5s)" -ForegroundColor DarkGray
    Start-DaemonDetachedProcess -Exe $Exe
    if (Wait-DaemonHealthy -Base $base -Deadline $budgetDeadline -Label "daemon") { return $true }

    $diag = Diagnose-DaemonLaunch -Exe $Exe -Base $base
    if ($diag.Findings -and $diag.Findings.Count -gt 0) {
        Write-Host "  Quick check:" -ForegroundColor DarkCyan
        foreach ($f in $diag.Findings | Select-Object -First 3) {
            Write-Host "    • $f" -ForegroundColor Gray
        }
    }

    if ($env:ARMARAOS_SKIP_INSTALL_REPAIR -eq "1") {
        Write-Host "  Repair skipped (ARMARAOS_SKIP_INSTALL_REPAIR=1)." -ForegroundColor Yellow
        return $false
    }

    $remaining = [Math]::Max(0, [int]($budgetDeadline - (Get-Date)).TotalSeconds)
    if ($remaining -lt 12) {
        Write-Host "  No time left for repair retry in this install window." -ForegroundColor Yellow
        return $false
    }

    Write-Host "  Repairing install state and retrying (up to ${remaining}s left)..." -ForegroundColor Yellow
    Repair-ArmaraosInstall -Exe $Exe
    Start-DaemonDetachedProcess -Exe $Exe
    Wait-DaemonHealthy -Base (Get-DaemonBaseUrl) -Deadline $budgetDeadline -Label "daemon (retry)"
}

function Open-ArmaraosDashboard {
    param(
        [string]$Exe,
        [Nullable[datetime]]$Deadline = $null
    )

    $base = Get-DaemonBaseUrl
    Write-Host ""
    Write-Host "  Opening dashboard in your browser..." -ForegroundColor Cyan

    if (Test-DaemonHealthy -Base $base) {
        try {
            Start-Process "$($base.TrimEnd('/'))/" | Out-Null
            return $true
        } catch {
            Write-Host "  Browser did not open — visit: $base/" -ForegroundColor Yellow
            return $false
        }
    }

    $remaining = if ($Deadline) {
        [Math]::Max(5, [int]($Deadline.Value - (Get-Date)).TotalSeconds)
    } else { 30 }
    $result = Invoke-ExternalWithTimeout -FilePath $Exe -ArgumentList @('dashboard') -TimeoutSec $remaining
    $base = Get-DaemonBaseUrl
    if ($result.TimedOut) {
        Write-Host "  Dashboard command timed out — visit: $base/" -ForegroundColor Yellow
        return (Test-DaemonHealthy -Base $base)
    }
    if (-not $result.Ok -and -not (Test-DaemonHealthy -Base $base)) {
        Write-Host "  Browser did not open — visit: $base/" -ForegroundColor Yellow
        return $false
    }
    return $true
}

# Golden path (Windows + Mac/Linux install.sh): start daemon, verify /api/health, repair + retry, open dashboard.
function Launch-ArmaraosAfterInstall {
    if ($env:ARMARAOS_SKIP_AUTO_LAUNCH -eq "1") {
        Write-DaemonLaunchReport -Status 'skipped'
        return "skipped"
    }

    $exe = Get-ArmaraosExe
    if (-not $exe) {
        Write-DaemonLaunchReport -Status 'failed' -Diagnosis (Diagnose-DaemonLaunch -Exe "")
        return "failed"
    }

    $deadline = (Get-Date).AddSeconds((Get-InstallDaemonBudgetSec))
    $base = Get-DaemonBaseUrl
    $healthy = Test-DaemonHealthy -Base $base

    if (-not $healthy) {
        $healthy = Start-ArmaraosDaemon -Exe $exe -Deadline $deadline
    } else {
        Write-Host ""
        Write-Host "  Daemon already running." -ForegroundColor Green
    }

    if (-not $healthy) {
        $grace = Get-InstallDaemonGraceSec
        if ($grace -gt 0) {
            Write-Host ""
            Write-Host "  Final recheck (${grace}s) — daemon may still be starting..." -ForegroundColor DarkCyan
            $graceDeadline = (Get-Date).AddSeconds($grace)
            $healthy = Wait-DaemonHealthy -Base (Get-DaemonBaseUrl) -Deadline $graceDeadline -Label "daemon (recheck)"
        }
    }

    if ($healthy) {
        Write-Host "  Daemon is running." -ForegroundColor Green
    }

    Open-ArmaraosDashboard -Exe $exe -Deadline $deadline | Out-Null

    if (-not $healthy -and (Test-DaemonHealthy -Base (Get-DaemonBaseUrl))) {
        $healthy = $true
        Write-Host "  Daemon became healthy during dashboard open." -ForegroundColor Green
    }

    $diag = Diagnose-DaemonLaunch -Exe $exe -Base (Get-DaemonBaseUrl)
    if ($healthy) {
        Write-DaemonLaunchReport -Status 'success' -Diagnosis $diag
        return "success"
    }
    Write-DaemonLaunchReport -Status 'failed' -Diagnosis $diag
    return "failed"
}

function Show-GetStarted {
    param(
        [string]$DesktopShortcut = "",
        [ValidateSet("success", "failed", "skipped")]
        [string]$LaunchResult = "skipped"
    )

    Write-Host ""
    Write-Host "  You're ready!" -ForegroundColor Cyan
    if ($LaunchResult -eq "success") {
        Write-Host "  Your browser should show the dashboard (setup wizard on first visit)." -ForegroundColor Green
        Write-Host "  You can close this window — the daemon keeps running." -ForegroundColor Green
    } elseif ($LaunchResult -eq "failed") {
        Write-Host "  See the Daemon launch report above for detected issues and next steps." -ForegroundColor Yellow
        Write-Host "  Quick retry: armaraos start --yolo --detach  then  armaraos dashboard" -ForegroundColor Green
    } else {
        Write-Host "  Open the dashboard: armaraos dashboard" -ForegroundColor Green
        Write-Host "  (starts the daemon if needed, then opens your browser)" -ForegroundColor Green
    }
    if ($DesktopShortcut) {
        Write-Host "  Next time: double-click ArmaraOS Dashboard on your desktop." -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "  Verify anytime: armaraos doctor"
    Write-Host "  Upgrade CLI:    armaraos update"
    Write-Host ""
}

function Get-ArmaraosExe {
    $exe = Join-Path $InstallDir "armaraos.exe"
    if (Test-Path $exe) { return $exe }
    return $null
}

function Stop-ArmaraosForInstall {
    $exe = Get-ArmaraosExe
    if ($exe) {
        & $exe stop 2>$null | Out-Null
    }
    foreach ($name in @('armaraos', 'openfang')) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

function Install-ArmaraosBinary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceExe
    )

    $dest = Join-Path $InstallDir "armaraos.exe"
    Stop-ArmaraosForInstall

    try {
        Copy-Item -Path $SourceExe -Destination $dest -Force -ErrorAction Stop
        return
    } catch {
        Write-Host "  Binary locked (Access is denied) — staging deferred install..." -ForegroundColor Yellow
    }

    $staged = Join-Path $InstallDir "armaraos.exe.new"
    Copy-Item -Path $SourceExe -Destination $staged -Force
    $parentPid = $PID
    $scriptPath = Join-Path $env:TEMP "armaraos-install-$parentPid.cmd"
    $legacy = Join-Path $InstallDir "openfang.exe"
    $script = @"
@echo off
setlocal EnableExtensions
:wait
tasklist /FI "PID eq $parentPid" 2>NUL | find "$parentPid" >NUL
if not errorlevel 1 (timeout /t 1 /nobreak >NUL & goto wait)
move /Y "$staged" "$dest"
"@
    if (Test-Path $legacy) {
        $script += "copy /Y `"$dest`" `"$legacy`" >NUL`r`n"
    }
    $script += "del `"%~f0`"`r`n"
    Set-Content -Path $scriptPath -Value $script -Encoding ASCII
    Start-Process -FilePath "cmd.exe" -ArgumentList "/C", $scriptPath -WindowStyle Hidden | Out-Null
    Write-Host "  Install will finish after this PowerShell window closes." -ForegroundColor Green
    Write-Host "  Close this window, wait a few seconds, open a new one, then run: armaraos --version" -ForegroundColor Yellow
    exit 0
}

function Initialize-ArmaraosIfNeeded {
    $exe = Get-ArmaraosExe
    if (-not $exe) { return }
    $configPath = Join-Path $env:USERPROFILE ".armaraos\config.toml"
    if (Test-Path $configPath) { return }
    Write-Host ""
    Write-Host "  First-time setup (armaraos init --quick)..." -ForegroundColor Cyan
    $init = Invoke-ExternalWithTimeout -FilePath $exe -ArgumentList @('init', '--quick') -TimeoutSec 60
    if ($init.TimedOut) {
        Write-Host "  Warning: init --quick timed out — run it manually before opening the dashboard." -ForegroundColor Yellow
    } elseif (-not $init.Ok) {
        Write-Host "  Warning: init --quick did not complete — run it manually before opening the dashboard." -ForegroundColor Yellow
    }
}

function Install-DashboardShortcut {
    $exe = Get-ArmaraosExe
    if (-not $exe) { return "" }

    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop -or -not (Test-Path $desktop)) { return "" }

    $shortcutPath = Join-Path $desktop "ArmaraOS Dashboard.lnk"
    try {
        $wsh = New-Object -ComObject WScript.Shell
        $shortcut = $wsh.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $exe
        $shortcut.Arguments = "dashboard"
        $shortcut.WorkingDirectory = $InstallDir
        $shortcut.Description = "Open ArmaraOS dashboard (starts daemon if needed)"
        $shortcut.Save()
        Write-Host ""
        Write-Host "  Created desktop shortcut: ArmaraOS Dashboard" -ForegroundColor Green
        return $shortcutPath
    } catch {
        Write-Host ""
        Write-Host "  Could not create desktop shortcut — run: armaraos dashboard" -ForegroundColor Yellow
        return ""
    }
}

function Get-Architecture {
    $arch = ""
    try { $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() } catch {}
    if (-not $arch) { try { $arch = $env:PROCESSOR_ARCHITECTURE } catch {} }
    if (-not $arch) {
        try {
            $wmiArch = (Get-CimInstance Win32_Processor).Architecture
            if ($wmiArch -eq 9) { $arch = "AMD64" }
            elseif ($wmiArch -eq 12) { $arch = "ARM64" }
        } catch {}
    }
    if (-not $arch -and [IntPtr]::Size -eq 8) { $arch = "X64" }
    switch ("$arch".ToUpper().Trim()) {
        { $_ -in "X64", "AMD64", "X86_64" } { return "x86_64" }
        { $_ -in "ARM64", "AARCH64", "ARM" } { return "aarch64" }
        default {
            Write-Host "  Unsupported architecture: $arch" -ForegroundColor Red
            exit 1
        }
    }
}

function Get-ManifestBaseCandidates {
    $bases = New-Object System.Collections.Generic.List[string]
    $add = {
        param([string]$Base)
        $b = "$Base".Trim().TrimEnd('/')
        if ($b -and -not $bases.Contains($b)) { [void]$bases.Add($b) }
    }
    if ($env:ARMARAOS_DOWNLOAD_BASE) { & $add $env:ARMARAOS_DOWNLOAD_BASE }
    & $add $DownloadBase
    & $add "https://ainativelang.com/downloads/armaraos/cli"
    & $add "https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli"
    return $bases
}

function Get-ManifestTag {
    param($Manifest)
    if (-not $Manifest) { return "" }
    if ($Manifest.tag) { return "$($Manifest.tag)".Trim() }
    if ($Manifest.version) { return "v$($Manifest.version)".Trim() }
    return ""
}

function Compare-ArmaraosReleaseTags {
    param([string]$Left, [string]$Right)
    $norm = {
        param([string]$Tag)
        $t = "$Tag".Trim()
        if ($t.StartsWith("v")) { $t = $t.Substring(1) }
        $parts = $t.Split(".")
        $nums = @()
        foreach ($p in $parts) {
            $n = 0
            [void][int]::TryParse(($p -replace '[^0-9].*$', ''), [ref]$n)
            $nums += $n
        }
        while ($nums.Count -lt 3) { $nums += 0 }
        return $nums
    }
    $a = & $norm $Left
    $b = & $norm $Right
    for ($i = 0; $i -lt 3; $i++) {
        if ($a[$i] -gt $b[$i]) { return 1 }
        if ($a[$i] -lt $b[$i]) { return -1 }
    }
    return 0
}

function Get-ManifestPlatformEntry {
    param($Manifest, [string]$PlatformKey)
    if (-not $Manifest -or -not $Manifest.platforms) { return $null }
    $prop = $Manifest.platforms.PSObject.Properties[$PlatformKey]
    if ($prop) { return $prop.Value }
    return $null
}

function Resolve-ManifestDownloadBase {
    param($Manifest, [string]$ManifestBase)
    $fromManifest = ""
    if ($Manifest -and $Manifest.download_base) {
        $fromManifest = "$($Manifest.download_base)".Trim().TrimEnd('/')
    }
    if ($fromManifest) { return $fromManifest }
    return $ManifestBase
}

function Get-CliManifest {
    if ($script:ArmaraosCliManifest) { return $script:ArmaraosCliManifest }

    $bestManifest = $null
    $bestTag = ""
    $bestBase = $DownloadBase

    foreach ($base in (Get-ManifestBaseCandidates)) {
        try {
            $cacheBust = [Guid]::NewGuid().ToString("n")
            $manifest = Invoke-RestMethod -Uri "$base/latest.json?cb=$cacheBust" -UseBasicParsing
            $tag = Get-ManifestTag $manifest
            if (-not $tag) { continue }
            if (-not $bestManifest -or (Compare-ArmaraosReleaseTags $tag $bestTag) -gt 0) {
                $bestManifest = $manifest
                $bestTag = $tag
                $bestBase = $base
            }
        } catch {
            continue
        }
    }

    if ($bestManifest) {
        $script:ArmaraosCliManifest = $bestManifest
        $script:ArmaraosResolvedDownloadBase = Resolve-ManifestDownloadBase -Manifest $bestManifest -ManifestBase $bestBase
        return $bestManifest
    }

    return $null
}

function Get-ResolvedDownloadBase {
    if (-not $script:ArmaraosResolvedDownloadBase) {
        $null = Get-CliManifest | Out-Null
    }
    if ($script:ArmaraosResolvedDownloadBase) { return $script:ArmaraosResolvedDownloadBase }
    return $DownloadBase
}

function Get-WindowsDownloadCandidates {
    param([string]$NativeArch)

    $manifest = Get-CliManifest
    $artifactBase = Get-ResolvedDownloadBase
    # Native ARM64 Windows builds may not be published yet; prefer x64 first (Windows emulation).
    $platformKeys = if ($NativeArch -eq "aarch64") {
        @("x86_64-pc-windows-msvc", "aarch64-pc-windows-msvc")
    } else {
        @("${NativeArch}-pc-windows-msvc")
    }

    $seen = @{}
    $candidates = @()

    foreach ($platformKey in $platformKeys) {
        if ($manifest) {
            $entry = Get-ManifestPlatformEntry -Manifest $manifest -PlatformKey $platformKey
            if ($entry -and $entry.archive -and -not $seen[$entry.archive]) {
                $seen[$entry.archive] = $true
                $candidates += [PSCustomObject]@{
                    PlatformKey = $platformKey
                    Archive     = $entry.archive
                    Url         = if ($entry.url) { $entry.url } else { "$artifactBase/$($entry.archive)" }
                    Sha256Url   = if ($entry.sha256_url) { $entry.sha256_url } else { "$artifactBase/$($entry.archive).sha256" }
                }
            }
        }

        $archive = "armaraos-$platformKey.zip"
        if ($seen[$archive]) { continue }
        $seen[$archive] = $true
        $candidates += [PSCustomObject]@{
            PlatformKey = $platformKey
            Archive     = $archive
            Url         = "$artifactBase/$archive"
            Sha256Url   = "$artifactBase/$archive.sha256"
        }
    }

    return $candidates
}

function Get-LatestVersion {
    if ($env:ARMARAOS_VERSION) { return $env:ARMARAOS_VERSION }
    if ($env:OPENFANG_VERSION) { return $env:OPENFANG_VERSION }
    Write-Host "  Fetching latest release from $DownloadBase/latest.json ..."
    $manifest = Get-CliManifest
    if ($manifest) {
        if ($manifest.tag) { return $manifest.tag }
        if ($manifest.version) { return "v$($manifest.version)" }
    }
    Write-Host "  Could not read $DownloadBase/latest.json" -ForegroundColor Red
    Write-Host "  Set `$env:ARMARAOS_VERSION=vX.Y.Z or retry after the next release syncs to ainativelang.com." -ForegroundColor Yellow
    exit 1
}

function Install-ArmaraOS {
    Write-Banner

    $arch = Get-Architecture
    $version = Get-LatestVersion
    $target = "${arch}-pc-windows-msvc"
    $downloadCandidates = Get-WindowsDownloadCandidates -NativeArch $arch

    Write-Host "  Installing ArmaraOS (CLI) $version for $target..."

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "armaraos-install-$([guid]::NewGuid().ToString('n'))"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $archivePath = $null
    $checksumUrl = $null
    $usedPlatform = $null

    foreach ($item in $downloadCandidates) {
        $candidatePath = Join-Path $tempDir $item.Archive
        try {
            Write-Host "  Downloading $($item.Archive)..." -ForegroundColor Cyan
            Invoke-WebRequest -Uri $item.Url -OutFile $candidatePath -UseBasicParsing
            if (-not (Test-Path -LiteralPath $candidatePath) -or (Get-Item -LiteralPath $candidatePath).Length -lt 1024) {
                throw "Download too small or missing: $($item.Url)"
            }
            $archivePath = $candidatePath
            $checksumUrl = $item.Sha256Url
            $usedPlatform = $item.PlatformKey
            break
        } catch {
            Write-Host "  Skipped $($item.Archive): $($_.Exception.Message)" -ForegroundColor DarkYellow
            continue
        }
    }
    if (-not $archivePath) {
        $tried = ($downloadCandidates | ForEach-Object { $_.PlatformKey } | Select-Object -Unique) -join ', '
        Write-Host "  Download failed (tried: $tried)." -ForegroundColor Red
        Write-Host "  If this is a fresh release, wait for ainativelang.com to sync CLI binaries." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
        exit 1
    }

    if ($arch -eq "aarch64" -and $usedPlatform -eq "x86_64-pc-windows-msvc") {
        Write-Host "  No native ARM64 build yet - using x64 package (Windows x64 emulation)." -ForegroundColor Yellow
    }

    try {
        $expectedHash = (Invoke-WebRequest -Uri $checksumUrl -UseBasicParsing).Content.Split(" ")[0].Trim().ToLower()
        $actualHash = (Get-FileHash $archivePath -Algorithm SHA256).Hash.ToLower()
        if ($expectedHash -ne $actualHash) {
            Write-Host "  Checksum verification FAILED!" -ForegroundColor Red
            exit 1
        }
        Write-Host "  Checksum verified." -ForegroundColor Green
    } catch {
        Write-Host "  Checksum file not available, skipping verification." -ForegroundColor Yellow
    }

    try {
        Expand-Archive -Path $archivePath -DestinationPath $tempDir -Force
    } catch {
        Write-Host "  Could not extract archive: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  URL was: $(($downloadCandidates | Where-Object { $_.Archive -eq (Split-Path -Leaf $archivePath) } | Select-Object -First 1).Url)" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
        exit 1
    }
    $exePath = Get-ChildItem -Path $tempDir -Filter "armaraos.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $exePath) {
        $exePath = Get-ChildItem -Path $tempDir -Filter "openfang.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (-not $exePath) {
        Write-Host "  Could not find armaraos.exe in archive." -ForegroundColor Red
        exit 1
    }

    Install-ArmaraosBinary -SourceExe $exePath.FullName
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue

    Add-UserPathEntry $InstallDir

    $installedExe = Join-Path $InstallDir "armaraos.exe"
    try {
        $versionOutput = & $installedExe --version 2>&1
        Write-Host ""
        Write-Host "  ArmaraOS CLI installed ($versionOutput)" -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "  ArmaraOS binary installed to $installedExe" -ForegroundColor Green
    }

    $py = Ensure-CompatiblePython
    if (-not $py) {
        $unsupported = Find-UnsupportedPython
        $ver = if ($unsupported) { Get-PythonVersionLabel $unsupported } else { "" }
        Show-PythonHelp -UnsupportedVersion $ver
        exit 1
    }

    $py = Resolve-PythonExecutable $py
    if (-not $py -or -not (Test-PythonAinlCompatible $py)) {
        $ver = if ($py) { Get-PythonVersionLabel $py } else { "unknown" }
        Write-Host "  Could not find a compatible Python (3.10-3.13) after install." -ForegroundColor Red
        Show-PythonHelp -UnsupportedVersion $ver
        exit 1
    }

    Install-Ainl -Py $py
    Repair-AinlLayout | Out-Null
    Initialize-ArmaraosIfNeeded
    Repair-ConfigTomlWindowsPaths | Out-Null
    $exe = Get-ArmaraosExe
    if ($exe) { Invoke-ArmaraosDoctorRepair -Exe $exe | Out-Null }
    $desktopShortcut = Install-DashboardShortcut
    $launchResult = Launch-ArmaraosAfterInstall
    Show-GetStarted -DesktopShortcut $desktopShortcut -LaunchResult $launchResult
}

Install-ArmaraOS
