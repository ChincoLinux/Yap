# build-windows.ps1 — Script de build del instalador Yap para Windows
# Issue: https://github.com/ChincoLinux/Yap/issues/162
#
# Uso:
#   .\packaging\windows\build-windows.ps1
#   .\packaging\windows\build-windows.ps1 -StubLlama    # sin descargar llama-cli real
#   .\packaging\windows\build-windows.ps1 -SkipISCC     # solo prepara los archivos
#
# Requisitos:
#   - Windows 10/11 o GitHub Actions windows-latest
#   - Inno Setup 6 instalado (o en C:\Program Files (x86)\Inno Setup 6\ISCC.exe)
#   - Internet para descargar Python embebido y llama-cli

[CmdletBinding()]
param(
    [string]$PythonVersion = "3.12.7",
    [string]$LlamaCppTag   = "b5097",          # llama.cpp release tag
    [switch]$StubLlama     = $false,            # use a fake llama-cli for CI
    [switch]$SkipISCC      = $false,            # skip Inno Setup compilation
    [string]$OutDir        = "dist\windows"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot  = Resolve-Path "$ScriptDir\..\.."
$BuildDir  = Join-Path $RepoRoot "build"

Write-Host "=== Yap Windows Build ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host "Build: $BuildDir"

# ─── 1. Directories ──────────────────────────────────────────────────────────
$PythonBuildDir  = Join-Path $BuildDir "python-embed"
$LlamaBuildDir   = Join-Path $BuildDir "llama-cli"
$DistDir         = Join-Path $RepoRoot $OutDir

New-Item -ItemType Directory -Force -Path $PythonBuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $LlamaBuildDir  | Out-Null
New-Item -ItemType Directory -Force -Path $DistDir        | Out-Null

# ─── 2. Python embedded ──────────────────────────────────────────────────────
$PythonZip = Join-Path $BuildDir "python-embed.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"

if (-not (Test-Path (Join-Path $PythonBuildDir "python.exe"))) {
    Write-Host "`n[1/4] Descargando Python $PythonVersion embedded..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip -UseBasicParsing
    Expand-Archive -Path $PythonZip -DestinationPath $PythonBuildDir -Force
    Remove-Item $PythonZip
    Write-Host "    OK: Python embebido en $PythonBuildDir" -ForegroundColor Green
} else {
    Write-Host "`n[1/4] Python embebido ya presente." -ForegroundColor Green
}

# Enable site-packages in embedded Python (needed for any pip installs)
$PthFile = Get-ChildItem $PythonBuildDir -Filter "python312._pth" -ErrorAction SilentlyContinue
if ($PthFile) {
    $content = Get-Content $PthFile.FullName
    $content = $content -replace "^#import site", "import site"
    Set-Content $PthFile.FullName $content
}

# ─── 3. llama-cli for Windows ────────────────────────────────────────────────
$LlamaExe = Join-Path $LlamaBuildDir "llama-cli.exe"

if ($StubLlama) {
    Write-Host "`n[2/4] Usando stub llama-cli (CI mode)..." -ForegroundColor Yellow
    # Create a minimal stub exe (Python script renamed to .bat for testing)
    $stubContent = "@echo off`r`necho [llama-cli stub] llamado con args: %*`r`nexit /b 0"
    Set-Content (Join-Path $LlamaBuildDir "llama-cli.bat") $stubContent
    # Copy batch as a fake exe for packaging purposes
    Copy-Item (Join-Path $LlamaBuildDir "llama-cli.bat") $LlamaExe
    Write-Host "    OK: stub llama-cli creado." -ForegroundColor Green
} elseif (-not (Test-Path $LlamaExe)) {
    Write-Host "`n[2/4] Descargando llama-cli $LlamaCppTag para Windows..." -ForegroundColor Yellow
    # llama.cpp releases include a Windows build with CUDA/CPU variants
    $LlamaZipUrl = "https://github.com/ggerganov/llama.cpp/releases/download/$LlamaCppTag/llama-$LlamaCppTag-bin-win-noavx-x64.zip"
    $LlamaZip    = Join-Path $BuildDir "llama-win.zip"
    $LlamaExtract = Join-Path $BuildDir "llama-extract"

    Invoke-WebRequest -Uri $LlamaZipUrl -OutFile $LlamaZip -UseBasicParsing
    Expand-Archive -Path $LlamaZip -DestinationPath $LlamaExtract -Force
    Remove-Item $LlamaZip

    # Find llama-cli.exe in the extracted archive
    $found = Get-ChildItem $LlamaExtract -Recurse -Filter "llama-cli.exe" | Select-Object -First 1
    if (-not $found) {
        # Older releases used "main.exe"
        $found = Get-ChildItem $LlamaExtract -Recurse -Filter "main.exe" | Select-Object -First 1
    }
    if ($found) {
        Copy-Item $found.FullName $LlamaExe
        # Also copy any required DLLs
        Get-ChildItem $found.DirectoryName -Filter "*.dll" | ForEach-Object {
            Copy-Item $_.FullName $LlamaBuildDir
        }
        Write-Host "    OK: llama-cli.exe en $LlamaBuildDir" -ForegroundColor Green
    } else {
        Write-Error "ERROR: llama-cli.exe no encontrado en el archivo descargado."
    }
    Remove-Item $LlamaExtract -Recurse -Force
} else {
    Write-Host "`n[2/4] llama-cli ya presente." -ForegroundColor Green
}

# ─── 4. Verify source files ──────────────────────────────────────────────────
Write-Host "`n[3/4] Verificando archivos fuente..." -ForegroundColor Yellow
$required = @("yap.py", "VERSION", "LICENSE", "USAGE.md",
              "whitelist\apps.conf", "whitelist\web.conf",
              "whitelist\pseint\ejercicios.conf")
foreach ($f in $required) {
    $path = Join-Path $RepoRoot $f
    if (-not (Test-Path $path)) {
        Write-Error "ERROR: archivo requerido no encontrado: $f"
    }
}
Write-Host "    OK: todos los archivos fuente presentes." -ForegroundColor Green

# ─── 5. Version (leida del fichero VERSION, jamas escrita a mano) ────────────
# El .iss dejaba la version hardcodeada en 1.0.1 mientras VERSION iba por
# 1.0.6: cinco releases de instaladores con nombre y registro equivocados.
# Ver https://github.com/ChincoLinux/Yap/issues/242
$VersionFile = Join-Path $RepoRoot "VERSION"
$YapVersion = (Get-Content $VersionFile -Raw).Trim()

if ($YapVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.]+)?$') {
    Write-Error "ERROR: VERSION con valor '$YapVersion' no es un semver valido. Corrige $VersionFile."
}
Write-Host "    OK: VERSION = $YapVersion" -ForegroundColor Green

