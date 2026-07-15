# setup.ps1 — one-command setup for Windows (PowerShell).
#
# Installs a private Python and all dependencies INSIDE this folder.
# Nothing is installed on your system. Deleting this folder (or running
# .\uninstall.ps1) removes every trace.
#
# Usage:  .\setup.ps1
# If Windows blocks the script, first run:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"

# Resolve the project folder (where this script lives) so it works from anywhere.
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Project

$Bin = Join-Path $Project ".bin"

# Keep uv's Python, cache, and the virtual environment all inside the project.
$env:UV_INSTALL_DIR = $Bin
$env:INSTALLER_NO_MODIFY_PATH = "1"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Project ".python"
$env:UV_CACHE_DIR = Join-Path $Project ".cache"

$PythonVersion = "3.12"

Write-Host "==> Setting up in: $Project"
Write-Host "    Everything installs inside this folder. Your system stays untouched."
Write-Host ""

# 1. Get uv (a small, self-contained tool) into .\.bin if it isn't there yet.
$Uv = Join-Path $Bin "uv.exe"
if (-not (Test-Path $Uv)) {
    Write-Host "==> Downloading uv (the installer tool)..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
} else {
    Write-Host "==> uv already present, skipping download."
}

# 2. Download a private Python, just for this project.
Write-Host "==> Installing a private Python $PythonVersion (this may take a minute)..."
& $Uv python install $PythonVersion

# 3. Create the environment and install the workshop package + dependencies.
Write-Host "==> Creating the environment (.venv) and installing packages..."
& $Uv venv (Join-Path $Project ".venv") --python $PythonVersion
$env:VIRTUAL_ENV = Join-Path $Project ".venv"
& $Uv pip install -e $Project

# 4. Create a .env for your API key if you don't have one yet.
$EnvFile = Join-Path $Project ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Project ".env.example") $EnvFile
    Write-Host "==> Created .env — open it and paste your OpenAI key."
}

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1. Open .env and paste your OpenAI API key."
Write-Host "  2. Run the first example:  .\run.ps1"
Write-Host ""
Write-Host "To remove everything later:  .\uninstall.ps1  (or just delete this folder)."
