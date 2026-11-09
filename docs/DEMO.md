# Five-minute recording covering both tasks

Prepare terminals, browser dashboard, GitHub Task 1 Actions page and a local fallback.
Use synthetic data and hide API keys, .env contents, account emails and personal tabs.
Confirm the employer's exact recording/upload requirements before submission.

0:00-0:20 — Introduce both solutions and the different problems they address.

0:20-1:35 — Task 1:
- Run dotnet test CloudQA.sln -c Release.
- Show the mutated fixture: renamed identifiers, reordering and decoys.
- Run headed live automation; explain label scoring and ambiguity rejection.

1:35-3:40 — Task 2:
- Open http://127.0.0.1:8765.
- With a configured API key, run a read-only PHPTravels heading assertion.
- Run a local fixture workflow using plain English, approve the proposed click,
  and show real assertions and the final report.
- If the key/network is unavailable, show the clearly labelled offline browser sample
  and state that live AI validation is pending. Do not call it a completed AI demo.

3:40-4:20 — Demonstrate a failed assertion and the distinct ERROR/BLOCKED outcomes.

4:20-5:00 — Show test results, architecture, GitHub Task 1 CI and limitations.
Mention that Task 2's committed CI workflow is configured, not remotely validated yet.

Do not claim login success on PHPTravels unless you actually obtain authorized demo
credentials, execute the login and verify the dashboard. No credentials are assumed.