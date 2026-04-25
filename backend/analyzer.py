import json
import os
import re
from pathlib import Path

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
MODEL = "claude-sonnet-4-6"

_TONE_PATH = Path(__file__).parent.parent / "Tone.md"
TONE_GUIDE = _TONE_PATH.read_text() if _TONE_PATH.exists() else ""


def _parse_json(text: str) -> dict:
    """Strip markdown fences if present, then parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def analyze_job(job_text: str) -> dict:
    """Extract structured info from raw job posting text."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Analyze this job posting. Return ONLY valid JSON — no markdown, no explanation.

JOB POSTING:
{job_text}

Return exactly this structure:
{{
    "company_name": "...",
    "job_title": "...",
    "seniority": "Junior | Mid | Senior | Lead | Manager | Director | VP | C-Level",
    "company_url": "homepage URL or null",
    "ideal_candidate_summary": "2-3 sentences describing the ideal candidate",
    "key_requirements": ["...", "..."],
    "ats_keywords": ["...", "..."],
    "nice_to_haves": ["...", "..."],
    "company_description": "brief description of the company from the posting"
}}

For ats_keywords: include every technical skill, tool, methodology, certification, and domain term that an ATS would scan for. Include both spelled-out and abbreviated forms where relevant (e.g. "Search Engine Optimization (SEO)")."""
        }]
    )
    return _parse_json(response.content[0].text)


def research_company(company_name: str, company_text: str, news: list[dict]) -> dict:
    """Summarize company research from website content and news."""
    news_block = "\n".join(
        f"- {n['title']}: {n['snippet']}" for n in news[:4]
    ) or "No recent news found."

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Summarize company research for a job applicant. Return ONLY valid JSON.

COMPANY: {company_name}

WEBSITE CONTENT:
{company_text[:5000] or "Not available."}

RECENT NEWS:
{news_block}

Return exactly this structure:
{{
    "summary": "2-3 sentence overview of what the company does",
    "mission_values": "their stated mission or core values",
    "market_position": "their market position, key differentiators, or notable competitors",
    "growth_stage": "startup | scale-up | established | enterprise",
    "key_talking_points": [
        "Specific insight worth mentioning in a cover letter or interview",
        "Another specific insight",
        "Another"
    ],
    "recent_highlights": [
        "Recent news item worth referencing to show research depth",
        "Another"
    ]
}}"""
        }]
    )
    return _parse_json(response.content[0].text)


def calculate_match_and_gaps(job_analysis: dict, tahel_profile: str) -> dict:
    """Score fit and identify CV gaps between Tahel's profile and the job."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Compare Tahel's profile to the job requirements. Return ONLY valid JSON.

TAHEL'S PROFILE:
{tahel_profile}

JOB REQUIREMENTS:
{json.dumps(job_analysis, indent=2)}

Return exactly this structure:
{{
    "match_score": <integer 1-100>,
    "match_rationale": "2-3 sentences explaining the score honestly",
    "strong_matches": ["Area where Tahel is a strong fit", "..."],
    "gaps": [
        {{
            "gap": "Specific missing skill or experience",
            "importance": "high | medium | low",
            "suggestion": "How to address or minimise this gap in the CV"
        }}
    ],
    "cv_strategy": "Overall CV tailoring strategy — what to lead with, what to emphasise, what to de-emphasise"
}}"""
        }]
    )
    return _parse_json(response.content[0].text)


def tailor_cv(
    job_analysis: dict,
    company_research: dict,
    match_gaps: dict,
    tahel_profile: str,
) -> str:
    """Generate full tailored CV text grounded entirely in Tahel's real experience."""
    keywords = ", ".join(job_analysis.get("ats_keywords", [])[:12])

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""You are an expert CV writer. Rewrite Tahel's CV for this specific role.

STRICT RULES:
- Every claim must be real and traceable to her profile below — do NOT invent anything
- Naturally weave in these ATS keywords: {keywords}
- Use strong action verbs (Led, Grew, Built, Managed, Launched, Closed, Delivered, etc.)
- Quantify achievements wherever the profile supports it
- Keep content to 1–2 pages worth of text

TONE AND WRITING RULES (follow without exception):
{TONE_GUIDE}

TAHEL'S PROFILE (source of truth):
{tahel_profile}

JOB ANALYSIS:
{json.dumps(job_analysis, indent=2)}

COMPANY RESEARCH:
{json.dumps(company_research, indent=2)}

TAILORING STRATEGY:
{json.dumps(match_gaps, indent=2)}

Write the CV with these clearly labelled sections:
1. PROFESSIONAL SUMMARY (3–4 sentences, front-load keywords, show fit for this role)
2. CORE SKILLS (grouped, ATS-optimised bullet list)
3. PROFESSIONAL EXPERIENCE (for each role: Job Title | Company | Dates | Location, then 4–6 bullet points)
4. EDUCATION
5. CERTIFICATIONS & LANGUAGES (if applicable)

Return clean plain text only — no markdown headers with #, no asterisks for bold."""
        }]
    )
    return response.content[0].text
