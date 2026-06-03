# Upgrade ArmaraOS CLI on Windows without `armaraos update` (v0.8.2 cannot replace its own .exe).
# Usage: irm https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli/upgrade-cli.ps1 | iex
#
# Env: ARMARAOS_VERSION (optional pin, e.g. v0.8.2), ARMARAOS_INSTALL_DIR (default %USERPROFILE%\.armaraos\bin)

$ErrorActionPreference = 'Stop'

$DownloadBase = if ($env:ARMARAOS_DOWNLOAD_BASE) {
    $env:ARMARAOS_DOWNLOAD_BASE.TrimEnd('/')
} else {
    'https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli'
}

$InstallDir = if ($env:ARMARAOS_INSTALL_DIR) {
    $env:ARMARAOS_INSTALL_DIR
} elseif ($env:OPENFANG_INSTALL_DIR) {
    $env:OPENFANG_INSTALL_DIR
} else {
    Join-Path $env:USERPROFILE '.armaraos\bin'
}

function Get-LatestTag {
    $manifestUrl = "$DownloadBase/latest.json"
    $manifest = Invoke-RestMethod -Uri $manifestUrl -UseBasicParsing
    if ($env:ARMARAOS_VERSION) {
        return $env:ARMARAOS_VERSION.Trim()
    }
    if ($manifest.tag) { return [string]$manifest.tag }
    if ($manifest.version) { return "v$($manifest.version)" }
    throw "Could not read tag from $manifestUrl"
}

function Stop-ArmaraosProcesses {
    $exe = Join-Path $InstallDir 'armaraos.exe'
    if (Test-Path -LiteralPath $exe) {
        try { & $exe stop 2>$null | Out-Null } catch { }
    }
    foreach ($name in @('armaraos', 'openfang')) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

Write-Host ''
Write-Host '  ArmaraOS CLI upgrade (Windows)' -ForegroundColor Cyan
Write-Host '  ==============================' -ForegroundColor Cyan
Write-Host ''

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$tag = Get-LatestTag
$zipName = 'armaraos-x86_64-pc-windows-msvc.zip'
$zipUrl = "$DownloadBase/$zipName"
$shaUrl = "$zipUrl.sha256"

Write-Host "  Target:    $tag"
Write-Host "  Install:   $InstallDir"
Write-Host ''

Stop-ArmaraosProcesses

$tmp = Join-Path ([IO.Path]::GetTempPath()) "armaraos-cli-upgrade-$([guid]::NewGuid().ToString('n'))"
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$zipPath = Join-Path $tmp $zipName

try {
    Write-Host '  Downloading CLI archive...' -ForegroundColor Cyan
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing

    try {
        $expected = (Invoke-WebRequest -Uri $shaUrl -UseBasicParsing).Content.Split(' ')[0].Trim().ToLower()
        $actual = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLower()
        if ($expected -ne $actual) {
            throw "Checksum mismatch (expected $expected, got $actual)"
        }
        Write-Host '  Checksum verified.' -ForegroundColor Green
    } catch {
        Write-Host "  Checksum skipped: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    Expand-Archive -LiteralPath $zipPath -DestinationPath $tmp -Force
    $src = Get-ChildItem -Path $tmp -Filter 'armaraos.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $src) {
        $src = Get-ChildItem -Path $tmp -Filter 'openfang.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (-not $src) {
        throw 'armaraos.exe not found in archive'
    }

    $dest = Join-Path $InstallDir 'armaraos.exe'
    Copy-Item -LiteralPath $src.FullName -Destination $dest -Force
    Write-Host '  CLI binary updated.' -ForegroundColor Green

    $legacy = Join-Path $InstallDir 'openfang.exe'
    if (Test-Path -LiteralPath $legacy) {
        Copy-Item -LiteralPath $dest -Destination $legacy -Force
    }

    $ver = & $dest --version 2>&1
    Write-Host ''
    Write-Host "  Installed: $ver" -ForegroundColor Green
    Write-Host ''
    Write-Host '  Next: armaraos doctor --repair' -ForegroundColor Cyan
    Write-Host '        armaraos start --yolo --detach' -ForegroundColor Cyan
    Write-Host '        armaraos dashboard' -ForegroundColor Cyan
    Write-Host ''
  Write-Host '  Note: On v0.8.2 and older, use this script on Windows instead of armaraos update.' -ForegroundColor DarkYellow
  Write-Host '        v0.8.3+ supports armaraos update in place.' -ForegroundColor DarkYellow
    Write-Host ''
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
