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
    "cv_strategy": "Overall CV tailoring strategy — what to lead with, what to emphasise, what to de-emphasise. Reference the company's current_focus and role_context to make this specific.",
    "role_pillars": [
        "2-3 short phrases (5-8 words each) describing what this specific role is fundamentally about",
        "Derived from THIS JD — not a fixed category. Examples: 'pipeline reporting and forecasting', 'CRM process optimisation', 'cross-team revenue alignment', 'programmatic ad operations at scale'",
        "Optional third pillar if the role clearly has one"
    ]
}}

Rules:
- role_pillars: return exactly 2-3 items. Each must be a concrete, JD-specific phrase — not generic labels like 'sales' or 'marketing'.
- Writing rule: never use em dashes (—) or en dashes (–). Use a comma or regular hyphen (-) instead."""
        }]
    )
    return _parse_json(response.content[0].text)


# ── Summary pipeline ──────────────────────────────────────────────────────────

def _extract_ingredients(job_analysis: dict, base_cv_text: str, gap_skills: list = None) -> dict:
    """Stage 1: Extract structured building materials for the summary (identity, anchor, skills)."""
    gap_block = (
        "\nSKILLS/TOOLS SHE DOES NOT HAVE — do NOT select any of these as skills:\n"
        + "\n".join(f"  - {g}" for g in gap_skills)
        + "\n"
        if gap_skills else ""
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": f"""From this CV, extract three building materials for a professional summary targeting the role below. Return ONLY valid JSON — no markdown, no explanation.

ROLE: {job_analysis.get('job_title', 'Unknown')}
KEY REQUIREMENTS: {', '.join(job_analysis.get('key_requirements', [])[:5])}
{gap_block}
CV:
{base_cv_text[:4000]}

Return exactly:
{{
  "identity": "a short identity fragment — job title mirroring the role + TOTAL career years across ALL roles in the CV (use the span from earliest to most recent role, not just the most recent domain) + domain (e.g. 'Senior Account Manager with 7 years in B2B sales and 3+ in programmatic AdTech'). Not a full sentence. No pronouns.",
  "anchor": "the single strongest quantified achievement directly from the CV. Must contain a real number, rank, percentage, or scale. Example: 'ranked #1 in revenue generation across a 300+ publisher portfolio for three consecutive quarters'. 10-20 words. No full stop.",
  "skills": "2-3 specific tools or domain capabilities most relevant to THIS role, named precisely. Example: 'HubSpot and Tableau for pipeline and performance tracking; publisher-side monetization strategy'. Not a generic list."
}}

Rules: every field must be grounded in the CV — do not invent. No em dashes."""}]
    )
    return _parse_json(response.content[0].text)


def _write_summary(ingredients: dict, job_analysis: dict, base_cv_text: str, prior_feedback: str = "", role_pillars: list = None, gap_skills: list = None, cv_strategy: str = "", company_context: str = "", tailored_bullets: dict = None) -> str:
    """Stage 2: Write one summary using pre-extracted building materials."""
    feedback_block = (
        f"\nPRIOR ATTEMPT FEEDBACK — fix these specifically:\n{prior_feedback}\n"
        if prior_feedback else ""
    )
    keywords = ", ".join(job_analysis.get("ats_keywords", [])[:6])
    pillars_block = (
        "\nROLE PILLARS — the 2-3 themes this role is fundamentally about:\n"
        + "\n".join(f"  - {p}" for p in role_pillars)
        + "\n"
        if role_pillars else ""
    )
    gap_block = (
        "\nSKILLS/TOOLS SHE DOES NOT HAVE — do NOT claim any of these, even if they appear in ATS keywords:\n"
        + "\n".join(f"  - {g}" for g in gap_skills)
        + "\n"
        if gap_skills else ""
    )
    strategy_block = (
        f"\nTAILORING FOCUS — the CV strategy for this role (let this guide what to emphasise):\n{cv_strategy}\n"
        if cv_strategy else ""
    )
    context_block = (
        f"\nCOMPANY CONTEXT — use this to inform the fit sentence if relevant:\n{company_context}\n"
        if company_context else ""
    )
    bullets_block = ""
    if tailored_bullets:
        previews = []
        for key in ("admaven_bullets", "aa_financial_bullets", "adore_bullets"):
            bullets = tailored_bullets.get(key, [])
            if bullets:
                previews.append(f"  - {bullets[0]}")
        if previews:
            bullets_block = "\nKEY THEMES IN THE TAILORED BULLETS — echo their language and framing in S3/S4:\n" + "\n".join(previews) + "\n"

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": f"""Write a professional CV summary. Return ONLY the summary text, nothing else.

BUILDING MATERIALS — use these, don't reinvent them:
  Identity: {ingredients.get('identity', '')}
  Anchor achievement: {ingredients.get('anchor', '')}
  Skills to feature: {ingredients.get('skills', '')}

