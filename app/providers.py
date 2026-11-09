import asyncio
import json
import time
from openai import AsyncOpenAI, RateLimitError
from pydantic import ValidationError
from .planner import OpenAIPlanner, SYSTEM

class GroqPlanner(OpenAIPlanner):
    def __init__(self, settings):
        key = settings.groq_api_key.get_secret_value()
        if not key:
            raise RuntimeError("GROQ_API_KEY is not configured. Add it to the local .env file.")
        self.client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1",
            timeout=settings.api_timeout_seconds, max_retries=0)
        self.model = settings.groq_model
        self.next_request = 0.0

    async def _parse(self, schema, payload):
        payload = dict(payload)
        observation = dict(payload.get("observation", {}))
        rows = observation.get("elements", [])
        rows = sorted(rows, key=lambda e: 0 if e["role"] == "heading" else 2 if e["role"] == "text" else 1)
        observation["elements"] = [
            {k:v for k,v in row.items() if k in ("ref","role","name","options","selected","checked","filled")}
            for row in rows[:100]]
        observation["truncated"] = len(rows) > 100 or observation.get("truncated", False)
        payload["observation"] = observation
        for attempt in range(3):
            await asyncio.sleep(max(0,self.next_request-time.monotonic()))
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role":"system","content":SYSTEM},
                              {"role":"user","content":json.dumps(payload,ensure_ascii=False)}],
                    response_format={"type":"json_schema","json_schema":{
                        "name":schema.__name__,"strict":True,"schema":schema.model_json_schema()}},
                    temperature=0.1,max_completion_tokens=3000)
                self.next_request = time.monotonic()+4
                if not response.choices or not response.choices[0].message.content:
                    raise RuntimeError("Groq returned no structured content")
                if response.choices[0].finish_reason != "stop":
                    raise RuntimeError("Groq structured output was incomplete")
                try:
                    return schema.model_validate_json(response.choices[0].message.content)
                except ValidationError:
                    if attempt == 2:
                        raise
                    payload["schema_repair"] = "Previous structured response violated semantic validation. Ensure text targets have a nonempty exact target.name; provide valid action fields and assertions."
            except RateLimitError as error:
                if attempt == 2:
                    raise
                try:
                    delay = min(30,max(2,float(error.response.headers.get("retry-after","15"))))
                except ValueError:
                    delay = 15
                self.next_request = time.monotonic()+delay

def create_planner(settings):
    return GroqPlanner(settings) if settings.ai_provider=="groq" else OpenAIPlanner(settings)