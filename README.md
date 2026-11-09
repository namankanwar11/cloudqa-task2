# CloudQA Task 2 — AI Browser Test Runner

A local FastAPI dashboard that turns natural-language instructions into bounded Playwright
actions through OpenAI structured output. Browser-verified assertions determine the result;
a model's claim of success does not.

**Project:** D:\Projects\CloudQA-Task2
**Current validation:** real browser execution/dashboard tested; real OpenAI planning awaits
an API key. Offline sample mode is a fixed script and is clearly labelled, not an AI fallback.

## Run on this Windows machine

Python 3.12, the virtual environment, packages and Chromium were installed on D.

~~~powershell
cd D:\Projects\CloudQA-Task2
. .\scripts\env.ps1
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
~~~

Open http://127.0.0.1:8765. The ignored .env currently has no API key and enables loopback
only for the local sample. Click **Run offline sample** to verify browser execution.
For natural-language AI execution, edit .env locally:

~~~dotenv
OPENAI_API_KEY=your_actual_key_here
OPENAI_MODEL=gpt-4.1-mini
ALLOW_LOCALHOST=true
~~~

Restart the server after changing .env. Never paste the key into chat, source, screenshots
or Git. Model availability is account-dependent; set OPENAI_MODEL to an accessible
Responses/structured-output-capable model. API access and billing are separate from ChatGPT.
No API call with a real key has been executed for this project yet.

## Fresh Windows installation

Prerequisite: Python 3.11+ (3.12 recommended), or the uv package manager already installed
on this machine. The environment script directs writable caches to D.

~~~powershell
cd D:\Projects\CloudQA-Task2
. .\scripts\env.ps1
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-lock.txt
.\.venv\Scripts\python.exe -m playwright install chromium
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\scripts\run.ps1
~~~

If using an existing official Windows Python instead of uv:
~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m playwright install chromium
~~~

Enable ALLOW_LOCALHOST=true only when using the local sample/fixtures. Public targets work
with it false. Do not use --reload on Windows: subprocess event-loop changes can prevent
Playwright from launching. The provided run script launches a single normal process.

## Usage

1. Enter the target HTTP(S) URL and a test instruction with objective expected results.
2. Optionally select Show browser window for headed execution.
3. For credentials, use placeholders such as {{CUSTOMER_EMAIL}} and {{CUSTOMER_PASSWORD}},
   entering their values in the credential panel or TEST_SECRET_<ALIAS> environment settings.
4. Run AI test. The UI displays the frozen assertions and live step timeline.
5. Review and approve each proposed click. Denial returns BLOCKED.
6. Inspect PASS / FAIL / ERROR and download the JSON report and masked screenshots.

PHPTravels example:
Open the page and verify the main heading
"PHPTRAVELS live demo: travel booking software, no credit card" is visible.

Credentials are not invented. PHPTravels currently requests user details before providing
demo access; this tool does not silently register an account or assume a successful login.

## Tests

~~~powershell
cd D:\Projects\CloudQA-Task2
. .\scripts\env.ps1
.\.venv\Scripts\python.exe -m pytest --junitxml=artifacts/test-results.xml -q
~~~

The normal suite requires no API key. It uses local HTTP fixtures, real Chromium and scripted
provider responses. It covers login, changed DOM, form fill/select/check, strict assertions,
approval denial/replay, cancellation, replanning, action budgets, URL policy, redaction,
backend API, JavaScript MIME type and the real OpenAI SDK with mocked HTTP transport.

Real model tests are explicitly opt-in and incur API usage:
~~~powershell
$env:RUN_LIVE_LLM = '1'
.\.venv\Scripts\python.exe -m pytest -m live_llm -v
Remove-Item Env:RUN_LIVE_LLM
~~~
They run on local fixture sites with known test credentials and fixture-only automatic
approval. Production dashboard clicks always require human approval.
See docs/VALIDATION.md for actual results and unvalidated cases.

## Configuration

.env.example lists all settings. Highlights:
- OPENAI_API_KEY / OPENAI_MODEL: secret and configurable model.
- MAX_STEPS=25 / MAX_REPLANS=3: bounded execution and recovery budgets.
- ACTION_TIMEOUT_MS=5000 / RUN_TIMEOUT_SECONDS=180: overall deadline includes approval time.
- API_TIMEOUT_SECONDS=40: individual API timeout; SDK retries are also bounded.
- CAPTURE_SCREENSHOTS=true: masked screenshots; disable on sensitive targets.
- EXTRA_ALLOWED_HOSTS: comma-separated exact hosts for redirects/SSO.
- ALLOW_LOCALHOST=false: explicit opt-in for loopback; other private networks remain blocked.

Inputs are masked and registered secrets redacted, but arbitrary site text can contain unknown
sensitive data. A reduced observation is sent to the configured AI provider. Use synthetic
data and inspect artifacts before sharing. This is a local single-user tool, not a public
service or an adversarial-site sandbox.

## Structure

~~~text
app/
  main.py          FastAPI endpoints and local session guard
  models.py        strict Pydantic action/assertion contracts
  planner.py       OpenAI structured planner and separate offline sample
  browser.py       observations, allowed actions, assertion verification
  observe.js       generic semantic DOM extraction
  runner.py        bounded orchestration, approvals, reports
  security.py      URL checks, redaction, secret resolution
  static/          responsive dashboard and local sample
tests/             real-browser tests and local HTML fixtures
scripts/           D-drive environment, run and test commands
docs/              architecture, examples, validation and recording guide
~~~

See docs/ARCHITECTURE.md for trust boundaries and limitations, docs/EXAMPLES.md for test
instructions and docs/DEMO.md for a five-minute recording covering both tasks.
The Task 1 project remains separate at D:\CloudQA-Internship.

## GitHub and CI

This repository includes .gitignore and .github/workflows/tests.yml. CI installs Python
and Chromium on Ubuntu, executes the normal suite without an API key and uploads test results.
Task 2 remote CI has not been run yet. To publish after creating an empty GitHub repository:

~~~powershell
git add .
git commit -m "Build AI browser testing tool"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/cloudqa-task2.git
git push -u origin main
~~~

Do not commit .env, .venv, artifacts or work. API keys must never enter Git history.