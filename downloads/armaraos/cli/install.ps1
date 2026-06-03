# ArmaraOS installer for Windows
# Usage: irm https://ainativelang.com/install.ps1 | iex
#
# Environment variables:
#   $env:ARMARAOS_INSTALL_DIR  — custom install directory
#   $env:ARMARAOS_VERSION      — specific version tag
#   $env:ARMARAOS_AUTO_PYTHON  — set to 0 to skip winget Python install (default: 1)
#   $env:ARMARAOS_SKIP_AINL    — set to 1 to install only the ArmaraOS CLI
#
# Legacy: OPENFANG_INSTALL_DIR, OPENFANG_VERSION

$ErrorActionPreference = 'Stop'

$DownloadBase = if ($env:ARMARAOS_DOWNLOAD_BASE) { $env:ARMARAOS_DOWNLOAD_BASE.TrimEnd('/') } else { "https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli" }
$DefaultInstallDir = Join-Path $env:USERPROFILE ".armaraos\bin"
$InstallDir =
    if ($env:ARMARAOS_INSTALL_DIR) { $env:ARMARAOS_INSTALL_DIR }
    elseif ($env:OPENFANG_INSTALL_DIR) { $env:OPENFANG_INSTALL_DIR }
    else { $DefaultInstallDir }

function Write-Banner {
    Write-Host ""
    Write-Host "  ArmaraOS Installer" -ForegroundColor Cyan
    Write-Host "  ==================" -ForegroundColor Cyan
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
    try {
        & $PyCmd -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Find-Python {
    foreach ($name in @("python3.12", "python3.11", "python3.10", "python3", "python")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            if (Test-Python310Plus $name) { return $name }
        }
    }
    # Common per-user install location after winget
    foreach ($ver in @("312", "311", "310")) {
        $localPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$ver\python.exe"
        if ((Test-Path $localPy) -and (Test-Python310Plus $localPy)) { return $localPy }
    }
    return $null
}

function Get-AinlVenvDir {
    if ($env:ARMARAOS_AINL_VENV) { return $env:ARMARAOS_AINL_VENV }
    return Join-Path $env:USERPROFILE ".armaraos\ainl-venv"
}

function Test-PythonExternallyManaged {
    param([string]$PyCmd)
    if (-not $PyCmd) { return $false }
    try {
        & $PyCmd -c "import sysconfig, pathlib; p=pathlib.Path(sysconfig.get_path('stdlib'))/'EXTERNALLY-MANAGED'; raise SystemExit(0 if p.is_file() else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Install-AinlViaVenv {
    param([string]$BasePy)
    $venvDir = Get-AinlVenvDir
    $venvPy = Join-Path $venvDir "Scripts\python.exe"
    Write-Host "  System Python is externally managed — using venv at $venvDir" -ForegroundColor Yellow
    if (-not (Test-Path $venvPy)) {
        Write-Host "  Creating AINL virtualenv..." -ForegroundColor Cyan
        & $BasePy -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Error: could not create venv at $venvDir" -ForegroundColor Red
            exit 1
        }
        $venvPy = Join-Path $venvDir "Scripts\python.exe"
    }
    Write-Host "  Installing ainativelang[mcp] into venv..." -ForegroundColor Cyan
    & $venvPy -m pip install -q "ainativelang[mcp]" 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $venvPy -m pip install --upgrade pip | Out-Null
        & $venvPy -m pip install "ainativelang[mcp]"
    }
    $scriptsDir = Join-Path $venvDir "Scripts"
    $ainl = Join-Path $scriptsDir "ainl.exe"
    if (-not (Test-Path $ainl)) {
        Write-Host "  Error: AINL not found in venv at $ainl" -ForegroundColor Red
        exit 1
    }
    Add-UserPathEntry $scriptsDir
    Write-Host "  Registering AINL MCP server for ArmaraOS..." -ForegroundColor Cyan
    & $ainl install-mcp --host armaraos
    $verLine = try { (& $ainl --version 2>&1 | Select-Object -First 1) } catch { "ainl" }
    Write-Host "  AINL ready in venv ($verLine)" -ForegroundColor Green
}

