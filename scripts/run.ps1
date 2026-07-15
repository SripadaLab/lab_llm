# run.ps1 - run a workshop example using the private environment.
#
# You do NOT need to activate anything. This uses the Python installed
# by .\scripts\setup.ps1, inside this folder.
#
# Usage:
#   .\scripts\run.ps1 modules\01_first_call\example.py

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Split-Path -Parent $ScriptDir
Set-Location $Project

$Python = Join-Path $Project ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "The environment isn't set up yet."
    Write-Host "Run this first:  .\scripts\setup.ps1"
    exit 1
}

if ($args.Count -lt 1) {
    Write-Host "Usage: .\scripts\run.ps1 <path-to-example>"
    Write-Host "Example: .\scripts\run.ps1 modules\01_first_call\example.py"
    exit 1
}

& $Python $args[0]
