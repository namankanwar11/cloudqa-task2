"""Runtime audit of documented claims. No real provider is used in this module."""
import asyncio
import base64
import json
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
import pytest
from playwright.async_api import async_playwright, expect
from app.browser import BrowserSession
from app.config import Settings
from app.main import create_app
from app.models import Action, Assertion, RunRequest
from app.runner import Runner
from app.security import NavigationPolicy, Redactor, PolicyError
from .helpers import assertion, target, ScriptedPlanner
from .test_runner import run_with_approvals

@asynccontextmanager
async def browser_case(local_site, path="audit.html"):
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        context=await browser.new_context()
        page=await context.new_page()
        session=BrowserSession(page,NavigationPolicy(local_site,allow_localhost=True),Redactor({}),1000)
        await context.route("**/*",session.guard)
        await page.goto(local_site+"/"+path)
        try:
            yield session
        finally:
            await browser.close()

def config(tmp_path, **kwargs):
    return Settings(_env_file=None,allow_localhost=True,artifacts_dir=tmp_path,
        action_timeout_ms=1000,**kwargs)

@pytest.mark.parametrize("kind,name,expected",[
    ("text","Exact confirmation","Exact confirmation"),
    ("hidden","Hidden message",""),
    ("checked","Enabled flag","true"),
])
async def test_additional_assertion_types(local_site,kind,name,expected):
    async with browser_case(local_site) as session:
        role="checkbox" if kind=="checked" else "text"
        await session.verify(assertion("condition",kind,role,name,expected))

async def test_label_and_semantic_group_scope(local_site):
    async with browser_case(local_site,"preferences.html") as session:
        await session.verify(assertion("label","visible","label","Display name"))
    async with browser_case(local_site) as session:
        scoped=target("button","Continue").model_copy(update={"scope_role":"group","scope_name":"Second panel"})
        await session.verify(Assertion(id="scoped",description="Scoped duplicate button",kind="visible",target=scoped,expected=""))

async def test_delayed_page_content_uses_assertion_wait(local_site):
    async with browser_case(local_site,"delayed-audit.html") as session:
        await session.verify(assertion("delayed","visible","text","Delayed confirmation"))

async def test_radio_and_unchecking_are_verified(local_site):
    async with browser_case(local_site) as session:
        observation=await session.snapshot()
        for role,name,value in [("radio","Priority","true"),("checkbox","Enabled flag","false")]:
            row=next(e for e in observation["elements"] if e["role"]==role and e["name"]==name)
            await session.execute(Action(kind="check",ref=row["ref"],value=value,assertion_id=None,destructive=False,reason="Local audit"))
            await session.verify(assertion("state","checked",role,name,value))

async def test_observations_omit_input_values_after_filling(local_site):
    async with browser_case(local_site,"account.html") as session:
        session.redactor=Redactor({"EMAIL":"private@example.test","PASSWORD":"opaque-audit-secret"})
        await session.page.get_by_label("Email address").fill("private@example.test")
        await session.page.get_by_label("Password").fill("opaque-audit-secret")
        encoded=json.dumps(await session.snapshot())
        assert "private@example.test" not in encoded
        assert "opaque-audit-secret" not in encoded
        assert "filled" in encoded

async def test_screenshot_really_masks_control_pixels(local_site,tmp_path):
    async with browser_case(local_site,"account.html") as session:
        await session.page.get_by_label("Password").fill("visible-only-to-browser")
        rect=await session.page.get_by_label("Password").bounding_box()
        path=tmp_path/"masked.png"
        await session.screenshot(path)
        data=base64.b64encode(path.read_bytes()).decode()
        pixel=await session.page.evaluate("""async ({data,x,y})=>{
            const image=new Image(); image.src='data:image/png;base64,'+data; await image.decode();
            const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
            const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);
            return Array.from(ctx.getImageData(x,y,1,1).data);
        }""",{"data":data,"x":int(rect["x"]+rect["width"]/2),"y":int(rect["y"]+rect["height"]/2)})
        assert pixel[:3]==[255,0,255]

