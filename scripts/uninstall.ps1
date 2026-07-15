# uninstall.ps1 - remove everything setup.ps1 created.
#
# Deletes the private Python, the environment, caches, the downloaded tool,
# and your .env. Only the source code is left behind.
# (Deleting this whole folder does the same thing.)
#
# Usage:  .\scripts\uninstall.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Split-Path -Parent $ScriptDir
Set-Location $Project

Write-Host "This removes the private Python, the .venv environment, caches, and .env."
Write-Host "Your source code is kept. Folder: $Project"
$reply = Read-Host "Continue? [y/N]"
if ($reply -notmatch '^(y|Y|yes|YES)$') {
    Write-Host "Cancelled."
    exit 0
}

# Installed-in-folder artifacts (safe to delete; setup.ps1 recreates them).
$targets = @(".bin", ".python", ".cache", ".venv", ".env", "uv.lock")
foreach ($t in $targets) {
    $path = Join-Path $Project $t
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
}

# Build/run leftovers.
Get-ChildItem -Path $Project -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $Project -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Done. Only the source code remains."
Write-Host "To set up again:  .\scripts\setup.ps1"
