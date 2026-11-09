# Example instructions

Use precise expected outcomes. Supply secrets by aliases, not plaintext in instructions.
These examples do not install website-specific workflows.

## Public reference (read-only)

URL: https://phptravels.com/demo

Instruction: Open the page and verify the main heading
"PHPTRAVELS live demo: travel booking software, no credit card" is visible.

The heading was observed in a real Chromium browser on 2026-11-09. Public text may change.
The real Groq-driven heading assertion passed. PHPTravels login is not validated.

## Different public website

URL: https://the-internet.herokuapp.com/login

Instruction: Verify the heading "Login Page" is visible and the Username textbox is visible.

This was executed with real Groq planning and Chromium: PASS.
Negative example: Verify the heading "CloudQA nonexistent customer dashboard" is visible.
That was executed and returned FAIL as expected.
## Local fixtures (two PowerShell terminals)

Terminal 1:
~~~powershell
cd D:\Projects\CloudQA-Task2
. .\scripts\env.ps1
.\.venv\Scripts\python.exe -m http.server 8766 --bind 127.0.0.1 --directory tests/fixtures
~~~

Set ALLOW_LOCALHOST=true in the app's ignored .env and restart the app.

URL: http://127.0.0.1:8766/account.html

Instruction: Log in using {{CUSTOMER_EMAIL}} and {{CUSTOMER_PASSWORD}} and verify the
"Customer dashboard" heading is shown.

Local fixture-only credentials:
CUSTOMER_EMAIL = demo@example.test
CUSTOMER_PASSWORD = fixture-only

Approve the Sign in click when the dashboard requests it. These are not PHPTravels credentials.

URL: http://127.0.0.1:8766/preferences.html (or reordered.html)

Instruction: Set Display name to Ada, choose French as Language, enable Send updates,
save preferences, and verify the confirmation "Preferences saved" is visible.

To demonstrate a FAIL on the same page:
Verify the heading "No such dashboard" is visible.

The standard automated suite uses scripted provider responses to validate these browser
workflows. Run the opt-in live model tests after configuring your API key to assess actual
natural-language planning. Change the instructions and try a different authorized website
before recording; do not describe scripted tests as unseen AI successes.