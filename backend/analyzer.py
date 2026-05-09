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


# ── Job analysis ──────────────────────────────────────────────────────────────

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


# ── Company analysis ──────────────────────────────────────────────────────────

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


# ── Match scoring ─────────────────────────────────────────────────────────────

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


# ── Summary pipeline ──────────────────────────────────────────────────────────

def _extract_anchor_fact(job_analysis: dict, base_cv_text: str) -> str:
    """Stage 1: Pick the single strongest quantified achievement from the CV for this role."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": f"""From this CV, identify the single most relevant quantified achievement to anchor a professional summary for the role below.

ROLE: {job_analysis.get('job_title', 'Unknown')}
KEY REQUIREMENTS: {', '.join(job_analysis.get('key_requirements', [])[:5])}

CV:
{base_cv_text[:4000]}

Return ONLY the anchor fact as a short phrase (10-20 words). It must contain a real number, rank, percentage, or scale directly from the CV. Example: "ranked #1 in revenue generation across a 300+ publisher portfolio for three consecutive quarters". No explanation, no full stop."""}]
    )
    return response.content[0].text.strip()


def _write_summary(anchor_fact: str, job_analysis: dict, base_cv_text: str, prior_feedback: str = "") -> str:
    """Stage 2: Write one summary using the pre-selected anchor fact."""
    feedback_block = (
        f"\nPRIOR ATTEMPT FEEDBACK — fix these specifically:\n{prior_feedback}\n"
        if prior_feedback else ""
    )
    keywords = ", ".join(job_analysis.get("ats_keywords", [])[:6])

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": f"""Write a professional CV summary. Return ONLY the summary text, nothing else.

ANCHOR FACT (use near the start, verbatim or very close): {anchor_fact}
ROLE: {job_analysis.get('job_title', 'Unknown')}
ATS KEYWORDS TO INCLUDE NATURALLY (pick 2-4): {keywords}
{feedback_block}
RULES — follow every one without exception:
1. Implied subject only — start sentences with verbs or nouns. NEVER use "I", "She", "He", "They", or any pronoun.
2. 60-70 words exactly. Count every word before returning.
3. Do NOT name any company — not AdMaven, not the hiring company, not any other employer.
4. No soft-skill claims: banned phrases include "trusted advisor", "consultative", "passionate", "results-driven", "detail-oriented", "dynamic", "motivated", "team player", "strong communicator".
5. Anchor fact must appear in the first or second sentence.
6. Final sentence: one specific factual positioning statement. Not a pitch, not flattery toward anyone.

CV FOR CONTEXT (do not invent facts not present here):
{base_cv_text[:3000]}

