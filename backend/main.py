import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).parent.parent / ".env")

from scraper import scrape_url, clean_pasted_text
from analyzer import analyze_job, research_company, calculate_match_and_gaps, tailor_cv
from news_search import search_recent_news
from google_client import create_tailored_cv_doc, log_to_sheet
from health_check import run_all_checks
from logger import logger

app = FastAPI(title="CV Updater")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
TAHEL_PROFILE_PATH = Path(__file__).parent.parent / "tahel_profile.md"


class JobRequest(BaseModel):
    input_type: str  # "url" or "paste"
    content: str


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

        yield _event("scraping", "Extracting job description...")
        if req.input_type == "url":
            logger.info(f"Processing job URL: {req.content[:80]}")
            job_text = scrape_url(req.content)
            job_url = req.content
        else:
            logger.info("Processing pasted job description")
            job_text = clean_pasted_text(req.content)
            job_url = ""

        yield _event("analyzing", "Analyzing job requirements and ATS keywords...")
        job_analysis = analyze_job(job_text)
        logger.info(f"Job analyzed: {job_analysis.get('company_name')} — {job_analysis.get('job_title')}")

        company_url = (job_analysis.get("company_url") or "").strip()
        company_text = job_analysis.get("company_description", "")
        if company_url:
            yield _event("researching", f"Scraping {job_analysis.get('company_name', 'company')} website...")
            try:
                company_text = scrape_url(company_url)
            except Exception as e:
                logger.warning(f"Company scrape failed ({company_url}): {e}")

        yield _event("news", "Searching for recent company news...")
        news = search_recent_news(job_analysis.get("company_name", ""))
        logger.info(f"News search returned {len(news)} results")

        yield _event("researching", "Synthesising company research...")
        company_research = research_company(
            job_analysis.get("company_name", ""), company_text, news
        )

        yield _event("matching", "Scoring fit and identifying CV gaps...")
        match_gaps = calculate_match_and_gaps(job_analysis, tahel_profile)
        logger.info(f"Match score: {match_gaps.get('match_score')}/100")

        yield _event("tailoring", "Tailoring CV content...")
        tailored_cv = tailor_cv(job_analysis, company_research, match_gaps, tahel_profile)

        yield _event("creating", "Creating tailored Google Doc...")
        cv_url = create_tailored_cv_doc(tailored_cv, job_analysis)
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
            "company_research": company_research,
            "match_gaps": match_gaps,
            "news": news,
            "cv_url": cv_url,
            "sheet_url": sheet_url,
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
