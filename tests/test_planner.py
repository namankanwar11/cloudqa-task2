import json
import httpx
from openai import AsyncOpenAI
from app.models import TestPlan as Plan
from app.planner import OpenAIPlanner
from .helpers import assertion

async def test_real_sdk_structured_contract_with_mock_transport():
    payload=Plan(summary="Objective heading check",assertions=[assertion()])
    captured=[]
    async def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={
            "id":"resp_fixture","object":"response","created_at":1,
            "model":"gpt-4.1-mini","status":"completed",
            "output":[{"type":"message","id":"msg_fixture","role":"assistant","status":"completed",
                "content":[{"type":"output_text","text":payload.model_dump_json(),"annotations":[]}]}]})
    planner=object.__new__(OpenAIPlanner)
    planner.model="gpt-4.1-mini"
    planner.client=AsyncOpenAI(api_key="fake-key-for-transport-test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        result=await planner.plan("Verify dashboard heading.",{"elements":[]},["PASSWORD"])
    finally:
        await planner.close()
    assert result==payload
    assert captured[0]["store"] is False
    assert captured[0]["text"]["format"]["type"]=="json_schema"
    assert captured[0]["text"]["format"]["strict"] is True
    assert captured[0]["text"]["format"]["schema"]["additionalProperties"] is False
def test_quota_error_has_actionable_safe_message():
    from openai import RateLimitError
    from app.planner import provider_error_message
    response=httpx.Response(429,request=httpx.Request("POST","https://api.openai.com/v1/responses"))
    error=RateLimitError("sensitive provider content",response=response,
        body={"code":"credit_balance_exhausted","type":"insufficient_quota","message":"sensitive provider content"})
    message=provider_error_message(error)
    assert "credits/quota exhausted" in message
    assert "sensitive provider content" not in message

def test_transient_rate_limit_does_not_claim_billing_failure():
    from openai import RateLimitError
    from app.planner import provider_error_message
    response=httpx.Response(429,request=httpx.Request("POST","https://api.openai.com/v1/responses"))
    error=RateLimitError("do not echo",response=response,body={"code":"rate_limit_exceeded"})
    assert "rate limit reached" in provider_error_message(error)
    assert "credits/quota" not in provider_error_message(error)

async def test_groq_structured_contract_uses_groq_host_and_validates_response():
    import time
    from app.providers import GroqPlanner
    captured=[]
    result=Plan(summary="Groq schema fixture",assertions=[assertion()])
    async def handler(request):
        captured.append((str(request.url),json.loads(request.content)))
        return httpx.Response(200,json={"id":"fixture","object":"chat.completion","created":1,
            "model":"openai/gpt-oss-120b","choices":[{"index":0,"finish_reason":"stop",
                "message":{"role":"assistant","content":result.model_dump_json()}}]})
    planner=object.__new__(GroqPlanner)
    planner.model="openai/gpt-oss-120b"
    planner.next_request=0
    planner.client=AsyncOpenAI(api_key="fake-groq-key",base_url="https://api.groq.com/openai/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        parsed=await planner.plan("Verify the dashboard.",{"elements":[]},[])
    finally:
        await planner.close()
    assert parsed==result
    assert captured[0][0]=="https://api.groq.com/openai/v1/chat/completions"
    assert captured[0][1]["response_format"]["json_schema"]["strict"] is True

def test_provider_configuration_selects_keys_without_exposing_them():
    from app.config import Settings
    from app.providers import GroqPlanner,create_planner
    settings=Settings(_env_file=None,ai_provider="groq",groq_api_key="fake-groq-key")
    assert settings.active_model=="openai/gpt-oss-120b"
    assert settings.key_variable=="GROQ_API_KEY"
    assert settings.active_key.get_secret_value()=="fake-groq-key"
    assert "fake-groq-key" not in repr(settings)

async def test_groq_rate_limit_retry_is_bounded_and_respects_delay(monkeypatch):
    from types import SimpleNamespace
    import app.providers as providers
    from openai import RateLimitError
    calls,delays=[],[]
    async def sleep(delay):
        delays.append(delay)
    monkeypatch.setattr(providers,"asyncio",SimpleNamespace(sleep=sleep))
    async def handler(request):
        calls.append(request)
        return httpx.Response(429,headers={"retry-after":"120"},
            json={"error":{"code":"rate_limit_exceeded","message":"synthetic"}})
    planner=object.__new__(providers.GroqPlanner)
    planner.model="openai/gpt-oss-120b";planner.next_request=0
    planner.client=AsyncOpenAI(api_key="fake",max_retries=0,base_url="https://api.groq.com/openai/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    import pytest
    try:
        with pytest.raises(RateLimitError):
            await planner.plan("Verify a heading.",{"elements":[]},[])
    finally:
        await planner.close()
    assert len(calls)==3
    assert len(delays)==3
    assert all(0<=delay<=30 for delay in delays)
    assert delays[1]>29 and delays[2]>29

async def test_groq_semantic_schema_repair_is_bounded(monkeypatch):
    from types import SimpleNamespace
    import app.providers as providers
    calls=[]
    async def sleep(delay): pass
    monkeypatch.setattr(providers,"asyncio",SimpleNamespace(sleep=sleep))
    good=Plan(summary="Repaired fixture",assertions=[assertion()])
    invalid=good.model_dump()
    invalid["assertions"][0]["target"]={"role":"text","name":"","scope_role":None,"scope_name":None}
    async def handler(request):
        calls.append(json.loads(request.content))
        content=json.dumps(invalid) if len(calls)==1 else good.model_dump_json()
        return httpx.Response(200,json={"id":"fixture","object":"chat.completion","created":1,
            "model":"openai/gpt-oss-120b","choices":[{"index":0,"finish_reason":"stop",
                "message":{"role":"assistant","content":content}}]})
    planner=object.__new__(providers.GroqPlanner)
    planner.model="openai/gpt-oss-120b";planner.next_request=0
    planner.client=AsyncOpenAI(api_key="fake",max_retries=0,base_url="https://api.groq.com/openai/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        assert await planner.plan("Verify a heading.",{"elements":[]},[])==good
    finally:
        await planner.close()
    assert len(calls)==2
    assert "schema_repair" in json.loads(calls[1]["messages"][1]["content"])

def test_missing_selected_provider_key_does_not_fall_back():
    import pytest
    from app.config import Settings
    from app.providers import create_planner
    settings=Settings(_env_file=None,ai_provider="groq",groq_api_key="",openai_api_key="other-provider-secret")
    with pytest.raises(RuntimeError,match="GROQ_API_KEY"):
        create_planner(settings)