# ─── 6. Run Inno Setup ───────────────────────────────────────────────────────
if (-not $SkipISCC) {
    Write-Host "`n[4/4] Compilando instalador con Inno Setup..." -ForegroundColor Yellow

    # Find ISCC.exe
    $isccPaths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue)?.Source
    )
    $iscc = $isccPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if (-not $iscc) {
        Write-Host "    AVISO: Inno Setup no encontrado. Instala desde https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
        Write-Host "    Saltando compilación del instalador. Los archivos están listos en $BuildDir." -ForegroundColor Yellow
    } else {
        $issFile = Join-Path $ScriptDir "yap-installer.iss"
        Push-Location $RepoRoot
        & $iscc $issFile "/DMyAppVersion=$YapVersion" /O"$DistDir"
        Pop-Location

        if ($LASTEXITCODE -eq 0) {
            $installer = Get-ChildItem $DistDir -Filter "yap-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            Write-Host "`n    Instalador generado: $($installer.FullName)" -ForegroundColor Green
            Write-Host "    Tamaño: $([math]::Round($installer.Length / 1MB, 1)) MB" -ForegroundColor Green
        } else {
            Write-Error "ERROR: ISCC falló con código $LASTEXITCODE"
        }
    }
} else {
    Write-Host "`n[4/4] Saltando ISCC (--SkipISCC)." -ForegroundColor Yellow
}

Write-Host "`n=== Build completado ===" -ForegroundColor Cyan
Write-Host "Archivos de build en: $BuildDir"
Write-Host "Instalador en:        $DistDir"
