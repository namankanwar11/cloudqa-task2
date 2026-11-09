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
async def test_natural_language_with_real_openai(local_site,tmp_path,page,instruction):
    from pydantic import SecretStr
    settings=Settings(allow_localhost=True,artifacts_dir=tmp_path,run_timeout_seconds=180)
    if not settings.openai_api_key.get_secret_value():
        pytest.fail("RUN_LIVE_LLM=1 was requested but OPENAI_API_KEY is missing")
    runner=Runner(settings,RunRequest(url=local_site+"/"+page,instruction=instruction,
        secrets={"EMAIL":SecretStr("demo@example.test"),"PASSWORD":SecretStr("fixture-only")}))
    # Auto-approval is confined to known local fixture tests; production always asks.
    result,_=await run_with_approvals(runner)
    assert result.status=="PASS",result.model_dump()