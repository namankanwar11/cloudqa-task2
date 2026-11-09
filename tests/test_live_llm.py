"""Opt-in real model evaluation. Never silently substitute a fake provider."""
import os
import pytest
from app.config import Settings
from app.models import RunRequest
from app.runner import Runner
from .test_runner import run_with_approvals

pytestmark=[
    pytest.mark.live_llm,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM")!="1",reason="Real OpenAI evaluation requires RUN_LIVE_LLM=1 and API billing/key"),
]

@pytest.mark.parametrize("page,instruction",[
    ("preferences.html","Set Display name to Ada, choose French as Language, enable Send updates, save preferences and verify Preferences saved is visible."),
    ("account.html","Log in with {{EMAIL}} and {{PASSWORD}} and verify the Customer dashboard heading is visible."),
])
async def test_natural_language_with_real_model(local_site,tmp_path,page,instruction):
    from pydantic import SecretStr
    settings=Settings(allow_localhost=True,artifacts_dir=tmp_path,run_timeout_seconds=180)
    if not settings.active_key.get_secret_value():
        pytest.fail("RUN_LIVE_LLM=1 was requested but the selected provider key is missing")
    runner=Runner(settings,RunRequest(url=local_site+"/"+page,instruction=instruction,
        secrets={"EMAIL":SecretStr("demo@example.test"),"PASSWORD":SecretStr("fixture-only")}))
    # Auto-approval is confined to known local fixture tests; production always asks.
    result,_=await run_with_approvals(runner)
    assert result.status=="PASS",result.model_dump()
async def test_novel_multistep_instruction_on_independent_fixture(local_site,tmp_path):
    settings=Settings(allow_localhost=True,artifacts_dir=tmp_path,run_timeout_seconds=300)
    assert settings.active_key.get_secret_value(), "Selected provider key is missing"
    runner=Runner(settings,RunRequest(url=local_site+"/novel-start.html",
        instruction='Open the workspace using its link. Set Nickname to Lira, select Express for Delivery speed, enable Gift wrap, click Preview configuration, and verify the exact confirmation text "Ready for review" is visible.'))
    result,_=await run_with_approvals(runner)
    assert result.status=="PASS",result.model_dump()

async def test_real_model_negative_assertion_stays_fail(local_site,tmp_path):
    settings=Settings(allow_localhost=True,artifacts_dir=tmp_path,run_timeout_seconds=180)
    assert settings.active_key.get_secret_value(), "Selected provider key is missing"
    runner=Runner(settings,RunRequest(url=local_site+"/novel-start.html",
        instruction='Verify that the heading "No such completed customer dashboard" is visible.'))
    result,_=await run_with_approvals(runner)
    assert result.status=="FAIL",result.model_dump()
    assert "FAIL" in result.assertions.values()
