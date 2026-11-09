import asyncio
import json
import secrets as tokenlib
import time
from pathlib import Path
from uuid import uuid4
from playwright.async_api import async_playwright
from .browser import BrowserSession, OBSERVE
from .models import Report, RunRequest, StepLog
from .planner import OpenAIPlanner, DemoPlanner, provider_error_message
from .providers import create_planner
from .security import NavigationPolicy, PolicyError, Redactor, needs_approval, safe_url_text

TERMINAL = {"PASS", "FAIL", "ERROR", "BLOCKED", "CANCELLED"}

class Runner:
    def __init__(self, settings, request: RunRequest, planner=None, run_id=None):
        self.settings, self.request = settings, request
        self.id = run_id or uuid4().hex
        self.report = Report(id=self.id, status="QUEUED", mode="demo" if request.mode == "demo" else settings.ai_provider, reason="Waiting to start")
        self.planner = planner
        self.approval_event = asyncio.Event()
        self.approved = False
        self.approval_token = None
        self.directory = settings.artifacts_dir / self.id
        self.started = time.monotonic()

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = self.report.model_dump()
        if payload["approval"]:
            payload["approval"] = {k: v for k, v in payload["approval"].items() if k != "token"}
        (self.directory / "report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def decide(self, token, approve):
        if self.report.status != "AWAITING_APPROVAL" or not self.approval_token or not tokenlib.compare_digest(token, self.approval_token):
            raise ValueError("Approval is missing, expired or already consumed")
        self.approved = approve
        self.approval_token = None
        self.approval_event.set()

    async def ask_approval(self, action, metadata, redact):
        self.approval_event.clear()
        self.approved = False
        self.approval_token = tokenlib.token_urlsafe(24)
        self.report.status = "AWAITING_APPROVAL"
        self.report.reason = "Review the next browser action before it executes"
        self.report.approval = {
            "token": self.approval_token, "action": action.kind,
            "control": redact.clean(metadata.get("name", "")),
            "reason": "Clicks and form submissions require explicit approval; they may change external state.",
        }
        self.save()
        await self.approval_event.wait()
        self.report.approval = None
        self.report.status = "RUNNING"
        if not self.approved:
            raise PolicyError("User denied the proposed action")

    async def run(self):
        self.started = time.monotonic()
        self.report.status, self.report.reason = "RUNNING", "Opening isolated browser"
        self.save()
        redactor = Redactor({k: v.get_secret_value() for k, v in self.request.secrets.items()},
                            redaction_only=[self.settings.openai_api_key.get_secret_value(), self.settings.groq_api_key.get_secret_value()])
        policy = NavigationPolicy(self.request.url, self.settings.extra_allowed_hosts, self.settings.allow_localhost)
        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                await policy.validate(self.request.url)
                if self.request.mode == "demo" and not (self.request.url.startswith(("http://127.0.0.1:", "http://localhost:")) and self.request.url.endswith("/demo")):
                    raise PolicyError("Offline demo mode only supports this application's /demo sample")
                if self.planner is None:
                    self.planner = DemoPlanner() if self.request.mode == "demo" else create_planner(self.settings)
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=self.request.headless)
                    try:
                        context = await browser.new_context(accept_downloads=False, service_workers="block")
                        page = await context.new_page()
                        session = BrowserSession(page, policy, redactor, self.settings.action_timeout_ms)
                        await context.route("**/*", session.guard)
                        # Block websocket channels and new windows; they bypass the single-page scope.
                        await context.route_web_socket("**/*", lambda ws: ws.close())
                        context.on("page", lambda popup: asyncio.create_task(popup.close()) if popup != page else None)
                        page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
                        await page.goto(self.request.url, wait_until="domcontentloaded", timeout=self.settings.action_timeout_ms * 3)
                        observation = await session.snapshot()
                        instruction = redactor.clean(self.request.instruction)
                        plan = await self.planner.plan(instruction, observation, list(self.request.secrets))
                        # JSON round trip freezes intent before any action can be executed.
                        frozen = type(plan).model_validate_json(plan.model_dump_json())
                        self.report.plan = redactor.data(frozen.model_dump())
                        required = {a.id: a for a in frozen.assertions}
                        self.report.assertions = {key: "PENDING" for key in required}
                        history, verified, retries, error = [], set(), 0, None
                        for number in range(1, self.settings.max_steps + 1):
                            self.report.reason = f"Planning browser step {number}"
                            self.save()
                            action = await self.planner.next_action(instruction, observation, frozen, history, verified, error)
                            step_start = time.monotonic()
                            status, detail = "OK", action.kind
                            try:
                                if action.kind == "finish":
                                    if verified != set(required):
                                        self.report.status = "FAIL"
                                        self.report.reason = "Planner stopped before all required assertions were verified"
                                    else:
                                        self.report.status = "PASS"
                                        self.report.reason = "All required assertions were verified by the browser"
                                    break
                                if action.kind == "assert":
                                    if action.assertion_id not in required:
                                        raise PolicyError("Planner requested an assertion outside the frozen test plan")
                                    assertion = required[action.assertion_id]
                                    try:
                                        await session.verify(assertion)
                                    except Exception as ex:
                                        # Assertion failure ends the run. The planner cannot weaken or retry it into PASS.
                                        if isinstance(ex, PolicyError):
                                            raise
                                        if isinstance(ex, AssertionError) or "strict mode violation" in str(ex):
                                            self.report.assertions[assertion.id] = "FAIL"
                                            self.report.status = "FAIL"
                                            self.report.reason = redactor.clean(f"Assertion {assertion.id} failed: {assertion.description}")
                                            status, detail = "FAIL", self.report.reason
                                        else:
                                            self.report.assertions[assertion.id] = "ERROR"
                                            self.report.status = "ERROR"
                                            self.report.reason = f"Browser execution error while evaluating assertion {assertion.id} ({type(ex).__name__})"
                                            status, detail = "ERROR", self.report.reason
                                    else:
                                        verified.add(assertion.id)
                                        self.report.assertions[assertion.id] = "PASS"
                                        detail = redactor.clean("Verified assertion " + assertion.id)
                                else:
                                    meta = session.metadata.get(action.ref, {})
                                    # Conservative policy: every click needs approval, not only suspicious words.
                                    approval = action.kind == "click" or needs_approval(action, meta)
                                    if approval:
                                        await self.ask_approval(action, meta, redactor)
                                        if action.ref:
                                            current = await session.refs[action.ref].evaluate(OBSERVE)
                                            if any(current.get(k) != meta.get(k) for k in ("name", "tag", "type", "href", "submits")):
                                                raise PolicyError("Control changed while awaiting approval; start a new run")
                                    session.write_approved = approval and self.approved
                                    try:
                                        await session.execute(action)
                                        # Wait for navigation completion when one is already in flight.
                                        await page.wait_for_load_state("domcontentloaded", timeout=self.settings.action_timeout_ms)
                                    finally:
                                        session.write_approved = False
                                    detail = redactor.clean(f"Filled {meta.get('role', 'field')}: {meta.get('name', '')} (value redacted)") if action.kind == "fill" else redactor.clean(f"Executed {action.kind} on {meta.get('role', 'page')}: {meta.get('name', '')}")
                                error = None
                            except PolicyError:
                                raise
                            except Exception as ex:
                                retries += 1
                                status, detail = "REPLAN", f"{type(ex).__name__}: action did not complete; re-inspecting page"
                                error = detail
                                if retries > self.settings.max_replans:
                                    self.report.status, self.report.reason = "ERROR", "Execution failed after the configured replan limit"
                            screenshot = None
                            if self.settings.capture_screenshots:
                                try:
                                    filename = f"step-{number:03d}.png"
                                    await session.screenshot(self.directory / filename)
                                    screenshot = f"/api/runs/{self.id}/screenshots/{filename}"
                                except Exception:
                                    pass
                            log = StepLog(number=number, action=action.kind, status=status,
                                detail=detail, elapsed_ms=int((time.monotonic()-step_start)*1000), screenshot=screenshot)
                            self.report.steps.append(log)
                            history.append(log.model_dump(exclude={"screenshot"}))
                            self.save()
                            if self.report.status in TERMINAL:
                                break
                            observation = await session.snapshot()
                        else:
                            self.report.status, self.report.reason = "ERROR", "Maximum browser step limit reached"
                    finally:
                        await browser.close()
        except PolicyError as ex:
            self.report.status, self.report.reason = "BLOCKED", redactor.clean(str(ex))
        except TimeoutError:
            self.report.status, self.report.reason = "ERROR", "Run deadline exceeded (includes approval waiting time)"
        except asyncio.CancelledError:
            self.report.status, self.report.reason = "CANCELLED", "Cancelled by user or server shutdown"
        except Exception as ex:
            self.report.status = "ERROR"
            provider_message = provider_error_message(ex, self.settings.ai_provider)
            if provider_message:
                self.report.reason = provider_message
            elif not self.settings.active_key.get_secret_value() and self.request.mode != "demo" and self.planner is None:
                self.report.reason = f"{self.settings.key_variable} is not configured. Add it to the local .env file."
            else:
                # Never persist provider or browser exception bodies: they may echo secrets/page text.
                self.report.reason = f"{type(ex).__name__}: planner or browser could not complete the run. Check configuration, API access and browser installation."
        finally:
            if self.planner:
                await self.planner.close()
            self.report.elapsed_ms = int((time.monotonic()-self.started)*1000)
            self.report.approval = None
            self.approval_token = None
            self.save()
        return self.report