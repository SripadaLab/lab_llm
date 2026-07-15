# run.ps1 - run a workshop example using the private environment.
#
# You do NOT need to activate anything. This uses the Python installed
# by .\setup.ps1, inside this folder.
#
# Usage:
#   .\run.ps1                                          # runs modules\01_first_call\example.py
#   .\run.ps1 modules\02_ratings_at_scale\example.py   # run a specific file

$ErrorActionPreference = "Stop"

$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Project

$Python = Join-Path $Project ".venv\Scripts\python.exe"
if ($args.Count -ge 1) { $Target = $args[0] } else { $Target = "modules\01_first_call\example.py" }

if (-not (Test-Path $Python)) {
    Write-Host "The environment isn't set up yet."
    Write-Host "Run this first:  .\setup.ps1"
    exit 1
}

& $Python $Target
