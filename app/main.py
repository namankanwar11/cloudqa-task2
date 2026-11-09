import asyncio
import os
import mimetypes
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from dotenv import dotenv_values
from .config import ROOT, Settings
from .models import Approval, RunRequest
from .runner import Runner, TERMINAL

STATIC = Path(__file__).with_name("static")

def create_app(settings=None, planner_factory=None):
    settings = settings or Settings()
    runs, tasks = {}, {}
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        yield
        for task in tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    app = FastAPI(title="CloudQA AI Browser Test Runner", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.state.runs, app.state.tasks = runs, tasks

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method not in ("GET", "HEAD") and not secrets.compare_digest(request.headers.get("X-Runner-Token", ""), token):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Missing local session token"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/demo")
    async def demo():
        return FileResponse(STATIC / "demo.html")

    @app.get("/api/config")
    async def config():
        return {"session_token": token, "model": settings.openai_model,
            "api_key_configured": bool(settings.openai_api_key.get_secret_value()),
            "allow_localhost": settings.allow_localhost, "max_steps": settings.max_steps}

    def get_run(run_id):
        if run_id not in runs:
            raise HTTPException(404, "Run not found (in-memory index resets on restart)")
        return runs[run_id]

    @app.post("/api/runs", status_code=202)
    async def start(request: RunRequest):
        if any(not task.done() for task in tasks.values()):
            raise HTTPException(409, "One run is already active; finish or cancel it first")
        if len(runs) >= 100:
            raise HTTPException(429, "This local session reached 100 runs; restart the app")
        aliases = {k.removeprefix("TEST_SECRET_"): v for k, v in
                   (dict(dotenv_values(ROOT / ".env")) | dict(os.environ)).items() if k.startswith("TEST_SECRET_") and v}
        from pydantic import SecretStr
        request.secrets = {k: SecretStr(v) for k, v in aliases.items()} | request.secrets
        planner = planner_factory() if planner_factory else None
        runner = Runner(settings, request, planner=planner)
        runs[runner.id] = runner
        tasks[runner.id] = asyncio.create_task(runner.run())
        return {"id": runner.id}

    @app.get("/api/runs/{run_id}")
    async def report(run_id: str):
        return get_run(run_id).report

    @app.post("/api/runs/{run_id}/approval")
    async def approve(run_id: str, request: Approval):
        try:
            get_run(run_id).decide(request.token, request.approve)
        except ValueError as ex:
            raise HTTPException(409, str(ex)) from None
        return {"accepted": True}

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        get_run(run_id)
        tasks[run_id].cancel()
        return {"accepted": True}

    @app.get("/api/runs/{run_id}/report")
    async def download(run_id: str):
        runner = get_run(run_id)
        if runner.report.status not in TERMINAL:
            raise HTTPException(409, "Report is not final yet")
        return FileResponse(runner.directory / "report.json", filename=f"{run_id}.json")

    @app.get("/api/runs/{run_id}/screenshots/{filename}")
    async def screenshot(run_id: str, filename: str):
        runner = get_run(run_id)
        import re
        if not re.fullmatch(r"step-\d{3}\.png", filename):
            raise HTTPException(404)
        path = runner.directory / filename
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path)

    return app

app = create_app()