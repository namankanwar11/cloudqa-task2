import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from playwright.async_api import Page, expect
from .models import Assertion
from .security import PolicyError, safe_url_text

OBSERVE = Path(__file__).with_name("observe.js").read_text(encoding="utf-8")
SELECTOR = "input,button,select,textarea,a[href],[role],h1,h2,h3,h4,h5,h6,p,li,output,label"

class BrowserSession:
    def __init__(self, page: Page, policy, redactor, timeout: int):
        self.page, self.policy, self.redactor, self.timeout = page, policy, redactor, timeout
        self.refs = {}
        self.metadata = {}
        self.write_approved = False
        self.blocked = []
        page.set_default_timeout(timeout)

    async def guard(self, route):
        request = route.request
        try:
            # Validate every request's resolved address. Only document navigations are
            # exact-host restricted; public CDN resources may load.
            await self.policy.validate(request.url, navigation=request.is_navigation_request())
            if request.method not in ("GET", "HEAD", "OPTIONS") and (not self.write_approved or urlsplit(request.url).hostname not in self.policy.hosts):
                raise PolicyError("Network write requires explicit action approval")
            await route.continue_()
        except Exception:
            self.blocked.append("A request was blocked by the navigation/write policy")
            await route.abort("blockedbyclient")

    async def snapshot(self) -> dict:
        for handle in self.refs.values():
            await handle.dispose()
        self.refs, self.metadata = {}, {}
        rows = []
        for handle in (await self.page.query_selector_all(SELECTOR))[:300]:
            try:
                meta = await handle.evaluate(OBSERVE)
                if not meta["visible"] or meta["disabled"]:
                    await handle.dispose()
                    continue
                ref = f"e{len(rows)+1}"
                self.refs[ref], self.metadata[ref] = handle, meta
                row = {k: v for k, v in meta.items() if k not in ("href", "visible", "disabled")}
                row["name"] = self.redactor.clean(row["name"])
                if row.get("selected"):
                    row["selected"] = [self.redactor.clean(x) for x in row["selected"]]
                if row["options"]:
                    row["options"] = [self.redactor.clean(x) for x in row["options"]]
                rows.append({"ref": ref, **row})
            except Exception:
                await handle.dispose()
        return {"url": self.redactor.clean(safe_url_text(self.page.url)), "elements": rows,
                "notice": self.blocked[-3:], "truncated": len(rows) >= 300}

    def target(self, target):
        root = self.page
        if target.scope_role:
            root = root.get_by_role(target.scope_role, name=target.scope_name or "", exact=True)
        if target.role == "text":
            return root.get_by_text(target.name, exact=True)
        if target.role == "label":
            return root.get_by_label(target.name, exact=True)
        return root.get_by_role(target.role, name=target.name, exact=True)

    async def verify(self, assertion: Assertion):
        expected = self.redactor.resolve(assertion.expected)
        if assertion.kind == "url":
            await self.policy.validate(expected)
            await expect(self.page).to_have_url(expected, timeout=self.timeout)
            return
        target = assertion.target.model_copy(update={"name": self.redactor.resolve(assertion.target.name)})
        locator = self.target(target)
        # Locator assertions are strict. Multiple matches cannot silently become first().
        if assertion.kind == "hidden":
            await expect(locator).to_be_hidden(timeout=self.timeout)
        elif assertion.kind == "visible":
            await expect(locator).to_be_visible(timeout=self.timeout)
        elif assertion.kind == "text":
            await expect(locator).to_have_text(expected, timeout=self.timeout)
        elif assertion.kind == "value":
            await expect(locator).to_have_value(expected, timeout=self.timeout)
        elif assertion.kind == "selected":
            await expect(locator.locator("option:checked")).to_have_text(expected, timeout=self.timeout)
        elif assertion.kind == "checked":
            await expect(locator).to_be_checked(checked=expected == "true", timeout=self.timeout)

    async def execute(self, action):
        if action.kind == "navigate":
            url = urljoin(self.page.url, action.value)
            await self.policy.validate(url)
            await self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 3)
            return
        if action.ref not in self.refs:
            raise PolicyError("Unknown or stale observation reference")
        handle = self.refs[action.ref]
        if not await handle.is_visible():
            raise RuntimeError("Observed element is no longer visible")
        meta = self.metadata[action.ref]
        if action.kind == "fill" and (meta.get("type") in ("password", "email") or re.search(r"password|e-?mail", meta.get("name", ""), re.I)):
            if not re.fullmatch(r"\{\{[A-Z][A-Z0-9_]*\}\}", action.value or ""):
                raise PolicyError("Credential/email fields require a registered secret placeholder; values cannot be invented")
        value = self.redactor.resolve(action.value or "")
        if action.kind == "click":
            href = self.metadata[action.ref].get("href")
            if href:
                await self.policy.validate(href)
            await handle.click(timeout=self.timeout)
        elif action.kind == "fill":
            await handle.fill(value, timeout=self.timeout)
            if await handle.input_value() != value:
                raise RuntimeError("Fill verification failed")
        elif action.kind == "select":
            await handle.select_option(label=value, timeout=self.timeout)
            selected = await handle.evaluate("e=>Array.from(e.selectedOptions).map(o=>o.textContent.trim())")
            if value not in selected:
                raise RuntimeError("Selection verification failed")
        elif action.kind == "check":
            await handle.set_checked(value == "true", timeout=self.timeout)
            if await handle.is_checked() != (value == "true"):
                raise RuntimeError("Checkbox verification failed")

    async def screenshot(self, path):
        # Do not capture credentials in controls or explicitly marked sensitive areas.
        masks = [self.page.locator("input,textarea,select,[data-sensitive]")]
        for secret in self.redactor.secrets.values():
            masks.append(self.page.get_by_text(secret, exact=False))
        await self.page.screenshot(path=str(path), full_page=False, mask=masks, timeout=self.timeout)