async def test_network_write_is_blocked_then_allowed_explicitly(local_site):
    async with browser_case(local_site) as session:
        # Local SimpleHTTP server rejects POST with 501 when reached.
        result=await session.page.evaluate("""async ()=>{try{
            const response=await fetch('/audit.html',{method:'POST',body:'synthetic'});
            return response.status;
        }catch{return 'blocked';}}""")
        assert result=="blocked"
        assert session.blocked
        session.write_approved=True
        result=await session.page.evaluate("""async ()=>{try{
            return (await fetch('/audit.html',{method:'POST',body:'synthetic'})).status;
        }catch{return 'blocked';}}""")
        assert result==501

@pytest.mark.parametrize("host_allowed", [False,True])
async def test_exact_host_navigation_configuration(local_site,host_allowed):
    alternate=local_site.replace("127.0.0.1","localhost")
    policy=NavigationPolicy(local_site,extra_hosts="localhost" if host_allowed else "",allow_localhost=True)
    if host_allowed:
        await policy.validate(alternate+"/audit.html")
    else:
        with pytest.raises(PolicyError):
            await policy.validate(alternate+"/audit.html")

async def test_headed_chromium_mode(local_site,tmp_path):
    planner=ScriptedPlanner([assertion("heading","visible","heading","Audit laboratory")],
        [{"kind":"assert","assertion_id":"heading"},{"kind":"finish"}])
    runner=Runner(config(tmp_path),RunRequest(url=local_site+"/audit.html",
        instruction="Verify Audit laboratory heading.",headless=False),planner)
    result=await runner.run()
    assert result.status=="PASS",result.reason

@pytest.mark.parametrize("control,confirmation",[("Open dialog","Dialog dismissed"),("Open sample window","Popup closed")])
async def test_runner_dismisses_dialogs_and_closes_popups(local_site,tmp_path,control,confirmation):
    planner=ScriptedPlanner([assertion("result","visible","text",confirmation)],
        [{"kind":"click","role":"button","name":control},{"kind":"assert","assertion_id":"result"},{"kind":"finish"}])
    result,_=await run_with_approvals(Runner(config(tmp_path),RunRequest(url=local_site+"/audit.html",
        instruction="Exercise a local browser policy and verify its confirmation."),planner))
    assert result.status=="PASS",result.reason

async def test_overall_deadline_really_interrupts_planning(local_site,tmp_path):
    class HungPlanner(ScriptedPlanner):
        async def plan(self,*args):
            await asyncio.Event().wait()
    runner=Runner(config(tmp_path,run_timeout_seconds=5),RunRequest(url=local_site+"/audit.html",
        instruction="Verify Audit laboratory heading."),HungPlanner([assertion()],[]))
    result=await runner.run()
    assert result.status=="ERROR" and "deadline exceeded" in result.reason
    assert 4500 <= result.elapsed_ms < 15000

async def test_control_change_invalidates_pending_approval(local_site,tmp_path):
    planner=ScriptedPlanner([assertion("heading","visible","heading","Approval fixture")],
        [{"kind":"click","role":"button","name":"Continue"}])
    runner=Runner(config(tmp_path),RunRequest(url=local_site+"/approval-change.html",
        instruction="Click Continue and verify the heading."),planner)
    task=asyncio.create_task(runner.run())
    try:
        for _ in range(300):
            if runner.approval_token: break
            await asyncio.sleep(.01)
        assert runner.approval_token
        await asyncio.sleep(1.5)
        runner.decide(runner.approval_token,True)
        result=await task
        assert result.status=="BLOCKED" and "changed" in result.reason
    finally:
        if not task.done():
            task.cancel()
            await task

