param(
    [switch]$IncludeLiveAI,
    [switch]$IncludeTask1
)
. "$PSScriptRoot\env.ps1"
$previousLiveSetting = $env:RUN_LIVE_LLM
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if ($IncludeLiveAI) {
        $env:RUN_LIVE_LLM = '1'
        & .\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/full-test-results.xml
    } else {
        Remove-Item Env:RUN_LIVE_LLM -ErrorAction SilentlyContinue
        & .\.venv\Scripts\python.exe -m pytest -m 'not live_llm' -q --junitxml=artifacts/full-test-results.xml
    }
    if ($LASTEXITCODE -ne 0) { throw 'Task 2 tests did not all pass. Review the output and XML report.' }
    if ($IncludeTask1) {
        Push-Location 'D:\CloudQA-Internship'
        try {
            . .\scripts\env.ps1
            dotnet build CloudQA.sln -c Release
            if ($LASTEXITCODE -ne 0) { throw 'Task 1 build failed.' }
            dotnet test CloudQA.sln -c Release --no-build
            if ($LASTEXITCODE -ne 0) { throw 'Task 1 tests failed.' }
        } finally { Pop-Location }
    }
} finally {
    Pop-Location
    if ($null -eq $previousLiveSetting) {
        Remove-Item Env:RUN_LIVE_LLM -ErrorAction SilentlyContinue
    } else {
        $env:RUN_LIVE_LLM = $previousLiveSetting
    }
}