function Install-PythonViaWinget {
    if ($env:ARMARAOS_AUTO_PYTHON -eq '0') { return $null }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $null }
    Write-Host ""
    Write-Host "  No Python 3.10+ on PATH — installing via winget (one-time)..." -ForegroundColor Yellow
    try {
        winget install Python.Python.3.12 `
            --accept-package-agreements `
            --accept-source-agreements `
            --disable-interactivity `
            -h 2>$null
        if ($LASTEXITCODE -ne 0) {
            winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        }
    } catch {
        Write-Host "  winget install failed: $_" -ForegroundColor Yellow
        return $null
    }
    Refresh-SessionPath
    Start-Sleep -Seconds 2
    return Find-Python
}

function Show-PythonHelp {
    Write-Host ""
    Write-Host "  Python 3.10+ is required for AINL (ainativelang[mcp])." -ForegroundColor Red
    Write-Host "  The ArmaraOS CLI is already installed — finish AINL after Python is ready." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Easiest options on Windows:" -ForegroundColor Yellow
    Write-Host "    • Desktop .msi (bundled Python): https://ainativelang.com/armaraos"
    Write-Host "    • winget:  winget install Python.Python.3.12"
    Write-Host "    • Official: https://www.python.org/downloads/ (check Add python.exe to PATH)"
    Write-Host ""
    Write-Host "  Then open a new PowerShell and re-run:" -ForegroundColor Cyan
    Write-Host "    irm https://ainativelang.com/install.ps1 | iex"
    Write-Host ""
    Write-Host "  CLI-only (skip AINL for now):" -ForegroundColor Cyan
    Write-Host '    $env:ARMARAOS_SKIP_AINL=1; irm https://ainativelang.com/install.ps1 | iex'
    Write-Host ""
}