async def test_api_enforces_single_active_run_cancel_and_host(local_site,tmp_path):
    class HungPlanner(ScriptedPlanner):
        async def plan(self,*args):
            await asyncio.Event().wait()
    app=create_app(config(tmp_path),lambda:HungPlanner([assertion()],[]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
        token=(await client.get("/api/config")).json()["session_token"]
        headers={"X-Runner-Token":token}
        payload={"url":local_site+"/audit.html","instruction":"Verify Audit laboratory heading."}
        first=await client.post("/api/runs",headers=headers,json=payload)
        id=first.json()["id"]
        await asyncio.sleep(.6)
        assert (await client.post("/api/runs",headers=headers,json=payload)).status_code==409
        assert (await client.post(f"/api/runs/{id}/cancel",headers=headers)).status_code==200
        await app.state.tasks[id]
        assert (await client.get("/api/runs/"+id)).json()["status"]=="CANCELLED"
        assert (await client.get("/",headers={"Host":"untrusted.example"})).status_code==400
        assert (await client.get(f"/api/runs/{id}/screenshots/not-a-screenshot.txt")).status_code==404
async def test_browser_execution_error_during_assertion_is_not_a_test_failure(local_site,tmp_path,monkeypatch):
    async def disconnected(self,required):
        raise RuntimeError("Synthetic browser disconnect")
    monkeypatch.setattr(BrowserSession,"verify",disconnected)
    planner=ScriptedPlanner([assertion("heading","visible","heading","Audit laboratory")],
        [{"kind":"assert","assertion_id":"heading"}])
    result=await Runner(config(tmp_path),RunRequest(url=local_site+"/audit.html",
        instruction="Verify the Audit laboratory heading."),planner).run()
    assert result.status=="ERROR",result.model_dump()

async def test_actual_dom_detachment_triggers_reinspection(local_site,tmp_path,monkeypatch):
    original=BrowserSession.execute
    detached=False
    async def detach_once(self,action):
        nonlocal detached
        if action.kind=="fill" and not detached:
            detached=True
            await self.page.get_by_label("Display name").evaluate("e=>e.replaceWith(e.cloneNode(true))")
        return await original(self,action)
    monkeypatch.setattr(BrowserSession,"execute",detach_once)
    planner=ScriptedPlanner([assertion("value","value","textbox","Display name","Lira")],[
        {"kind":"fill","role":"textbox","name":"Display name","value":"Lira"},
        {"kind":"fill","role":"textbox","name":"Display name","value":"Lira"},
        {"kind":"assert","assertion_id":"value"},{"kind":"finish"}])
    result=await Runner(config(tmp_path),RunRequest(url=local_site+"/preferences.html",
        instruction="Set Display name to Lira and verify its value."),planner).run()
    assert result.status=="PASS",result.reason
    assert result.steps[0].status=="REPLAN"

async def test_approval_wait_is_included_in_overall_deadline(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[
        {"kind":"click","role":"button","name":"Open dialog"}])
    runner=Runner(config(tmp_path,run_timeout_seconds=5),RunRequest(url=local_site+"/audit.html",
        instruction="Open the dialog and verify the outcome."),planner)
    result=await runner.run()  # Deliberately never approve.
    assert result.status=="ERROR" and "deadline exceeded" in result.reason
    assert result.approval is None
    assert runner.approval_token is None

async def test_screenshots_can_be_disabled_and_report_timings_exist(local_site,tmp_path):
    planner=ScriptedPlanner([assertion("heading","visible","heading","Audit laboratory")],
        [{"kind":"assert","assertion_id":"heading"},{"kind":"finish"}])
    runner=Runner(config(tmp_path,capture_screenshots=False),RunRequest(url=local_site+"/audit.html",
        instruction="Verify Audit laboratory heading."),planner)
    result=await runner.run()
    assert result.status=="PASS"
    assert result.elapsed_ms>0 and result.steps[0].elapsed_ms>=0
    assert not list(runner.directory.glob("*.png"))
    assert result.steps[0].screenshot is None
    assert json.loads((runner.directory/"report.json").read_text())["status"]=="PASS"

async def test_each_run_gets_an_isolated_cookie_store(local_site,tmp_path):
    first=ScriptedPlanner([assertion("stored","visible","text","Cookie stored")],[
        {"kind":"click","role":"button","name":"Store cookie"},
        {"kind":"assert","assertion_id":"stored"},{"kind":"finish"}])
    result,_=await run_with_approvals(Runner(config(tmp_path),RunRequest(url=local_site+"/isolation.html",
        instruction="Store the synthetic session cookie and verify confirmation."),first))
    assert result.status=="PASS",result.reason
    second=ScriptedPlanner([assertion("clean","visible","heading","No prior session")],
        [{"kind":"assert","assertion_id":"clean"},{"kind":"finish"}])
    result=await Runner(config(tmp_path),RunRequest(url=local_site+"/isolation.html",
        instruction="Verify there is no prior session."),second).run()
    assert result.status=="PASS",result.reason

async def test_runner_blocks_an_otherwise_reachable_websocket(local_site,tmp_path):
    from websockets.asyncio.server import serve
    from websockets.asyncio.client import connect
    from urllib.parse import quote
    connections=[]
    async def handler(socket):
        connections.append(True)
        await socket.wait_closed()
    async with serve(handler,"127.0.0.1",0) as server:
        endpoint=f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        async with connect(endpoint):
            await asyncio.sleep(.02)
        assert connections  # Positive control: endpoint is reachable without browser policy.
        connections.clear()
        planner=ScriptedPlanner([assertion("closed","visible","text","Channel closed")],
            [{"kind":"assert","assertion_id":"closed"},{"kind":"finish"}])
        result=await Runner(config(tmp_path),RunRequest(
            url=local_site+"/channel-audit.html?channel="+quote(endpoint,safe=""),
            instruction="Verify the browser channel is closed."),planner).run()
        assert result.status=="PASS",result.reason
        assert connections==[]

async def test_selected_label_and_dom_value_are_distinct_assertions(local_site):
    async with browser_case(local_site) as session:
        await session.page.set_content('<label>Speed<select><option value="std">Standard</option><option value="exp">Express</option></select></label>')
        observation=await session.snapshot()
        row=next(e for e in observation["elements"] if e["role"]=="combobox")
        await session.execute(Action(kind="select",ref=row["ref"],value="Express",assertion_id=None,destructive=False,reason="Local audit"))
        await session.verify(assertion("label","selected","combobox","Speed","Express"))
        await session.verify(assertion("value","value","combobox","Speed","exp"))
        with pytest.raises(AssertionError):
            await session.verify(assertion("wrong-label","selected","combobox","Speed","Standard"))

async def test_runner_blocks_service_worker_registration(local_site,tmp_path):
    # Positive control: this browser/site can register a worker when allowed.
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        try:
            context=await browser.new_context(service_workers="allow")
            page=await context.new_page()
            await page.goto(local_site+"/worker-audit.html")
            await expect(page.get_by_text("Worker registered",exact=True)).to_be_visible()
        finally:
            await browser.close()
    planner=ScriptedPlanner([assertion("blocked","visible","text","Worker blocked")],
        [{"kind":"assert","assertion_id":"blocked"},{"kind":"finish"}])
    result=await Runner(config(tmp_path),RunRequest(url=local_site+"/worker-audit.html",
        instruction="Verify that the service worker is blocked."),planner).run()
    assert result.status=="PASS",result.reason

async def test_runner_disables_download_acceptance(local_site,tmp_path,monkeypatch):
    from playwright.async_api import Browser
    # Positive control: the same local file is downloadable with explicit acceptance.
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        try:
            context=await browser.new_context(accept_downloads=True)
            page=await context.new_page()
            await page.goto(local_site+"/download-audit.html")
            async with page.expect_download() as download_info:
                await page.get_by_role("link",name="Download synthetic file").click()
            assert await (await download_info.value).failure() is None
        finally:
            await browser.close()
    observed=[]
    event=asyncio.Event()
    original=Browser.new_context
    async def record(download):
        observed.append(await download.failure())
        event.set()
    async def spy(self,*args,**kwargs):
        context=await original(self,*args,**kwargs)
        context.on("page",lambda page:page.on("download",lambda download:asyncio.create_task(record(download))))
        return context
    monkeypatch.setattr(Browser,"new_context",spy)
    class DownloadPlanner(ScriptedPlanner):
        async def next_action(self,instruction,observation,plan,history,verified,last_error):
            if history:
                await asyncio.wait_for(event.wait(),timeout=3)
            return await super().next_action(instruction,observation,plan,history,verified,last_error)
    planner=DownloadPlanner([assertion("heading","visible","heading","Download fixture")],[
        {"kind":"click","role":"link","name":"Download synthetic file"},
        {"kind":"assert","assertion_id":"heading"},{"kind":"finish"}])
    result,_=await run_with_approvals(Runner(config(tmp_path),RunRequest(url=local_site+"/download-audit.html",
        instruction="Exercise the local download policy and verify the heading."),planner))
    assert result.status=="PASS",result.reason
    assert observed and observed[0] is not None
    assert "accept_downloads" in observed[0]
