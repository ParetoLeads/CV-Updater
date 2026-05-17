# Changelog

All notable changes to CV Updater are documented here.
Format: `vMAJOR.MINOR.PATCH — YYYY-MM-DD`

---

## v2.6.0 — 2026-05-17

### Changed

**Pipeline knowledge transfer (main.py + analyzer.py)**
- `generate_summary` now receives `cv_strategy` (the tailoring strategy from gap analysis), `company_context` (overview + current_focus from company_analysis), and `tailored_bullets` (first bullet per employer from the just-written CV). The summary is no longer written blind — it knows the strategy and can echo the same language as the bullets.
- `tailor_cv` now receives `gap_skills` as an explicit prohibition list. Previously, gaps were only embedded in the match_gaps JSON context. Now a dedicated `SKILLS SHE DOES NOT HAVE` block is injected into both the edit and fallback paths, matching the pattern already used in the summary pipeline.
- `gap_skills` now extracted from `match_gaps` before `tailor_cv` is called (previously extracted after, so it was only available to `generate_summary`).

**Summary pipeline — less rigid, better context (analyzer.py)**
- `_write_summary`: replaced rigid S1/S2/S3/S4 sentence-slot instructions with effect-based guidance ("what the reader should know after reading"). Gives Claude the destination, not the vehicle. Structure is now a recommendation, not a prescription.
- `_write_summary`: added one concrete few-shot example showing the desired tone and rhythm. One good example replaces half the banned-constructions list.
- `_write_summary`: trimmed the banned constructions list to hard/specific items only. Vague stylistic rules removed from the prompt — they belong in the rubric's `natural_voice` criterion or in Python validation, not as a growing list Claude navigates around.
- `_extract_ingredients`: max_tokens raised from 200 to 400 (previous limit may have been clipping the skills field). Identity extraction instruction tightened: now explicitly asks for total career years across all roles, not just the most recent domain tenure.
- `_validate_and_fix`: four new Python checks added:
  - Tool-to-outcome construction: regex for `\b(Uses|Applies|Leverages|Employs)\b.{0,40}\bto\b`
  - Background-translates template: regex for `[Aa] background.*?translates`
  - Gap skills: substring match against the gap_skills list
  - Missing spaces between sentences: unconditional `re.sub(r'\.(\S)', r'. \1', summary)`
- `generate_summary`: retry loop now requires both `score >= 7` AND `len(words) <= 70` to exit. Previously a 75-word summary could score 7/10 and ship.

**Page length (google_client.py + analyzer.py)**
- `_replace_bullets_in_doc`: new bullets are now capped at the original paragraph count before the replacement loop. Previously, if Claude returned more bullets than the original doc had, new paragraph objects were inserted and the document grew beyond one page.
- `tailor_cv`: added per-bullet length guidance to both edit and fallback paths: "Each bullet must fit on one line — 15 to 22 words maximum."

**Housekeeping**
- `Tone.md`: updated "Professional Summary Rules" to match current (v2.5.1) structure — S1 = achievement, S2 = identity. Was reversed, creating conflicting instructions since Tone.md is injected into every `_write_summary` call.
- `frontend/app.js`: added "Generating professional summary" step to the STEPS array (between tailoring and creating). Previously the `summarising` SSE event had no matching step element.
- `frontend/app.js`: added end-of-stream safety net — if the stream closes without a `complete` event, the UI now shows an error instead of silently hanging in the progress state.

---

## v2.5.2 — 2026-05-17

### Fixed
- **Summary hallucination bug:** Summary was claiming gap skills (e.g. Salesforce) despite the gap analysis correctly identifying them as missing. Root cause: `generate_summary` had no knowledge of identified gaps. Fix: gap skill names extracted from `match_gaps.gaps` in `main.py` and passed through `generate_summary` → `_extract_ingredients` (Stage 1) and `_write_summary` (Stage 2) as an explicit prohibition block.
- **Rigid S3 voice ("Uses [tool] to [outcome]"):** S3 instruction rewritten from "Capability" (tool inventory) to "Edge" — what makes her distinctly effective, as a pitch rather than a job description. "Uses [tool] to [outcome]" and "Leverages [tool] to [outcome]" added to banned constructions in both the prompt and the rubric's `natural_voice` criterion.

