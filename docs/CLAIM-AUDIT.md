# Claim audit — 2026-11-09

> Publication update: this document preserves the local audit performed before publication.
> The project is now public at https://github.com/namankanwar11/cloudqa-task2.
> See the README and GitHub Actions for current remote CI results.
> Historical statements about no push or unvalidated remote CI describe the audit's original state.

This audit tests the claims that can be checked on this Windows machine. It does not
certify every possible website, every English instruction, or adversarial security.
The final machine-generated counts are in artifacts/claim-audit-summary.json.

## Latest results

- Regular suite: **74 passed, 4 live cases deselected** (54.06 seconds).
- Post-fix real Groq suite: **4 passed, 72 other cases deselected** (237.47 seconds);
  the two download/worker audit tests were added afterward and also passed in the full regular run.
- Task 1: **9 tests passed**, build **0 warnings / 0 errors**.
- Preserved pre-fix live rerun: **1 failed, 3 passed**, with the incorrect form assertion retained.
- Current provider key values were not found in publishable files.
- No GitHub push was performed.

## Evidence and interpretation

**Runtime verified** means a named automated test executed the behavior.
**Sample verified** means finite live-model/browser cases succeeded; it is not a universal guarantee.
**Code reviewed** means the mechanism exists but was not independently exercised in this audit.
**Unvalidated** means no successful execution evidence is claimed.

| Claim | Verdict | Evidence / practical limit |
|---|---|---|
| URL + English instruction accepted | Runtime verified | API validation and real provider workflows |
| LLM creates structured, validated plans/actions | Runtime verified | OpenAI mocked SDK, Groq mocked contract and real model tests |
| Arbitrary model code/selectors rejected | Runtime verified | Unknown action and extra selector validation tests; executor uses fixed allowlist |
| Real Chromium execution | Runtime verified | Browser tests run actual Chromium, not DOM mocks |
| Headless and headed modes | Runtime verified | Default headless tests and headed Chromium test |
| Generic labels, ARIA, roles and text | Runtime verified | Reordered fixtures, aria-labelledby novel form, label locator and semantic group scope |
| Website-specific workflows absent in AI executor | Code reviewed + sample verified | Reference names occur in UI defaults only; changed DOM and different fixture sites pass |
| Click, fill, select, checkbox/radio and navigation | Runtime verified | Original workflows, new multi-page workflow, radio/uncheck and navigation tests |
| Text/visible/hidden/value/selected-label/checked/exact-URL assertions | Runtime verified | Original tests and added assertion-type tests |
| Reinspect after DOM changes | Runtime verified | An input is actually detached/replaced; first action replans, second uses fresh observation |
| Explicit waits for delayed content | Runtime verified | Delayed confirmation appears after page load |
| PASS requires all planned assertions | Runtime verified | Early finish fails; unknown assertion ID blocked; failed assertion cannot be rewritten |
| Plan covers every possible English requirement | Not provable; limitation | A model may misunderstand or omit intent. Review its required assertions |
| Distinguish FAIL / ERROR / BLOCKED / CANCELLED | Runtime verified after bug fix | Negative assertions, injected browser failure, policy denial and cancellation |
| Overall deadline includes approval time | Runtime verified | Hung planner and unapproved click both stop at configured deadline |
| Step and replan budgets | Runtime verified | Existing bounded loop and replan tests |
| Groq retry count/delay and semantic repair | Runtime verified with mocked HTTP | Three-attempt bound, capped Retry-After, invalid schema repaired before execution |
| Real Groq login and form handling | Sample verified | Original customer login + preferences workflows |
| A new multi-page English workflow | Sample verified | Follow workspace link, fill Nickname, select Express, check Gift wrap, preview, assert confirmation |
| Real AI negative test | Sample verified | Nonexistent dashboard heading returns FAIL |
| PHPTravels heading | Sample verified, earlier run | Real Groq public-site report and user's supplied PASS report; no login claim |
| A second public website | Sample verified, earlier run | The Internet login-page heading/Username assertion; negative assertion FAIL |
| Screenshots, timings and JSON reports | Runtime verified | Files/JSON/timings checked; screenshot control pixels are actually magenta-masked |
| Disable screenshots | Runtime verified | No PNG and no screenshot link when disabled |
| Registered secret/input redaction | Runtime verified for synthetic cases | Input values absent after fill; report redaction, JSON escaping, provider keys not executor aliases |
| Every possible PII/secret is detected | Not claimed | Arbitrary page text/images may reveal unknown sensitive information |
| Every runner-initiated click requires approval | Runtime verified | Approval denial, consumed token, changed-control rejection and local approved actions |
| All destructive behavior on arbitrary sites prevented | Not claimed | GET side effects and arbitrary website JS cannot be fully inferred; this is not a sandbox |
| Unsafe schemes, private addresses and host changes rejected | Runtime verified | Scheme/IP/DNS tests and exact-host policy tests |
| Network writes gated | Runtime verified | A real local POST is blocked before permission and reaches server when explicitly enabled |
| WebSockets blocked | Runtime verified | Reachable local WebSocket positive control; browser connection never reaches server |
| Popups closed and dialogs dismissed | Runtime verified | Local popup and confirmation produce policy-specific observed outcomes |
| Automatic download acceptance disabled | Runtime verified | Same synthetic file downloads when acceptance is enabled; the runner reports an acceptance failure when disabled |
| Service workers blocked | Runtime verified | Same fixture registers a worker when allowed; registration is blocked in the actual runner |
| Browser session isolation | Runtime verified | First run writes a cookie; the next run cannot see it |
| Dashboard, report/screenshot links, mobile layout | Runtime verified | Isolated app process + real browser; report and image HTTP responses checked |
| Untrusted report text is not executed as HTML | Runtime verified | Malicious img/onerror string renders as text; no DOM injection/execution |
| API session token, Host filter, single active run | Runtime verified | Unauthorized POST, untrusted Host, concurrent start and cancel tests |
| API keys excluded from publishable files | Checked separately | .env ignored; current key values scanned without printing them |
| Task 1 build/test claims | Runtime verified again | Build: 0 warnings/errors; 9 xUnit tests passed |
| Task 2 remote GitHub CI | Unvalidated | No remote push or CI run was authorized/performed |
| Real OpenAI success | Unvalidated | Earlier real API call failed for exhausted credits; mocked contract is not a live success |
| PHPTravels customer login/dashboard | Unvalidated | No authorized demo credentials supplied |
| Linux/macOS, other engines, iframe/shadow-root/new tabs | Unvalidated / unsupported | Outside implemented/validated scope |
| All unseen websites/test cases will pass | Not claimed | Finite testing cannot establish this |