{TONE_GUIDE}"""}]
    )
    return response.content[0].text.strip()


def _validate_and_fix(summary: str, company_name: str) -> str:
    """Stage 3: Python-validate for hard violations; one targeted Claude fix if needed."""
    # Hard-truncate word count first
    words = summary.split()
    if len(words) > 70:
        truncated = ' '.join(words[:70])
        last_period = truncated.rfind('.')
        summary = truncated[:last_period + 1] if last_period > len(truncated) * 0.7 else truncated

    issues = []

    if re.search(r'\b(she|he|they|her|his|their)\b', summary, re.IGNORECASE):
        issues.append(
            "Remove all third-person pronouns (she/he/they/her/his/their). "
            "Rewrite those sentences with implied subject — start with a verb or noun instead."
        )

    if company_name and company_name.lower() in summary.lower():
        issues.append(f"Remove all mentions of '{company_name}'. Do not name any company.")

    banned = [
        "results-driven", "proven track record", "passionate", "dedicated",
        "dynamic", "motivated", "trusted advisor", "consultative", "detail-oriented",
        "team player", "strong communicator", "hard worker",
    ]
    for phrase in banned:
        if phrase.lower() in summary.lower():
            issues.append(f"Remove the phrase '{phrase}' — it is a banned soft-skill assertion.")

    if issues:
        fix_prompt = (
            "Fix ONLY these specific issues in the text below. "
            "Do not change anything else. Return only the fixed text, nothing else.\n\n"
            "ISSUES TO FIX:\n"
            + "\n".join(f"- {i}" for i in issues)
            + "\n\nTEXT:\n" + summary
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": fix_prompt}]
        )
        summary = response.content[0].text.strip()
        # Re-truncate in case fix crept over limit
        words = summary.split()
        if len(words) > 70:
            summary = ' '.join(words[:70])

    return summary


def _score_summary(summary: str, job_analysis: dict, anchor_fact: str) -> dict:
    """Stage 4: Score the summary 0-10 against a fixed rubric. Returns score + feedback."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": f"""You are a senior CV reviewer. Score this professional summary against the rubric. Return ONLY valid JSON.

SUMMARY:
{summary}

ROLE: {job_analysis.get('job_title', '')}
ANCHOR FACT THAT SHOULD APPEAR: {anchor_fact}

RUBRIC (score each 0-2, total 0-10):
1. anchor_fact: Quantified achievement specific, real, and prominent? (0=missing/vague, 1=present but buried, 2=strong and leads)
2. implied_subject: Zero pronouns (I/She/He/They/her/his/their)? Sentences start with verbs or nouns? (0=pronoun found, 2=clean)
3. no_company_flattery: No company name, no pitch to the employer? (0=violates, 2=clean)
4. no_soft_skills: No personality-trait claims ("trusted advisor", "consultative", "passionate", etc.)? (0=multiple violations, 1=one, 2=none)
5. relevance: Does the framing connect her background to what THIS specific role needs? (0=generic, 1=partial, 2=specific)

Return exactly: {{"score": <integer 0-10>, "feedback": "<specific actionable feedback on what to fix, or Passes all criteria if score >= 7>"}}"""}]
    )
    try:
        return _parse_json(response.content[0].text)
    except Exception:
        return {"score": 0, "feedback": "Scoring failed — retrying."}


def generate_summary(job_analysis: dict, base_cv_text: str, tahel_profile: str) -> str:
    """
    Generate a professional summary using a decomposed, validated, scored pipeline.

    Stage 1: Extract anchor fact (focused Claude call)
    Stage 2: Write summary using anchor fact (focused Claude call)
    Stage 3: Python validate + targeted Claude fix
    Stage 4: Score against rubric (Claude) — retry Stage 2-3 up to 5 times until score >= 7
    """
    anchor_fact = _extract_anchor_fact(job_analysis, base_cv_text)

    best_summary = ""
    best_score = -1
    prior_feedback = ""

    for attempt in range(5):
        summary = _write_summary(anchor_fact, job_analysis, base_cv_text, prior_feedback)
        summary = _validate_and_fix(summary, job_analysis.get("company_name", ""))
        result = _score_summary(summary, job_analysis, anchor_fact)

        score = result.get("score", 0)
        if score > best_score:
            best_score = score
            best_summary = summary

        if score >= 7:
            break

        prior_feedback = result.get("feedback", "")

    return best_summary


# ── CV tailoring ──────────────────────────────────────────────────────────────

def tailor_cv(
    job_analysis: dict,
    company_analysis: dict,
    match_gaps: dict,
    tahel_profile: str,
    base_cv_text: str = "",
) -> dict:
    """Edit the Base CV bullets to fit a specific role. Returns dict with bullets per employer.
    Summary is generated separately via generate_summary()."""
    keywords = ", ".join(job_analysis.get("ats_keywords", [])[:12])

    json_schema = """{
  "admaven_bullets": ["<bullet 1>", "<bullet 2>", "<bullet 3>"],
  "aa_financial_bullets": ["<bullet 1>", "<bullet 2>"],
  "adore_bullets": ["<bullet 1>", "<bullet 2>"]
}"""

    if base_cv_text.strip():
        instruction = f"""You are an expert CV editor. Edit Tahel's existing CV bullets to better fit this specific role.

Return ONLY valid JSON — no markdown fences, no explanation:
{json_schema}

WHAT TO EDIT:
- Rewrite bullets to lead with the skills and outcomes most relevant to THIS job
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
        instruction = f"""You are an expert CV writer. Write Tahel's CV bullets for this specific role.

Return ONLY valid JSON — no markdown fences, no explanation:
{json_schema}

RULES FOR BULLETS:
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
        max_tokens=2000,
        messages=[{"role": "user", "content": instruction}],
    )
    return _parse_json(response.content[0].text)
