# Architecture and trust boundaries

The Groq and OpenAI paths are general and do not contain a PHPTravels workflow, site selectors,
credentials or login success rules. The offline DemoPlanner is a separate, explicitly selected
local sample. It is never a fallback for AI failure.

1. FastAPI validates URL/instruction/mode and optional SecretStr alias values.
2. A fresh isolated Chromium context is launched per run; no existing user profile is used.
3. A request policy checks HTTP(S), exact allowed navigation hosts and resolved addresses.
4. DOM observations collect visible controls, labels, ARIA role/name relationships, headings,
   nearby visible text and select options. Current element handles receive ephemeral refs.
   Typed text/password values are omitted; visible option text and button labels remain semantic evidence. The model sees a redacted, bounded observation.
5. Provider structured output (Groq Chat Completions or OpenAI Responses) parses into a Pydantic TestPlan. This initial
   intent is frozen: required assertion IDs/conditions cannot change during replanning.
6. The model chooses one allowlisted action from each fresh observation. No model-generated
   selectors, JavaScript, Python, shell or file operations are executed.
7. All clicks pause for a per-action single-use approval. A changed control invalidates approval.
   Browser fill/select/check operations verify their resulting DOM state.
8. The next observation is captured after the action. Execution errors permit a bounded
   number of replans. Failed assertions terminate as FAIL; replanning cannot weaken them.
9. A model finish response results in PASS only if every frozen assertion has been
   independently verified with Playwright. Otherwise it is FAIL.
10. Reports include statuses, timings, assertion outcomes, steps and masked screenshots.

## Results

- PASS: all planned required assertions were verified and the planner finished.
- FAIL: a required assertion failed, or the planner finished before verifying every assertion.
- ERROR: API, browser, execution, timeout, replan limit or step budget prevented completion.
- BLOCKED: policy or user approval denied an action.
- CANCELLED: the user or shutdown cancelled the run.
- AWAITING_APPROVAL: a proposed click is paused; this is not a terminal result.

The initial plan is still model-generated. This is not a formal proof that the model
interpreted every natural-language requirement correctly. Review assertions shown in the UI.
A model can under-specify intent; general unseen-case planning quality needs live evaluation.

## Safety and privacy

Only HTTP(S) is allowed. Private/link-local/reserved addresses are blocked; loopback needs an
explicit local-demo opt-in. Redirects/frame navigations must stay on the exact-host allowlist.
Public CDN subresources can load. Non-GET requests are blocked unless an approved action is
executing, and writes must target allowlisted hosts. Popups close, dialogs dismiss, service
workers and websockets are blocked. Downloads are disabled.

Every click requires approval because keyword detection alone cannot establish safety.
The browser is not a network or malware sandbox: GET endpoints can have side effects,
DNS can change after validation, and arbitrary website JS still runs. For adversarial sites,
use a disposable OS/container and an outbound network firewall. Test only authorized sites.

Credential/email fields require secret aliases; invented model credential literals are blocked.
The provider API key is redaction-only and cannot be resolved into a browser field.
Registered secret aliases are resolved only by the executor, never sent as values to the
planner. Environment secrets use TEST_SECRET_<ALIAS>. Secret values and email patterns are
redacted from observations and reports. Typed text/password values are omitted from observations;
screenshots mask input/textarea/select and data-sensitive regions, plus visible registered
secret text. Raw HTML, traces and exception bodies are not persisted.
No automatic redactor can identify all unknown PII or secrets in arbitrary page text/images.
The reduced page observation is sent to the selected provider; use synthetic data, avoid regulated data,
and inspect artifacts before sharing. store=false is set for OpenAI responses, but do not
interpret that as a promise of zero provider retention.

FastAPI binds to loopback, checks Host and requires a process-local token for write APIs.
The UI uses textContent for report data, a restrictive CSP and no third-party frontend code.
It is a single-user development tool, not a production multi-user service. No app login,
durable task queue, encrypted storage or tenant isolation is included.
The in-memory run index resets on restart; report files remain on disk.

## Scope and limits

- Chromium only; headless and headed modes supported. Headed requires a desktop session.
- Main page and native inputs/radios/checkboxes/selects, semantic role/text assertions.
- No iframe/shadow-root traversal, CAPTCHA solving, MFA, uploads, downloads or new-tab flows.
- Custom controls may work through click/fill if semantic metadata exists; no dedicated
  general-purpose custom dropdown/date-picker/drag/drop support.
- Names are a pragmatic approximation of accessible names, not a complete browser AX tree.
  Strict semantic assertions fail on ambiguity instead of choosing the first result.
- Up to 300 DOM candidates are scanned. Very large, inaccessible or virtualized pages can
  omit the needed element; major asynchronous changes can require replanning.
- Cross-host SSO requires explicit extra host configuration and may still be blocked.
- Network writes caused by background JavaScript outside the approved action window fail.
- Maximum steps, replans, action timeout, API timeout and overall deadline bound execution.
  The overall deadline includes time waiting for user approval.
- Assertions validate DOM visibility/text/value/selected-label/checked state or an exact URL, not backend
  persistence or pixel-level correctness.
- LLM variability, API costs, unavailable models and changed public websites remain risks.
## Groq provider

AI_PROVIDER selects Groq or OpenAI explicitly. No credential is sent to the other provider.
Groq uses its OpenAI-compatible Chat Completions endpoint with strict JSON Schema, followed
by Pydantic semantic validation. The OpenAI Python package is only the compatible HTTP client.
The default Groq model is openai/gpt-oss-120b. The model name does not imply paid OpenAI API use.
Groq observations are reduced to at most 100 prioritized semantic candidates. Input values
remain absent; filled booleans, checked state and redacted visible selected-option text help
the planner distinguish completed actions. Logs identify filled field names without values.
There is one bounded semantic repair loop and a bounded rate-limit retry delay, all within
the run deadline. Free-tier limits can prevent completion; ERROR is returned in that case.
## Assertion failure classification

Failed expected conditions and strict-locator ambiguity return FAIL.
Execution exceptions while evaluating assertions return ERROR, rather than pretending the
condition itself was disproved. A regression test injects a browser fault to enforce this.
Textboxes use value assertions, native select labels use selected assertions, and rendered
confirmation messages use visible/text assertions. The model can still misinterpret intent.