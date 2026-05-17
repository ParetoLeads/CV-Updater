import base64
import hmac
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

load_dotenv(Path(__file__).parent.parent / ".env")

from scraper import scrape_company_pages, clean_pasted_text
from analyzer import analyze_job, build_company_analysis, calculate_match_and_gaps, tailor_cv, generate_summary
from news_search import search_recent_news, find_company_url
from google_client import create_tailored_cv_doc, log_to_sheet, check_duplicate, read_base_cv_text
from health_check import run_all_checks
from logger import logger

app = FastAPI(title="CV Updater")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        username = os.getenv("APP_USERNAME", "")
        password = os.getenv("APP_PASSWORD", "")
        if not username or not password:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                req_user, req_pass = decoded.split(":", 1)
                if hmac.compare_digest(req_user, username) and hmac.compare_digest(req_pass, password):
                    return await call_next(request)
            except Exception:
                pass
        return StarletteResponse(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="CV Updater"'},
        )


app.add_middleware(BasicAuthMiddleware)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
TAHEL_PROFILE_PATH = Path(__file__).parent.parent / "tahel_profile.md"


class JobRequest(BaseModel):
    job_url: str = ""        # stored in tracker only — not scraped
    job_description: str     # used for all analysis
    force: bool = False


def _event(step: str, message: str, data: dict = None) -> str:
    payload = {"step": step, "message": message}
    if data:
        payload["data"] = data
    return f"data: {json.dumps(payload)}\n\n"


async def _process_stream(req: JobRequest):
    try:
        if not TAHEL_PROFILE_PATH.exists():
            msg = "tahel_profile.md not found. Please fill in tahel_questionnaire.md and convert it first."
            logger.error(msg)
            yield _event("error", msg)
            return
        tahel_profile = TAHEL_PROFILE_PATH.read_text()

        yield _event("scraping", "Preparing job description...")
        logger.info("Processing pasted job description")
        job_text = clean_pasted_text(req.job_description)
        job_url = req.job_url.strip()

        yield _event("analyzing", "Analyzing job requirements and ATS keywords...")
        job_analysis = analyze_job(job_text)
        logger.info(f"Job analyzed: {job_analysis.get('company_name')} — {job_analysis.get('job_title')}")

        if not req.force:
            dup = check_duplicate(job_analysis.get("company_name", ""), job_analysis.get("job_title", ""))
            if dup:
                logger.info(f"Duplicate detected: {dup['company']} — {dup['title']} (logged {dup['date']})")
                yield _event("duplicate", f"Looks like you already tailored a CV for this one! {dup['company']} — {dup['title']} was processed on {dup['date']}.", dup)
                return

        company_url = (job_analysis.get("company_url") or "").strip()
        if not company_url:
            company_name = job_analysis.get("company_name", "")
            if company_name:
                logger.info(f"No company URL in job post — searching for {company_name} website...")
                company_url = find_company_url(company_name)
                if company_url:
                    logger.info(f"Company URL found: {company_url}")
                else:
                    logger.warning(f"Could not find company URL for: {company_name}")

        company_text = job_analysis.get("company_description", "")
        if company_url:
            yield _event("company_scrape", f"Researching {job_analysis.get('company_name', 'company')} website and About page...")
            try:
                company_text = scrape_company_pages(company_url)
            except Exception as e:
                logger.warning(f"Company scrape failed ({company_url}): {e}")

        yield _event("news", "Searching for recent company news...")
        news = search_recent_news(job_analysis.get("company_name", ""))
        logger.info(f"News search returned {len(news)} results")

        yield _event("company_analysis", "Building Company Analysis...")
        company_analysis = build_company_analysis(
            job_analysis.get("company_name", ""), company_text, news, job_analysis
        )

        yield _event("matching", "Scoring fit and identifying CV gaps...")
        match_gaps = calculate_match_and_gaps(job_analysis, company_analysis, tahel_profile)
        logger.info(f"Match score: {match_gaps.get('match_score')}/100")

        yield _event("tailoring", "Tailoring CV content...")
        base_cv_text = read_base_cv_text()
        tailored_cv = tailor_cv(job_analysis, company_analysis, match_gaps, tahel_profile, base_cv_text)

        yield _event("summarising", "Generating professional summary...")
        role_pillars = match_gaps.get("role_pillars", [])
        gap_skills = [g.get("gap", "") for g in match_gaps.get("gaps", []) if g.get("gap")]
        tailored_cv["summary"] = generate_summary(job_analysis, base_cv_text, tahel_profile, role_pillars, gap_skills)

        yield _event("creating", "Creating tailored Google Doc...")
        cv_url, folder_url = create_tailored_cv_doc(tailored_cv, job_analysis)
        logger.info(f"CV doc created: {cv_url}")

        yield _event("logging", "Logging to application tracker...")
        sheet_url = log_to_sheet(
            job_analysis,
            match_gaps.get("match_score", 0),
            cv_url,
            job_url,
        )
        logger.info(f"Logged to sheet: {sheet_url}")

        yield _event("complete", "Done!", {
            "job_analysis": job_analysis,
            "company_analysis": company_analysis,
            "match_gaps": match_gaps,
            "news": news,
            "cv_url": cv_url,
            "sheet_url": sheet_url,
            "folder_url": folder_url,
        })

    except Exception as e:
        logger.error(f"Process failed: {e}", exc_info=True)
        yield _event("error", str(e))


@app.post("/api/process")
async def process_job(req: JobRequest):
    return StreamingResponse(
        _process_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health-check")
async def health_check():
    result = run_all_checks()
    for name, check in result["checks"].items():
        level = "info" if check["status"] == "ok" else "warning" if check["status"] == "warning" else "error"
        getattr(logger, level)(f"Health check [{name}]: {check['message']}")
    return result


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "tahel_profile_ready": TAHEL_PROFILE_PATH.exists(),
    }


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