function Install-Ainl {
    param([string]$Py)

    Write-Host ""
    Write-Host "  Installing AINL (ainativelang[mcp])..." -ForegroundColor Cyan

    if (-not (Test-Python310Plus $Py)) {
        $ver = try { & $Py -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" } catch { "unknown" }
        Write-Host "  Error: Python $ver is too old — AINL needs 3.10+." -ForegroundColor Red
        Show-PythonHelp
        exit 1
    }

    $pyVer = try { & $Py -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" } catch { "unknown" }
    Write-Host "  Using Python $pyVer ($Py)" -ForegroundColor Green

    if (Test-PythonExternallyManaged $Py) {
        Install-AinlViaVenv -BasePy $Py
        return
    }

    $pipFailed = $false
    try {
        & $Py -m pip install --user -q "ainativelang[mcp]" 2>$null
        if ($LASTEXITCODE -ne 0) { $pipFailed = $true }
    } catch { $pipFailed = $true }

    if ($pipFailed) {
        $pipLog = & $Py -m pip install --user "ainativelang[mcp]" 2>&1 | Out-String
        if ($pipLog -match 'externally-managed-environment|EXTERNALLY-MANAGED') {
            Install-AinlViaVenv -BasePy $Py
            return
        }
        Write-Host "  pip install failed: $pipLog" -ForegroundColor Red
        exit 1
    }

    $userBase = & $Py -c "import site; print(site.USER_BASE)"
    $scriptsDir = Join-Path $userBase "Scripts"
    $ainl = Join-Path $scriptsDir "ainl.exe"
    if (-not (Test-Path $ainl)) {
        $cmd = Get-Command ainl -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $ainl = $cmd.Source }
    }
    if (-not $ainl -or -not (Test-Path $ainl)) {
        Write-Host "  Error: AINL installed but could not find 'ainl.exe'." -ForegroundColor Red
        Write-Host "  Add to PATH: $scriptsDir" -ForegroundColor Yellow
        exit 1
    }

    Add-UserPathEntry $scriptsDir

    Write-Host "  Registering AINL MCP server for ArmaraOS..." -ForegroundColor Cyan
    & $ainl install-mcp --host armaraos

    $verLine = try { (& $ainl --version 2>&1 | Select-Object -First 1) } catch { "ainl" }
    Write-Host "  AINL ready ($verLine)" -ForegroundColor Green
}

function Show-GetStarted {
    Write-Host ""
    Write-Host "  You're ready — run these now:" -ForegroundColor Cyan
    Write-Host "    armaraos init --quick"
    Write-Host "    armaraos start --detach"
    Write-Host "    armaraos dashboard"
    Write-Host ""
    Write-Host "  Verify anytime: armaraos doctor"
    Write-Host "  Upgrade CLI:    armaraos update"
    Write-Host ""
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

function Get-LatestVersion {
    if ($env:ARMARAOS_VERSION) { return $env:ARMARAOS_VERSION }
    if ($env:OPENFANG_VERSION) { return $env:OPENFANG_VERSION }
    Write-Host "  Fetching latest release from $DownloadBase/latest.json ..."
    try {
        $manifest = Invoke-RestMethod -Uri "$DownloadBase/latest.json" -UseBasicParsing
        if ($manifest.tag) { return $manifest.tag }
        if ($manifest.version) { return "v$($manifest.version)" }
    } catch {
        Write-Host "  Could not read $DownloadBase/latest.json" -ForegroundColor Red
    }
    Write-Host "  Set `$env:ARMARAOS_VERSION=vX.Y.Z or retry after the next release syncs to ainativelang.com." -ForegroundColor Yellow
    exit 1
}

function Install-ArmaraOS {
    Write-Banner

    $arch = Get-Architecture
    $version = Get-LatestVersion
    $target = "${arch}-pc-windows-msvc"
    $archiveCandidates = @(
        "armaraos-${target}.zip",
        "openfang-${target}.zip"
    )

    Write-Host "  Installing ArmaraOS (CLI) $version for $target..."

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "armaraos-install-$([guid]::NewGuid().ToString('n'))"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $archivePath = $null
    $checksumUrl = $null

    foreach ($archive in $archiveCandidates) {
        $url = "$DownloadBase/$archive"
        $candidatePath = Join-Path $tempDir $archive
        try {
            Invoke-WebRequest -Uri $url -OutFile $candidatePath -UseBasicParsing
            $archivePath = $candidatePath
            $checksumUrl = "$url.sha256"
            break
        } catch {
            continue
        }
    }
    if (-not $archivePath) {
        Write-Host "  Download failed for: $($archiveCandidates -join ', ')" -ForegroundColor Red
        Write-Host "  If this is a fresh release, wait for ainativelang.com to sync CLI binaries." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
        exit 1
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

    Expand-Archive -Path $archivePath -DestinationPath $tempDir -Force
    $exePath = Get-ChildItem -Path $tempDir -Filter "armaraos.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $exePath) {
        $exePath = Get-ChildItem -Path $tempDir -Filter "openfang.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (-not $exePath) {
        Write-Host "  Could not find armaraos.exe in archive." -ForegroundColor Red
        exit 1
    }

    Copy-Item -Path $exePath.FullName -Destination (Join-Path $InstallDir "armaraos.exe") -Force
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

    if ($env:ARMARAOS_SKIP_AINL -eq '1') {
        Write-Host ""
        Write-Host "  Skipped AINL (ARMARAOS_SKIP_AINL=1)." -ForegroundColor Yellow
        Show-GetStarted
        return
    }

    $py = Find-Python
    if ($py) {
        Write-Host "  Found existing Python on PATH." -ForegroundColor Green
    }
    if (-not $py) { $py = Install-PythonViaWinget }
    if (-not $py) { $py = Find-Python }
    if (-not $py) {
        Show-PythonHelp
        exit 1
    }

    Install-Ainl -Py $py
    Show-GetStarted
}

Install-ArmaraOS
