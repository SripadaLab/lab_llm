# uninstall.ps1 - remove the local install created by setup.ps1.
#
# Deletes the private Python, the environment, caches, the downloaded tool,
# and your .env. Source code and run outputs stay.
# Privacy Filter checkpoints outside this folder stay because they may be
# shared with other projects.
# (Deleting the whole folder removes those too.)
#
# Usage:  .\scripts\uninstall.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Split-Path -Parent $ScriptDir
Set-Location $Project

Write-Host "This removes the private Python, the .venv environment, caches, and .env."
Write-Host "Source code and run outputs stay. Folder: $Project"
Write-Host "Privacy Filter checkpoints outside this folder also stay."
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

# Build and cache leftovers.
Get-ChildItem -Path $Project -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $Project -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Done. Source code and run outputs remain."
Write-Host "Shared Privacy Filter checkpoints were not removed."
Write-Host "To set up again:  .\scripts\setup.ps1"
