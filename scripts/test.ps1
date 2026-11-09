. "$PSScriptRoot\env.ps1"
Push-Location (Split-Path $PSScriptRoot -Parent)
try { & .\.venv\Scripts\python.exe -m pytest --junitxml=artifacts/test-results.xml -q }
finally { Pop-Location }