ROLE: {job_analysis.get('job_title', 'Unknown')}
{gap_block}ATS KEYWORDS — weave in 1-2 naturally (only if they reflect real experience): {keywords}
{pillars_block}{strategy_block}{context_block}{bullets_block}{feedback_block}
WHAT THE READER SHOULD KNOW AFTER READING:
  1. One specific thing she achieved, at scale — lead with this. Number first. Confident, not boastful. Past employer may be named (e.g. "at AdMaven"). Do NOT name the hiring company.
  2. Who she is: title, years of experience, domain.
  3. What makes her distinctly effective in this type of role — a combination, a behaviour, an approach. Not a list of tools.
  4. Why her background is a natural fit here — only if you can say it in one clean sentence, not a template.

Write 3 to 4 sentences. Start with the accomplishment. Structure the rest however flows naturally.

EXAMPLE — the tone and rhythm to aim for (not the exact words):
"Ranked #1 in revenue generation across 300+ publisher accounts for three consecutive quarters at AdMaven. Senior Account Manager with 7 years in B2B sales, including 3+ in programmatic AdTech. Builds publisher revenue through Tableau-driven traffic analysis and hands-on account strategy, not just relationship management. High-volume B2C sales background brings the conversion instinct and persistence that enterprise account growth needs."

HARD RULES:
  - No pronouns (I/she/he/they/her/his/their). Implied subject only.
  - Do NOT name the hiring company. Past employer names (e.g. AdMaven) are fine.
  - No soft-skill assertions: passionate, results-driven, detail-oriented, trusted advisor, dynamic, motivated, team player.
  - Banned phrases: "Specializing in...", "Expertise spans...", "this record reflects...", "brings a wealth of...".
  - 55-70 words total. Count carefully.

CV FOR CONTEXT — do not invent facts not present here:
{base_cv_text[:3000]}

{TONE_GUIDE}"""}]
    )
    return response.content[0].text.strip()


def _validate_and_fix(summary: str, company_name: str, gap_skills: list = None) -> str:
    """Stage 3: Python-validate for hard violations; one targeted Claude fix if needed."""
    # Fix missing spaces between sentences unconditionally
    summary = re.sub(r'\.(\S)', r'. \1', summary)

    # Hard-truncate word count
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

    if re.search(r'\b(Uses|Applies|Leverages|Employs)\b.{0,40}\bto\b', summary, re.IGNORECASE):
        issues.append(
            "Remove any sentence structured as '[Tool/verb] [tool name] to [outcome]'. "
            "Rewrite to describe what she does and achieves, not a tool she uses."
        )

    if re.search(r'[Aa] background.*?translates', summary):
        issues.append(
            "Remove the phrase 'A background in X translates...' — it is a banned template construction. "
            "Rewrite to make the same point in more direct, natural language."
        )

    banned = [
        "results-driven", "proven track record", "passionate", "dedicated",
        "dynamic", "motivated", "trusted advisor", "consultative", "detail-oriented",
        "team player", "strong communicator", "hard worker",
    ]
    for phrase in banned:
        if phrase.lower() in summary.lower():
            issues.append(f"Remove the phrase '{phrase}' — it is a banned soft-skill assertion.")

    if gap_skills:
        for skill in gap_skills:
            if skill and skill.lower() in summary.lower():
                issues.append(f"Remove mention of '{skill}' — she does not have this skill or experience.")

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


def _score_summary(summary: str, job_analysis: dict, anchor: str) -> dict:
    """Stage 4: Score the summary 0-10 against a fixed rubric. Returns score + feedback."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": f"""You are a senior CV reviewer. Score this professional summary against the rubric. Return ONLY valid JSON.

SUMMARY:
{summary}

ROLE: {job_analysis.get('job_title', '')}
ANCHOR ACHIEVEMENT THAT SHOULD APPEAR: {anchor}

RUBRIC (score each 0-2, total 0-10):
1. anchor_fact: Does the quantified achievement open the summary as sentence 1, stated confidently with the number or rank first? (0=missing or vague, 1=present but not leading — buried in sentence 2 or later, 2=leads as sentence 1 with the number first)
2. professional_identity: Does the summary establish who she is — role title, experience level, domain — by sentence 2 at the latest? (0=identity never appears, 1=title or domain present but incomplete, 2=clean identity: role + years + domain, appears in sentence 1 or 2)
3. information_density: Does every sentence contain a concrete claim — a number, named tool, domain term, or specific skill? (0=one or more filler sentences with no concrete claim, 1=all sentences have claims but some are vague, 2=every sentence earns its place)
4. no_violations: Free of pronouns, the hiring company name, and soft-skill assertions? Past employer names (e.g. AdMaven) are allowed. (0=pronoun or hiring company name present, 1=one minor soft-skill claim, 2=completely clean)
5. natural_voice: Does it read like a confident professional, not a corporate template? Varied rhythm, no banned constructions ("Specializing in", "Expertise spans", "this record reflects", "Uses [tool] to [outcome]", "Leverages [tool] to [outcome]", etc.)? (0=template feel or banned constructions present, 1=mostly natural but one stiff sentence, 2=reads naturally with varied rhythm)

Return exactly: {{"score": <integer 0-10>, "feedback": "<specific actionable feedback on what to fix, or 'Passes all criteria' if score >= 7>"}}"""}]
    )
    try:
        return _parse_json(response.content[0].text)
    except Exception:
        return {"score": 0, "feedback": "Scoring failed — retrying."}


