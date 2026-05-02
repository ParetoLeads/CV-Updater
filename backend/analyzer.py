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

For ats_keywords: include every technical skill, tool, methodology, certification, and domain term that an ATS would scan for. Include both spelled-out and abbreviated forms where relevant (e.g. "Search Engine Optimization (SEO)").

Writing rule: never use em dashes (—) or en dashes (–). Use a comma or regular hyphen (-) instead."""
        }]
    )
    return _parse_json(response.content[0].text)


def build_company_analysis(
    company_name: str,
    company_text: str,
    news: list[dict],
    job_analysis: dict,
) -> dict:
    """Build a comprehensive Company Analysis from job description, website, and news."""
    news_block = "\n".join(
        f"- [{n.get('published_date', 'n/d')}] {n['title']}: {n['snippet']}"
        for n in news[:5]
    ) or "No recent news found."

    role_summary = (
        f"{job_analysis.get('job_title', 'Unknown role')} "
        f"({job_analysis.get('seniority', '')}) — "
        f"{job_analysis.get('ideal_candidate_summary', '')}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""You are building a Company Analysis for a job applicant.
Synthesise ALL three sources below. Return ONLY valid JSON — no fences, no explanation.

COMPANY: {company_name}

SOURCE 1 — COMPANY WEBSITE (homepage + about pages):
{company_text[:7000] or "Not available."}

SOURCE 2 — RECENT NEWS:
{news_block}

SOURCE 3 — THE ROLE BEING APPLIED FOR:
{role_summary}
Key requirements: {', '.join(job_analysis.get('key_requirements', [])[:6])}
Nice to haves: {', '.join(job_analysis.get('nice_to_haves', [])[:4])}

Return exactly this structure:
{{
    "overview": "2-3 sentences on what the company does and who they serve",
    "mission_values": "Their stated mission/core values — quote directly from the website where possible",
    "market_position": "Their positioning, key differentiators, notable competitors",
    "growth_stage": "startup | scale-up | established | enterprise",
    "current_focus": "What the company is actively pushing for right now — draw from news and strategic language on the site",
    "role_context": "How this specific role connects to the company's current goals — why are they hiring for this now",
    "key_themes": [
        "A specific theme from the company's identity Tahel should weave into her CV",
        "Another — be specific, not generic"
    ],
    "key_talking_points": [
        "A research-backed insight worth mentioning in a cover letter or interview",
        "Another that shows Tahel understands their current moment, not just their history"
    ],
    "recent_highlights": [
        "Concrete news item with approximate date",
        "Another if available"
    ]
}}

Rules:
- current_focus and recent_highlights: draw primarily from SOURCE 2
- mission_values and key_themes: draw primarily from SOURCE 1
- role_context: cross-reference SOURCE 3 with what you learned from 1 and 2
- Never invent facts; if a source is unavailable use the other two
- Never use em dashes (—) or en dashes (–) — use a comma or regular hyphen (-) instead"""
        }]
    )
    return _parse_json(response.content[0].text)


def calculate_match_and_gaps(job_analysis: dict, company_analysis: dict, tahel_profile: str) -> dict:
    """Score fit and identify CV gaps using job requirements, company context, and Tahel's profile."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Compare Tahel's profile to the job requirements and company context. Return ONLY valid JSON.

TAHEL'S PROFILE:
{tahel_profile}

JOB REQUIREMENTS:
{json.dumps(job_analysis, indent=2)}

COMPANY CONTEXT:
{json.dumps({
    "current_focus": company_analysis.get("current_focus", ""),
    "role_context": company_analysis.get("role_context", ""),
    "key_themes": company_analysis.get("key_themes", []),
    "growth_stage": company_analysis.get("growth_stage", ""),
}, indent=2)}

Return exactly this structure:
{{
    "match_score": <integer 1-100>,
    "match_rationale": "2-3 sentences explaining the score honestly — reference both the role requirements and the company's current focus",
    "strong_matches": ["Area where Tahel is a strong fit", "..."],
    "gaps": [
        {{
            "gap": "Specific missing skill or experience",
            "importance": "high | medium | low",
            "suggestion": "How to address or minimise this gap in the CV"
        }}
    ],
    "cv_strategy": "Overall CV tailoring strategy — what to lead with, what to emphasise, what to de-emphasise. Reference the company's current_focus and role_context to make this specific."
}}

Writing rule: never use em dashes (—) or en dashes (–). Use a comma or regular hyphen (-) instead."""
        }]
    )
    return _parse_json(response.content[0].text)


def tailor_cv(
    job_analysis: dict,
    company_analysis: dict,
    match_gaps: dict,
    tahel_profile: str,
    base_cv_text: str = "",
) -> dict:
    """Edit the Base CV to fit a specific role. Returns structured dict with summary + bullets per company."""
    keywords = ", ".join(job_analysis.get("ats_keywords", [])[:12])

    json_schema = """{
  "summary": "<rewritten professional summary — 3-5 sentences, speaks directly to this role and company>",
  "admaven_bullets": ["<bullet 1>", "<bullet 2>", "<bullet 3>"],
  "aa_financial_bullets": ["<bullet 1>", "<bullet 2>"],
  "adore_bullets": ["<bullet 1>", "<bullet 2>"]
}"""

    if base_cv_text.strip():
        instruction = f"""You are an expert CV editor. Edit Tahel's existing CV to better fit this specific role.

Return ONLY valid JSON — no markdown fences, no explanation:
{json_schema}

WHAT TO EDIT:
- summary: rewrite to speak directly to this role and company type
- Bullets for each role: rewrite to lead with the skills and outcomes most relevant to THIS job
- Weave in ATS keywords naturally — do not force them
- Adjust tone to match what the job description asks for
- 2-4 bullets per role

WHAT NOT TO CHANGE:
- The facts and numbers — reframe HOW they are described, never change the actual figures
- Never add experience not in the base CV or profile

ATS KEYWORDS TO WEAVE IN: {keywords}

TONE AND WRITING RULES (follow without exception):
{TONE_GUIDE}

BASE CV (edit this — keep all facts):
{base_cv_text}

JOB ANALYSIS:
{json.dumps(job_analysis, indent=2)}

COMPANY CONTEXT:
- Current focus: {company_analysis.get('current_focus', 'N/A')}
- Role context: {company_analysis.get('role_context', 'N/A')}
- Key themes: {', '.join(company_analysis.get('key_themes', []))}

TAILORING STRATEGY:
{json.dumps(match_gaps, indent=2)}"""
    else:
        instruction = f"""You are an expert CV writer. Write Tahel's CV for this specific role.

Return ONLY valid JSON — no markdown fences, no explanation:
{json_schema}

STRICT RULES:
- Every claim must be real and traceable to her profile below — do NOT invent anything
- Naturally weave in these ATS keywords: {keywords}
- Use strong action verbs (Led, Grew, Built, Managed, Launched, Closed, Delivered, etc.)
- Quantify achievements wherever the profile supports it
- 2-4 bullets per role

TONE AND WRITING RULES (follow without exception):
{TONE_GUIDE}

TAHEL'S PROFILE (source of truth):
{tahel_profile}

JOB ANALYSIS:
{json.dumps(job_analysis, indent=2)}

COMPANY ANALYSIS:
{json.dumps(company_analysis, indent=2)}

TAILORING STRATEGY:
{json.dumps(match_gaps, indent=2)}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": instruction}],
    )
    return _parse_json(response.content[0].text)
