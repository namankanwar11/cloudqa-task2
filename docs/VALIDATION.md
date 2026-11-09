# Actual validation record — 2026-11-09

Environment: Windows, Python 3.12.13, Playwright Chromium 156.
Project and writable tool caches are on D. No live OpenAI key was available.

## Executed checks

- Python compileall: application and tests compiled.
- Pytest: 38 passed, 2 skipped. Skips are the explicit opt-in real OpenAI tests.
- API/browser tests include real local login with fixture credentials, fill/select/check,
  reordered/renamed DOM, assertion failure, skipped-assertion rejection, approval denial
  and single-use tokens, cancellation, bounded replanning, exact URL assertions, blocked
  unsafe navigation, secret redaction and HTTP API/report retrieval.
- Credential/email fields require registered aliases; model-invented credential values are blocked.
- The provider API key is redaction-only and cannot be resolved as an executor placeholder.
- Real OpenAI SDK parsing/request schema exercised against a mocked HTTP transport;
  no real AI completion or billing event is claimed.
- Dashboard launched at http://127.0.0.1:8765. Playwright clicked the offline sample and
  observed PASS, assertion evidence and a masked screenshot.
- Mobile viewport 390 x 844: no horizontal overflow.
- No frontend JavaScript runtime errors in the dashboard smoke run.
- Missing API key: the dashboard returned ERROR with an actionable configuration message.
- PHPTravels: real Chromium reached https://phptravels.com/demo and verified its known
  public demo heading was visible. This is a read-only connectivity/DOM smoke check,
  not natural-language planning validation. No login or demo registration was attempted.
- Task 1 was rebuilt with 0 warnings/errors and its 9 xUnit browser tests passed again.

Machine-generated evidence (ignored by Git):
- artifacts/test-results.xml
- artifacts/ui-validation/result.json
- artifacts/ui-validation/desktop.png
- artifacts/ui-validation/mobile.png
- artifacts/ui-validation/phptravels.png
- artifacts/<run-id>/report.json and step screenshots

To rerun the dashboard smoke check, start the app in one terminal, then in another:
~~~powershell
cd D:\Projects\CloudQA-Task2
. .\scripts\env.ps1
.\.venv\Scripts\python.exe -m scripts.verify_dashboard
~~~
It expects port 8765 and ALLOW_LOCALHOST=true. It does not make a paid model call.

## Still unvalidated

- Real OpenAI planning, account/model availability, API rate limits and billing.
- Real model reliability on unseen instructions and a different website.
- PHPTravels login or any customer dashboard (no authorized credentials supplied).
- Task 2 remote GitHub Actions execution. Its workflow is configured, not remotely run.
- Linux/macOS execution, other browser engines, iframe/shadow-root and new-tab workflows.
- Adversarial-site isolation, complete PII detection or exhaustive destructive-action detection.

Before submission: configure a local API key and run the opt-in model tests and new
instructions on an authorized second website. A scripted-provider PASS is not evidence
of model generalization. The lack of live model validation is a material remaining step.

## Sources used for implementation

- OpenAI structured outputs:
  https://developers.openai.com/api/docs/guides/structured-outputs
- Playwright semantic assertions/accessibility guidance:
  https://playwright.dev/python/docs/aria-snapshots
- Reference site inspected:
  https://phptravels.com/demo