def generate_summary(job_analysis: dict, base_cv_text: str, tahel_profile: str, role_pillars: list = None, gap_skills: list = None, cv_strategy: str = "", company_context: str = "", tailored_bullets: dict = None) -> str:
    """
    Generate a professional summary using a decomposed, validated, scored pipeline.

    Stage 1: Extract building materials — identity fragment, anchor achievement, key skills
    Stage 2: Write summary using those ingredients
    Stage 3: Python validate + targeted Claude fix
    Stage 4: Score against rubric (Claude) — retry Stage 2-3 up to 5 times until score >= 7
    """
    ingredients = _extract_ingredients(job_analysis, base_cv_text, gap_skills)
    anchor = ingredients.get("anchor", "")

    best_summary = ""
    best_score = -1
    prior_feedback = ""

    for attempt in range(5):
        summary = _write_summary(
            ingredients, job_analysis, base_cv_text, prior_feedback,
            role_pillars, gap_skills, cv_strategy, company_context, tailored_bullets,
        )
        summary = _validate_and_fix(summary, job_analysis.get("company_name", ""), gap_skills)
        result = _score_summary(summary, job_analysis, anchor)

        score = result.get("score", 0)
        if score > best_score:
            best_score = score
            best_summary = summary

        if score >= 7 and len(summary.split()) <= 70:
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
    gap_skills: list = None,
) -> dict:
    """Edit the Base CV bullets to fit a specific role. Returns dict with bullets per employer.
    Summary is generated separately via generate_summary()."""
    ats_keywords = job_analysis.get("ats_keywords", [])
    priority_keywords = ", ".join(ats_keywords[:4])
    secondary_keywords = ", ".join(ats_keywords[4:10])
    role_pillars = match_gaps.get("role_pillars", [])
    role_pillars_formatted = "\n".join(f"- {p}" for p in role_pillars) if role_pillars else ""
    gap_prohibition = (
        "\nSKILLS SHE DOES NOT HAVE — do not include these in bullets, even if they appear in ATS keywords:\n"
        + "\n".join(f"- {g}" for g in gap_skills)
        + "\n"
        if gap_skills else ""
    )

    json_schema = """{
  "admaven_bullets": ["<bullet 1>", "<bullet 2>", "<bullet 3>"],
  "aa_financial_bullets": ["<bullet 1>", "<bullet 2>"],
  "adore_bullets": ["<bullet 1>", "<bullet 2>"]
}"""

    if base_cv_text.strip():
        instruction = f"""You are an expert CV editor. Edit Tahel's existing CV bullets to better fit this specific role.

Return ONLY valid JSON — no markdown fences, no explanation:
{json_schema}

ROLE PILLARS — what this role is fundamentally about:
{role_pillars_formatted}

For each employer section, order bullets so the one most directly relevant to these pillars comes first.
Relevance to the pillars takes priority over any other ordering.

WHAT TO EDIT:
- Rewrite bullets using the language and priorities of this specific role
- Adjust tone to match what the job description asks for
- 2-4 bullets per role
- Each bullet must fit on one line — 15 to 22 words maximum. Tight and specific.

WHAT NOT TO CHANGE:
- The facts and numbers — reframe HOW they are described, never change the actual figures
- Never add experience not in the base CV or profile
{gap_prohibition}
ATS KEYWORD PLACEMENT RULES:
Priority keywords (must appear — at least one per role section, ideally in the first bullet):
{priority_keywords}
Secondary keywords (use where they fit naturally — do not force all of them):
{secondary_keywords}

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

ROLE PILLARS — what this role is fundamentally about:
{role_pillars_formatted}

For each employer section, order bullets so the one most directly relevant to these pillars comes first.

RULES FOR BULLETS:
- Every claim must be real and traceable to her profile below — do NOT invent anything
- Use strong action verbs (Led, Grew, Built, Managed, Launched, Closed, Delivered, etc.)
- Quantify achievements wherever the profile supports it
- 2-4 bullets per role
- Each bullet must fit on one line — 15 to 22 words maximum. Tight and specific.
{gap_prohibition}
ATS KEYWORD PLACEMENT RULES:
Priority keywords (must appear — at least one per role section, ideally in the first bullet):
{priority_keywords}
Secondary keywords (use where they fit naturally — do not force all of them):
{secondary_keywords}

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
