import asyncio
import json
import pytest
from pydantic import SecretStr
from app.config import Settings
from app.models import RunRequest
from app.runner import Runner
from .helpers import ScriptedPlanner, assertion, target
from app.models import Assertion

def settings(tmp_path, **kwargs):
    return Settings(_env_file=None, openai_api_key="", allow_localhost=True,
        artifacts_dir=tmp_path, action_timeout_ms=700, run_timeout_seconds=30, **kwargs)

async def run_with_approvals(runner, approve=True):
    task=asyncio.create_task(runner.run())
    approvals=0
    while not task.done():
        if runner.report.status=="AWAITING_APPROVAL" and runner.approval_token:
            approvals+=1
            runner.decide(runner.approval_token, approve)
        await asyncio.sleep(.02)
    return await task, approvals

async def test_customer_login_real_browser_with_secret_redaction(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[
        {"kind":"fill","role":"textbox","name":"Email address","value":"{{EMAIL}}"},
        {"kind":"fill","role":"textbox","name":"Password","value":"{{PASSWORD}}"},
        {"kind":"click","role":"button","name":"Sign in"},
        {"kind":"assert","assertion_id":"result"},{"kind":"finish"}])
    request=RunRequest(url=local_site+"/account.html",
        instruction="Log in as a customer using {{EMAIL}} and {{PASSWORD}} and verify the Customer dashboard is shown.",
        secrets={"EMAIL":SecretStr("demo@example.test"),"PASSWORD":SecretStr("fixture-only")})
    runner=Runner(settings(tmp_path),request,planner)
    result,approvals=await run_with_approvals(runner)
    assert result.status=="PASS",result.reason
    assert approvals==1
    assert result.assertions=={"result":"PASS"}
    assert len(list(runner.directory.glob("*.png")))==4
    text=(runner.directory/"report.json").read_text()+json.dumps(planner.seen)
    assert "fixture-only" not in text and "demo@example.test" not in text

@pytest.mark.parametrize("page",["preferences.html","reordered.html"])
async def test_different_dom_fill_select_check_and_text_assertion(local_site,tmp_path,page):
    assertions=[
        assertion("name","value","textbox","Display name","Ada"),
        assertion("language","value","combobox","Language","French"),
        assertion("updates","checked","checkbox","Send updates","true"),
        assertion("saved","visible","text","Preferences saved")]
    planner=ScriptedPlanner(assertions,[
        {"kind":"fill","role":"textbox","name":"Display name","value":"Ada"},
        {"kind":"select","role":"combobox","name":"Language","value":"French"},
        {"kind":"check","role":"checkbox","name":"Send updates","value":"true"},
        {"kind":"click","role":"button","name":"Save preferences"},
        *[{"kind":"assert","assertion_id":a.id} for a in assertions],{"kind":"finish"}])
    runner=Runner(settings(tmp_path),RunRequest(url=local_site+"/"+page,
        instruction="Set display name to Ada, choose French, enable Send updates, save preferences and verify every setting and the confirmation."),planner)
    result,_=await run_with_approvals(runner)
    assert result.status=="PASS",result.reason

async def test_assertion_failure_is_not_replanned_or_fabricated(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[
        {"kind":"assert","assertion_id":"result"},{"kind":"finish"}])
    result=await Runner(settings(tmp_path,capture_screenshots=False),
        RunRequest(url=local_site+"/account.html",instruction="Verify Customer dashboard is visible."),planner).run()
    assert result.status=="FAIL"
    assert result.assertions["result"]=="FAIL"
    assert len(planner.actions)==1

async def test_finish_cannot_skip_required_assertions(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[{"kind":"finish"}])
    result=await Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Verify Customer dashboard is visible."),planner).run()
    assert result.status=="FAIL" and result.assertions["result"]=="PENDING"

