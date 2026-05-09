# Changelog

All notable changes to CV Updater are documented here.
Format: `vMAJOR.MINOR.PATCH — YYYY-MM-DD`

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