---

## v2.5.1 — 2026-05-17

### Changed
- Summary S1 is now achievement-first (narrative hook) instead of identity-first. S1 leads with the anchor achievement — number or rank first, stated with confidence. Past employers may be named in S1 (e.g. "at AdMaven"). S2 now carries the identity context (role title, years, domain).
- `_score_summary` rubric updated to match: `anchor_fact` now requires the achievement to lead as sentence 1 (not "leads or immediately follows identity"); `professional_identity` now checks for identity by sentence 2 (not sentence 1); `no_violations` updated to allow past employer names while still banning the hiring company name.
- `_write_summary` voice rules updated: S1 guidance added ("land like a fact, not a boast — lead with the number"); hiring company ban now explicitly scoped to the hiring company only (past employers allowed).

---

## v2.5.0 — 2026-05-17

### Changed
- `calculate_match_and_gaps` now returns a `role_pillars` field: 2-3 short JD-specific phrases describing what this role is fundamentally about (e.g. "pipeline reporting and forecasting", "CRM process optimisation"). Derived fresh from each JD — flexible alternative to rigid role archetypes.
- `tailor_cv` keyword injection refactored: ATS keywords now split into `priority_keywords` (top 4, must appear — at least one per role section, ideally in the first bullet) and `secondary_keywords` (5-10, used where natural). Replaces the previous vague "weave in naturally" instruction.
- `tailor_cv` bullet ordering now explicitly driven by `role_pillars`: first bullet of each employer section must be the one most relevant to the role pillars, not generic relevance. Instruction is concrete and pillar-referenced, not prose.
- `generate_summary` and `_write_summary` accept optional `role_pillars` param; pillars are passed to S3 (capability) and S4 (fit) sentence guidance so the summary echoes the same themes as the bullets.
- `main.py`: `role_pillars` extracted from `match_gaps` and passed to `generate_summary` after tailoring.

---

## v2.4.0 — 2026-05-09

### Changed
- Stage 1 `_extract_anchor_fact` renamed to `_extract_ingredients`; now returns a JSON dict with three building-material fields (`identity`, `anchor`, `skills`) instead of a single anchor phrase — gives Stage 2 richer, pre-selected inputs for all four sentences
- Stage 2 `_write_summary` rewritten: replaces 6 negative rules with a positive 4-sentence structure guide (S1=identity, S2=proof, S3=capability, S4=fit) plus an explicit voice contract banning template constructions ("Specializing in...", "Expertise spans...", "this record reflects...", etc.)
- Stage 4 `_score_summary` rubric overhauled: `implied_subject` + `no_company_flattery` + `no_soft_skills` collapsed into `no_violations` (Python already catches these); `relevance` replaced by two new criteria — `professional_identity` (does sentence 1 establish title/years/domain?) and `natural_voice` (does it read like a person, not a template?); `information_density` added (does every sentence contain a concrete claim?)
- `Tone.md` Professional Summary Rules updated to match the 4-sentence structure guide

---

## v2.3.0 — 2026-05-09

### Changed
- Professional summary generation replaced with a 4-stage decomposed pipeline in `analyzer.py`:
  - Stage 1 `_extract_anchor_fact`: isolated Claude call picks the single strongest quantified achievement from the base CV for this specific role (returns 10-20 word phrase only)
  - Stage 2 `_write_summary`: isolated Claude call writes one summary using the pre-selected anchor fact; 6 strict rules, no company name passed in
  - Stage 3 `_validate_and_fix`: Python hard-validates (word count, third-person pronouns, company name, banned phrases); one targeted Claude fix call only if violations found
  - Stage 4 `_score_summary`: rubric-based Claude scorer (0-10, 5 criteria × 0-2 each); returns score + specific feedback
- Retry loop: if score < 7, Stage 2-3 re-run with scorer feedback injected; up to 5 attempts; best-scoring version returned if threshold never reached
- `tailor_cv` simplified: no longer generates the summary; returns bullets only (`admaven_bullets`, `aa_financial_bullets`, `adore_bullets`)
- `main.py`: `generate_summary` called separately after `tailor_cv`; result merged into the dict before passing to `create_tailored_cv_doc`