async def test_approval_denial_blocks_click(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[{"kind":"click","role":"button","name":"Sign in"}])
    result,count=await run_with_approvals(Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Log in and verify Customer dashboard."),planner),approve=False)
    assert result.status=="BLOCKED" and count==1

async def test_unknown_assertion_id_cannot_replace_plan(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[{"kind":"assert","assertion_id":"invented"}])
    result=await Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Verify Customer dashboard is visible."),planner).run()
    assert result.status=="BLOCKED"

async def test_missing_api_key_is_error_not_pass(local_site,tmp_path):
    result=await Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Verify the heading is visible.")).run()
    assert result.status=="ERROR" and "OPENAI_API_KEY" in result.reason

async def test_cross_host_navigation_blocked(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[{"kind":"navigate","value":"https://example.com/"}])
    result=await Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Go somewhere else and verify the heading."),planner).run()
    assert result.status=="BLOCKED"

async def test_step_limit_ends_as_execution_error(local_site,tmp_path):
    planner=ScriptedPlanner([assertion("heading","visible","heading","Customer sign in")],
        [{"kind":"assert","assertion_id":"heading"}]*2)
    result=await Runner(settings(tmp_path,max_steps=2),RunRequest(url=local_site+"/account.html",
        instruction="Verify Customer sign in heading."),planner).run()
    assert result.status=="ERROR" and "step limit" in result.reason

async def test_url_assertion_after_navigation(local_site,tmp_path):
    assertion_url=Assertion(id="url",description="Arrived at preferences",kind="url",target=None,expected=local_site+"/preferences.html")
    planner=ScriptedPlanner([assertion_url],[{"kind":"navigate","value":"/preferences.html"},
        {"kind":"assert","assertion_id":"url"},{"kind":"finish"}])
    result=await Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Navigate to preferences and verify its exact URL."),planner).run()
    assert result.status=="PASS",result.reason
async def test_execution_error_replans_from_fresh_snapshot(local_site,tmp_path):
    planner=ScriptedPlanner([assertion("name","value","textbox","Display name","Ada")],[
        {"kind":"fill","role":"button","name":"Save preferences","value":"wrong control type"},
        {"kind":"fill","role":"textbox","name":"Display name","value":"Ada"},
        {"kind":"assert","assertion_id":"name"},{"kind":"finish"}])
    result=await Runner(settings(tmp_path,capture_screenshots=False),RunRequest(url=local_site+"/preferences.html",
        instruction="Set Display name to Ada and verify its value."),planner).run()
    assert result.status=="PASS",result.reason
    assert result.steps[0].status=="REPLAN"
    assert planner.replans[1] is not None

async def test_replan_budget_is_bounded(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[
        {"kind":"fill","role":"button","name":"Sign in","value":"invalid"}])
    result=await Runner(settings(tmp_path,max_replans=0),RunRequest(url=local_site+"/account.html",
        instruction="Log in and verify the dashboard."),planner).run()
    assert result.status=="ERROR" and "replan limit" in result.reason

async def test_duplicate_semantic_assertion_is_not_arbitrarily_resolved(local_site,tmp_path):
    planner=ScriptedPlanner([assertion("duplicate","visible","button","Continue")],
        [{"kind":"assert","assertion_id":"duplicate"}])
    result=await Runner(settings(tmp_path),RunRequest(url=local_site+"/duplicate.html",
        instruction="Verify the Continue button is visible."),planner).run()
    assert result.status=="FAIL"

async def test_approval_deadline_and_token_replay(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[{"kind":"click","role":"button","name":"Sign in"}])
    runner=Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Log in and verify dashboard."),planner)
    task=asyncio.create_task(runner.run())
    for _ in range(300):
        if runner.approval_token:
            break
        await asyncio.sleep(.01)
    token=runner.approval_token
    assert token
    runner.decide(token,False)
    with pytest.raises(ValueError):
        runner.decide(token,True)
    assert (await task).status=="BLOCKED"

async def test_cancelled_run_is_reported_and_browser_closes(local_site,tmp_path):
    planner=ScriptedPlanner([assertion()],[{"kind":"click","role":"button","name":"Sign in"}])
    runner=Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Log in and verify dashboard."),planner)
    task=asyncio.create_task(runner.run())
    for _ in range(300):
        if runner.approval_token:
            break
        await asyncio.sleep(.01)
    task.cancel()
    assert (await task).status=="CANCELLED"

@pytest.mark.parametrize("field",["Email address","Password"])
async def test_model_cannot_invent_credentials(local_site,tmp_path,field):
    planner=ScriptedPlanner([assertion()],[
        {"kind":"fill","role":"textbox","name":field,"value":"invented-credential"}])
    result=await Runner(settings(tmp_path),RunRequest(url=local_site+"/account.html",
        instruction="Log in as customer and verify dashboard."),planner).run()
    assert result.status=="BLOCKED"
    assert "placeholder" in result.reason
