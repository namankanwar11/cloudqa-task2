. "$PSScriptRoot\env.ps1"
Push-Location (Split-Path $PSScriptRoot -Parent)
try { & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 }
finally { Pop-Location }