## Bug found and fixed

The audit injected a browser execution error during an assertion. The old code incorrectly
returned FAIL. The new regression test failed before the fix. The handler now returns ERROR
for non-assertion execution exceptions; actual failed conditions still return FAIL.
Strict-locator ambiguity remains a failed assertion, never an arbitrary first match.

A separate live-model repeatability failure was preserved: the preferences form actions
completed correctly, but the model tried to find the textbox value as a visible text node.
The planner now explicitly distinguishes input value, selected option label and rendered text.
A selected-label assertion was added, with a test proving an option label can differ from
its underlying DOM value. This reduces a measured failure mode; it does not make language
interpretation infallible. The original failed XML remains alongside the post-fix results.

## Reproduce

Normal suite, no model calls:
~~~powershell
cd D:\Projects\CloudQA-Task2
.\scripts\test_all.ps1
~~~

Include all real AI cases (uses your configured provider quota):
~~~powershell
.\scripts\test_all.ps1 -IncludeLiveAI
~~~

Include Task 1 build/tests as well:
~~~powershell
.\scripts\test_all.ps1 -IncludeLiveAI -IncludeTask1
~~~

Each real-model case has a bounded deadline. Free-tier rate limits or model variability
can cause a later run to fail even when a prior run passed. Preserve failures and inspect
the reports rather than changing expected results into a PASS.

All work remains local. No GitHub push was performed.