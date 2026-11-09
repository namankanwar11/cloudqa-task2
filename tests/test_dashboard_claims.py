"""Real dashboard/browser checks against an isolated local app process. No AI calls."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urljoin
import httpx
import pytest
from playwright.async_api import async_playwright,expect
from app.config import ROOT

@pytest.fixture(scope="module")
def audit_dashboard():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",0))
        port=probe.getsockname()[1]
    env=dict(os.environ,ALLOW_LOCALHOST="true",OPENAI_API_KEY="",GROQ_API_KEY="")
    process=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(port)],
        cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
    base=f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Isolated dashboard process exited")
            try:
                if httpx.get(base,timeout=.3).status_code==200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        else:
            raise RuntimeError("Isolated dashboard did not start")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

async def test_dashboard_offline_run_report_screenshot_and_mobile(audit_dashboard,tmp_path):
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        page=await browser.new_page(viewport={"width":1440,"height":1000})
        errors=[]
        page.on("pageerror",lambda error:errors.append(type(error).__name__))
        try:
            await page.goto(audit_dashboard)
            await page.get_by_role("button",name="Run offline sample").click()
            await expect(page.locator("#status")).to_have_text("PASS",timeout=20000)
            response=await page.request.get(urljoin(page.url,await page.locator("#download").get_attribute("href")))
            report=await response.json()
            assert report["status"]=="PASS" and report["mode"]=="demo"
            image=page.locator("#timeline img")
            await expect(image).to_be_visible()
            assert (await page.request.get(urljoin(page.url,await image.get_attribute("src")))).status==200
            await page.screenshot(path=str(tmp_path/"dashboard.png"),full_page=True)
            await page.set_viewport_size({"width":390,"height":844})
            assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            assert not errors
        finally:
            await browser.close()

async def test_dashboard_renders_untrusted_report_as_text(audit_dashboard):
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        page=await browser.new_page()
        payload='<img src=x onerror="window.auditXss=true">'
        async def routes(route):
            request=route.request
            if request.url.endswith("/api/config"):
                data={"session_token":"synthetic-local-token","model":"mock","provider":"audit",
                    "api_key_configured":False,"allow_localhost":True}
            elif request.method=="POST":
                data={"id":"fixture"}
            else:
                data={"id":"fixture","status":"ERROR","mode":"audit","reason":payload,
                    "elapsed_ms":1,"plan":{"assertions":[{"id":"a","description":payload}]},
                    "assertions":{"a":"ERROR"},"steps":[],"approval":None}
            await route.fulfill(status=200,content_type="application/json",body=json.dumps(data))
        await page.route("**/api/**",routes)
        try:
            await page.goto(audit_dashboard)
            await page.get_by_role("button",name="Run offline sample").click()
            await expect(page.locator("#status")).to_have_text("ERROR")
            await expect(page.locator("#reason")).to_have_text(payload)
            assert await page.evaluate("window.auditXss===undefined")
            assert await page.locator("#reason img").count()==0
        finally:
            await browser.close()