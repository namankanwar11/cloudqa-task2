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