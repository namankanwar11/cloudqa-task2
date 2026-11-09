# Actual validation — 2026-11-09

## Latest claim-audit update

See docs/CLAIM-AUDIT.md and artifacts/claim-audit-summary.json for the expanded claim audit.
The final regular suite passed 74 cases (4 live cases deselected; 54.06 seconds).
The post-fix live suite passed all four real Groq cases (237.47 seconds).
A preceding repeated run had 1 failure and 3 passes; its XML was preserved.
The audit fixed browser-error classification and clarified form assertion semantics, adding
a selected-option-label assertion. Runtime checks now include headed mode, real DOM detachment,
masked screenshot pixels, cookie isolation, WebSocket/service-worker/download controls,
approval change/deadlines, API boundaries, dashboard/mobile/report links and safe report text.

The counts below are the earlier baseline and are retained as historical evidence.

Windows, Python 3.12.13, Playwright Chromium, Groq with openai/gpt-oss-120b.
Project, dependencies, browser profiles and artifacts are on D.

## Latest executed results

- Regular automated suite: 43 passed, 2 live-model tests deselected (17.59 seconds).
- Real Groq model suite: 2 passed, 43 deselected (123.02 seconds).
  Both workflows used natural-language instructions, real model responses and real Chromium:
  customer login with fixture-only secret aliases, and preferences fill/select/check/save.
- PHPTravels public heading: real Groq planning and browser assertion PASS.
- A different public website, https://the-internet.herokuapp.com/login:
  heading "Login Page" and Username field assertions PASS.
- Deliberately nonexistent dashboard heading on that second site: FAIL as expected.
- Full dashboard-to-Groq-to-Chromium workflow: PASS on the second public site; screenshot saved as artifacts/ui-validation/groq-live-dashboard.png.
- Dashboard offline sample, desktop/mobile layout, JavaScript and provider configuration
  checks passed; no horizontal overflow at 390 x 844.
- Task 1 was separately rebuilt with 0 warnings/errors and all 9 xUnit tests passed.

The fixture-only live tests automatically approve known local clicks. The dashboard requires
explicit approval for every click. Public-site checks were read-only; unexpected clicks were
denied. No PHPTravels registration, login, booking or purchase was performed.

## Failures observed and handled

- An earlier OpenAI attempt failed with HTTP 429, code credit_balance_exhausted,
  type insufficient_quota. Both live tests ended as ERROR. The app now explains quota failures
  separately from temporary rate limits without echoing provider response bodies.
- Initial Groq development runs exposed an empty visible-text target and insufficient
  action-history detail. Semantic validation and bounded schema repair were added; history now
  identifies field names without values. Observations include filled/checked/selected state.
  Final local live-model rerun passed both tests; this is not a guarantee of all future runs.
- A proposed positive test on example.com expected an "Example Domain" heading.
  It returned FAIL. Inspection confirmed that heading was absent on the current page.
  That failure was preserved rather than changing the assertion into a pass.

## Evidence (ignored by Git)

- artifacts/test-results.xml — regular suite
- artifacts/groq-live-tests.xml — real model suite
- artifacts/groq-public-validation.json — PHPTravels and original example.com cases
- artifacts/groq-second-site-validation.json — second-site positive and negative checks
- artifacts/<run-id>/report.json — individual assertions, timings and step evidence
- artifacts/ui-validation/ — masked screenshots and UI smoke results

Run the regular suite with scripts/test.ps1. For the real model suite:
~~~powershell
$env:RUN_LIVE_LLM = '1'
.\.venv\Scripts\python.exe -m pytest -m live_llm -v
Remove-Item Env:RUN_LIVE_LLM
~~~

## Still unvalidated / limitations

- PHPTravels customer login or dashboard (no authorized credentials supplied).
- Task 2 remote GitHub CI. No Task 2 push has been performed; approval is required first.
- Other OS/browser engines, iframe/shadow-root and new-tab workflows.
- Exhaustive unfamiliar-website reliability, adversarial isolation or complete PII detection.
- Real OpenAI success remains unvalidated because the tested key had no API credits.

Finite positive/negative cases do not prove arbitrary unseen-case generalization.
Model output is variable and free-tier rate limits can cause execution ERROR.
Test new instructions on authorized targets before recording.

## Implementation references

- https://console.groq.com/docs/structured-outputs
- https://console.groq.com/docs/openai
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://playwright.dev/python/docs/aria-snapshots