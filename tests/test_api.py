import asyncio
import httpx
from app.config import Settings
from app.main import create_app
from .helpers import ScriptedPlanner, assertion

async def test_api_runs_real_browser_and_returns_report(local_site,tmp_path):
    planner=ScriptedPlanner([assertion("heading","visible","heading","Customer sign in")],
        [{"kind":"assert","assertion_id":"heading"},{"kind":"finish"}])
    app=create_app(Settings(_env_file=None,allow_localhost=True,artifacts_dir=tmp_path),lambda:planner)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
        token=(await client.get("/api/config")).json()["session_token"]
        response=await client.post("/api/runs",headers={"X-Runner-Token":token},
            json={"url":local_site+"/account.html","instruction":"Verify the sign in heading is shown."})
        assert response.status_code==202
        id=response.json()["id"]
        await app.state.tasks[id]
        report=(await client.get("/api/runs/"+id)).json()
        assert report["status"]=="PASS",report
        download=await client.get(f"/api/runs/{id}/report")
        assert download.status_code==200 and download.json()["assertions"]=={"heading":"PASS"}

async def test_api_rejects_cross_origin_mutation_without_session_token():
    app=create_app(Settings(_env_file=None))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
        response=await client.post("/api/runs",json={"url":"https://example.com","instruction":"Verify page heading."})
        assert response.status_code==403
async def test_static_javascript_has_executable_mime_type():
    app=create_app(Settings(_env_file=None))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
        response=await client.get("/static/app.js")
        assert response.status_code==200
        assert response.headers["content-type"].split(";")[0] in ("text/javascript","application/javascript")
        assert response.headers["x-content-type-options"]=="nosniff"