### Removed
- `_trim_to_70`, `_pick_best_summary` helpers (replaced by Stage 3 Python validation)
- `summary_candidates` JSON field and `summary_rules` block from `tailor_cv` prompt

---

## v2.2.0 — 2026-05-09

### Added
- Railway deployment support: `railway.toml` (build + start command) and root `requirements.txt` (full package list duplicated from `backend/requirements.txt` — Nixpacks doesn't follow `-r` includes)
- HTTP Basic Auth middleware in `main.py` — protects all routes and static files; controlled by `APP_USERNAME` / `APP_PASSWORD` env vars; bypassed when not set (local dev unaffected)
- Cloud Google auth path in `google_client._creds()` — reads `GOOGLE_TOKEN_JSON` env var, reconstructs credentials, auto-refreshes expired access token; returns early without touching `client_secrets.json` or browser flow
- Cloud Google health check path in `health_check.check_google()` — validates `GOOGLE_TOKEN_JSON` env var and reports status correctly on Railway

---

## v2.1.2 — 2026-05-06

### Changed
- Summary generation now produces 5 distinct candidates per run; Python filters to those ≤70 words; the best survivor is selected via a second lightweight Claude call; if no candidates pass, the shortest is trimmed to fit
- Summary rules tightened: anchor fact must be a genuine achievement (ranking, scale, revenue) — basic job duties ("tracked CTR and eCPM") are explicitly disallowed as anchors
- `summary_candidates` replaces the single `summary` field in the JSON schema; post-processing resolves it to `summary` before returning

## v2.1.1 — 2026-05-06

### Changed
- Professional summary prompt rewritten with strict, enforceable rules: 70-word hard limit; must include one quantified verifiable fact from the base CV; banned word list (results-driven, passionate, proven track record, etc.); no soft-skill assertions; no company flattery. Rules extracted into a `summary_rules` block shared by both the base-CV-edit and fallback paths.

---

## v2.1.0 — 2026-05-02

### Changed
- Input section redesigned: toggle replaced with two separate fields - Job URL (optional, saved to tracker) and Job Description (required, used for analysis)
- Job URL is stored in the tracker for reference; no URL scraping happens - the pasted description is always used for analysis
- Analyze & Tailor CV button is now full width with a lift-and-glow hover effect
- Result cards now have consistent 18px gaps between them
- Match rationale text changed from italic muted-grey to normal black body text
- Progress steps now go green individually as each step completes (browser yield fix)
- 4 CTA buttons replace the previous 3, arranged in a 2x2 grid, each with a unique color and emoji: View tailored CV (blue), Open tracker (green), View Drive (amber), Start new (purple)
- System status card hides when the results page is shown; restores on Start new

### Added
- View Drive button links to the company's Google Drive folder for the application
- Em dash cleanup: prompts instruct Claude not to use em dashes; JS post-processes any that slip through

### Fixed
- Missing gap between result section cards (results section now uses flex + 18px gap)

---

## v2.0.0 — 2026-04-29

### Changed
- Results page completely redesigned: replaced 3-column grid layout with a clean single-column design (7 sections, 700px max-width)
- Job header card: company name + title · level on left, colour-coded match score on right, match rationale in italic below divider
- Company overview, role summary, key insights (→ bullets, max 3), CV gaps (amber blocks, hidden if none), and power keyword pills now each occupy their own card
- Three CTA buttons (View tailored CV / Open tracker / Start new) replace old action links
- Mobile responsive at 600px — CTA buttons stack vertically
- Removed news feed card from results view

---

## v1.5.0 — 2026-04-29

### Changed
- Output CV now preserves the formatting and design of the Base CV docx (fonts, sizes, bold headers, spacing)
- `tailor_cv` now returns structured JSON (summary + bullets per company) instead of plain text
- `create_tailored_cv_doc` downloads the Base CV as `.docx`, applies tailored content via python-docx (replacing only paragraph text, preserving all run formatting), then uploads and converts to Google Doc
- Added `python-docx` dependency

### Fixed
- Previous approach (delete all → insert plain text) destroyed all formatting — now all formatting is preserved

---

## v1.4.3 — 2026-04-29

### Fixed
- Syntax error in `app.js` (stray `);` on line 264) caused the entire JS file to fail parsing — health check never ran, status stayed grey, submit button stayed disabled

---

## v1.4.2 — 2026-04-25

### Changed
- Company page discovery now uses nav/header/footer links extracted from the homepage instead of guessing common paths like `/about`

---

## v1.4.1 — 2026-04-25

### Added
- Auto-discovers company URL via Tavily if the job posting doesn't include one
- Scrapes multiple page types (homepage, about, product) for richer company context

---

## v1.4.0 — 2026-04-25

### Added
- Three-source Company Analysis pipeline: synthesises company website, recent news, and job description context into a structured brief
- `GOOGLE_CV_TEMPLATE_ID` env var for direct Base CV lookup (avoids Drive-wide search)

### Changed
- Removed hardcoded role categories from tailor prompt; CV strategy now comes entirely from the gap analysis output

---

## v1.3.0 — 2026-04-25

### Changed
- CV tailoring now edits the Base CV text rather than generating from scratch — preserves Tahel's voice, structure, and document formatting

---

## v1.2.0 — 2026-04-25

### Added
- Company subfolder created in Google Drive for each application
- PDF export of tailored CV saved alongside the Google Doc

### Fixed
- Python 3.9 compatibility: replaced `dict | None` type hint with untyped annotation in `check_duplicate`

---

## v1.1.0 — 2026-04-25

### Added
- Duplicate detection: checks tracker sheet before processing; shows existing CV link with option to force-reprocess
- `Submitted?` checkbox column in tracker spreadsheet
- `Tone.md` writing guidelines injected into every CV tailoring prompt
- LinkedIn URL handling: detects LinkedIn URLs, shows a friendly error, and switches UI to paste mode

---

## v0.5.0 — 2026-04-25

### Added
- Playwright headless browser fallback for JS-rendered job pages (detects unrendered template patterns)

### Fixed
- Google credentials path resolution

---

## v0.4.0 — 2026-04-25

### Fixed
- Progress screen: pre-renders all steps upfront, adds elapsed timer, corrects step label names

### Changed
- Removed questionnaire file; `tahel_profile.md` now used directly as the source of truth

---

## v0.3.0 — 2026-04-25

### Added
- `backend/health_check.py` — validates API keys and Google credentials on startup; powers the status card in the UI
- `backend/logger.py` — structured logging to both console and `logs/cv_updater.log`

---

## v0.2.0 — 2026-04-25

### Added
- Full application: FastAPI backend + vanilla HTML/CSS/JS frontend
- `backend/main.py` — FastAPI app with SSE streaming endpoint `/api/process`
- `backend/scraper.py` — URL scraping and paste cleaning (BeautifulSoup)
- `backend/analyzer.py` — Claude API calls: job analysis, company research, match scoring, CV tailoring
- `backend/news_search.py` — Tavily API integration for recent company news
- `backend/google_client.py` — Google Docs (copy template, write tailored CV) + Sheets (auto-create tracker, log rows)
- `frontend/index.html` — Clean single-page UI with URL/paste toggle
- `frontend/style.css` — Responsive design, works on mobile
- `frontend/app.js` — SSE streaming client, real-time progress steps, results rendering
- `start.sh` — One-command server start with local IP displayed for wife's device
- `.env.example` — Template for required environment variables
- `.gitignore` — Excludes secrets, venv, and local config

### Flow
Job input → scrape/clean → Claude job analysis → company scrape → news search →
Claude company research → Claude match score + gaps → Claude CV tailoring →
Google Doc creation → Google Sheets logging → results displayed in UI

---

## v0.1.0 — 2026-04-25

### Added
- CLAUDE.md — project memory file, auto-loaded by Claude Code each session
- CHANGELOG.md — version history
- ISSUES.md — living bug and problem tracker
- GitHub repository connected with version tagging workflow
