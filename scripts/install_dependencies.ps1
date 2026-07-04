$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "Dependencies installed."
