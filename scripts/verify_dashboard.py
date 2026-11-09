import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright,expect
from app.config import Settings
from app.browser import BrowserSession
from app.security import NavigationPolicy,Redactor

async def main():
    out=Path("artifacts/ui-validation")
    out.mkdir(parents=True,exist_ok=True)
    result={}
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        page=await browser.new_page(viewport={"width":1440,"height":1100})
        errors=[]
        page.on("pageerror",lambda error:errors.append(type(error).__name__))
        await page.goto("http://127.0.0.1:8765/")
        await expect(page.get_by_role("heading",name="Define a test")).to_be_visible()
        await page.get_by_role("button",name="Run offline sample").click()
        await expect(page.locator("#status")).to_have_text("PASS",timeout=30000)
        result["offline_dashboard_browser_workflow"]="PASS (scripted planner, not AI)"
        await page.screenshot(path=str(out/"desktop.png"),full_page=True)
        await page.set_viewport_size({"width":390,"height":844})
        await page.screenshot(path=str(out/"mobile.png"),full_page=True)
        result["mobile_overflow"]=await page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert result["mobile_overflow"] is False
        await page.set_viewport_size({"width":1440,"height":1100})
        configured = await (await page.request.get("http://127.0.0.1:8765/api/config")).json()
        if not configured["api_key_configured"]:
            await page.get_by_role("button",name="Run AI test").click()
            await expect(page.locator("#status")).to_have_text("ERROR",timeout=30000)
            await expect(page.locator("#reason")).to_contain_text("OPENAI_API_KEY")
            result["missing_key_feedback"]="ERROR correctly shown; no fabricated pass"
        else:
            result["missing_key_feedback"]="Not exercised: an API key is configured; no paid call was made by this smoke script."
        result["frontend_js_errors"]=errors
        assert not errors
        live=await browser.new_page()
        policy=NavigationPolicy("https://phptravels.com/demo")
        session=BrowserSession(live,policy,Redactor({}),15000)
        await live.route("**/*",session.guard)
        try:
            await live.goto("https://phptravels.com/demo",wait_until="domcontentloaded",timeout=45000)
            heading=live.get_by_role("heading",name="PHPTRAVELS live demo: travel booking software, no credit card",exact=True)
            await expect(heading).to_be_visible(timeout=15000)
            result["phptravels_browser_smoke"]="Known public demo heading visible in real Chromium. No AI planning or login attempted."
            await live.screenshot(path=str(out/"phptravels.png"),mask=[live.locator("input")])
        except Exception as ex:
            result["phptravels_browser_smoke"]="UNVERIFIED: "+type(ex).__name__
        await browser.close()
    (out/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
asyncio.run(main())