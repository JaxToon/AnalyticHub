# Start the Bank Data & Analytics Hub PoC at http://127.0.0.1:8000
param([int]$Port = 8000, [switch]$Reset)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if ($Reset -and (Test-Path "$root\data")) { Remove-Item -Recurse -Force "$root\data" }
& "$root\.venv\Scripts\python.exe" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $Port
