# Run positive & negative test scenarios and write the evidence file shown on /evidence
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force "$root\evidence" | Out-Null
& "$root\.venv\Scripts\python.exe" -m pytest --junitxml="$root\evidence\test-results.xml" -v
