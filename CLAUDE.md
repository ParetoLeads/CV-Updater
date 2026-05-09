# CV Updater — Claude Project Memory

## Project Purpose
A private web application that tailors Tahel's CV for specific job applications.
Used by Nathan and Tahel on their home network. Not public-facing.

## Repository
- GitHub: https://github.com/ParetoLeads/CV-Updater
- Local: /Users/nathanshapiro/Desktop/CV Updater

## Versioning Convention
- `v0.x.x` — foundation / pre-release
- `v1.x.x` — first working application
- `vX.0.0` — major redesign or breaking change
- `v1.X.0` — new feature added
- `v1.0.X` — bug fix only

To revert to a version: `git checkout v2.0.0`
To list all versions: `git tag`

## Tech Stack
| Layer | Choice |
|-------|--------|
| Backend | Python 3.11+ + FastAPI |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| AI | Claude API — claude-sonnet-4-6 |
| Web scraping | requests + BeautifulSoup4 |
| News search | Tavily API |
| Google integration | google-api-python-client (Docs + Sheets + Drive) |
| Local hosting | uvicorn, `--host 0.0.0.0` for home network access |

## File Structure
```
CV Updater/
├── CLAUDE.md                  ← this file (Claude's memory)
├── CHANGELOG.md               ← version history
├── ISSUES.md                  ← bug/problem tracker
├── Tone.md                    ← writing style rules injected into every CV tailoring call
├── tahel_profile.md           ← source of truth for experience, skills, career prefs
├── .env                       ← secrets (not committed)
├── local_config.json          ← auto-created runtime config (not committed)
├── start.sh                   ← one-command server start
├── backend/
│   ├── main.py                ← FastAPI app + SSE streaming endpoint
│   ├── scraper.py             ← URL scraping + paste cleaning
│   ├── analyzer.py            ← Claude API: job analysis, company research, gap scoring, CV tailoring
│   ├── news_search.py         ← Tavily news search
│   ├── google_client.py       ← Google Drive/Docs/Sheets: folder creation, Base CV copy, PDF export
│   ├── health_check.py        ← API key + credential validation; powers the status card in UI
│   ├── logger.py              ← structured logging to console + logs/cv_updater.log
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## Google Drive Structure (output)
```
GOOGLE_OUTPUT_FOLDER_ID/
├── Tahel Tabacznik - Base CV   ← READ ONLY — source doc, never edited by the app
├── {Company Name}/             ← auto-created per application
│   ├── Tahel Tabacznik - CV    ← Google Doc (editable, copy of Base CV with tailored text)
│   └── Tahel Tabacznik - CV    ← PDF export of the same content
└── Tahel — Job Applications Tracker   ← Google Sheet (auto-created)
```

## Dev Commands
```bash
# Start the server (creates venv + installs deps on first run)
chmod +x start.sh && ./start.sh

# Or manually
cd backend && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Access
# Nathan's Mac:   http://localhost:8080
# Wife's device:  http://<Mac local IP>:8080
```

## Required Environment Variables (.env)
```
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
GOOGLE_OUTPUT_FOLDER_ID=    ← Drive folder ID where company subfolders are created
GOOGLE_CV_TEMPLATE_ID=          ← optional: file ID of "Tahel Tabacznik - Base CV" (app searches by name if blank)
GOOGLE_SHEET_ID=            ← auto-created on first run if blank; set explicitly on Railway (see local_config.json)
```

## Railway Deployment (online access for Tahel)
Additional env vars required on Railway:
```
GOOGLE_TOKEN_JSON=   ← full contents of token.json (paste raw JSON); replaces browser OAuth flow on server
APP_USERNAME=        ← HTTP Basic Auth username (share with Tahel)
APP_PASSWORD=        ← HTTP Basic Auth password (share with Tahel)
GOOGLE_SHEET_ID=     ← must be set explicitly; local_config.json is ephemeral on Railway
```
Current GOOGLE_SHEET_ID value: `1-TsMoRaTQ4kpl2y94EvS1vzP4hUWoTqRow5Q2i7YthQ`

Railway config files: `railway.toml` (build/start command), root `requirements.txt` (delegates to `backend/requirements.txt`)

**Local dev unaffected**: `APP_USERNAME`/`APP_PASSWORD` absent → auth bypassed. `GOOGLE_TOKEN_JSON` absent → existing `token.json` + `client_secrets.json` OAuth flow used as before.

## Google API Setup (one-time)
1. Go to console.cloud.google.com → create project "CV Updater"
2. Enable: Google Docs API, Google Drive API, Google Sheets API
3. Create OAuth 2.0 credentials (Desktop app type) → download as `client_secrets.json` in project root
4. A browser sign-in window opens on first run; `token.json` is saved and reused after that
5. The tracking Sheet is auto-created on first run

## Application Flow
1. User inputs job URL or pastes description
2. Duplicate check: after analysis, the app reads the tracker sheet — if same company+title already exists, shows a friendly card with the existing CV link and options to go back or force-reprocess
3. Backend streams progress via SSE:
   - Scrape / clean job text
   - Claude analyzes: company, title, seniority, ideal candidate, ATS keywords
   - Duplicate check against tracker sheet
   - Scrape company website
   - Tavily searches recent news (last ~6 months)
   - Claude synthesizes company research
   - Claude scores match + identifies CV gaps against tahel_profile.md
   - Read Base CV text (exported as plain text from Drive) — passed to Claude as the document to edit
   - Claude **edits** the Base CV: adjusts tone, rewrites bullet emphasis per role, weaves in ATS keywords; does NOT rewrite from scratch
   - Google Drive: create/reuse company subfolder → copy Base CV → replace text with tailored version → export PDF
   - Google Sheets: log row with checkbox in Submitted? column
4. UI shows full results: analysis, company intel, news, match score, gaps, links

## Standing Rule: Documentation
After every response where you make code changes, update these files before finishing:
- **CHANGELOG.md** — add a version entry if the change is significant, or note it under the current version
- **CLAUDE.md** — update the file structure, Key Decisions, or Lessons Learned if anything changed
- **ISSUES.md** — add any bugs discovered; move to Resolved when fixed

This applies to every code change, no matter how small.

---

## Key Decisions
- **SSE streaming**: used for real-time progress (not polling) — better UX for a ~60s process
- **tahel_profile.md as source of truth**: Claude is instructed to never invent experience
- **Base CV as edit target**: Claude edits the actual Base CV text rather than writing from scratch — better output quality, preserves Tahel's voice and structure
- **Base CV is read-only**: the app downloads it as .docx, applies changes to a copy — the original is never modified
- **python-docx for formatting**: `tailor_cv` returns structured JSON (summary + bullets per company); `create_tailored_cv_doc` applies it to the .docx via python-docx, replacing only paragraph text while preserving all run formatting (font, size, bold, spacing), then uploads/converts to Google Doc
- **Tone.md injected on every run**: writing rules (no em dashes, no AI buzzwords, natural voice) are injected into every tailor_cv call
- **OAuth2 for Google**: files are owned by Nathan's Google account (service accounts have no Drive storage)
- **Vanilla JS frontend**: no build step, works on any device on the network

---

## Lessons Learned

### v0.1.0 — 2026-04-25
- Project foundations established: CLAUDE.md, CHANGELOG.md, ISSUES.md
- Versioning uses git tags for easy rollback
- CLAUDE.md is auto-loaded by Claude Code each session

### v0.2.0 — 2026-04-25
- Full application built: FastAPI backend + vanilla JS frontend
- SSE chosen over polling for real-time progress feedback
- tahel_profile.md is the single source of truth for CV content
- OAuth2 used for Google (not service accounts) — files are owned by Nathan's account and live in his Drive
- Tavily API used for news (designed for AI agents, cleaner than raw search)
- local_config.json stores auto-created Sheet ID without polluting .env

### v0.3.0 — 2026-04-25
- Health check endpoint added; validates all API keys and Google credentials before the user can submit
- File + console logging added for debugging production issues without SSH

### v0.4.0 — 2026-04-25
- Progress steps pre-rendered on submit (not added dynamically) — avoids layout shift and makes state transitions cleaner
- Questionnaire file removed; tahel_profile.md is the single source of truth from this point forward

### v0.5.0 — 2026-04-25
- Playwright added as a fallback scraper for JS-heavy job pages
- Detection heuristic: look for unrendered template patterns (`{{...}}`, `[object Object]`) to decide when to use it

### v1.1.0 — 2026-04-25
- Duplicate detection prevents re-processing the same role — checks company + job title (case-insensitive) against tracker sheet
- `force: true` flag lets user bypass duplicate check when needed
- Tone.md injected into every tailor_cv call to enforce consistent writing style

### v1.2.0 — 2026-04-25
- Each application now gets its own company subfolder in Google Drive
- PDF exported alongside the Google Doc — gives Tahel a ready-to-send file

### v1.3.0 — 2026-04-25
- Switched from generating CV from scratch to editing the Base CV — output quality is significantly better; Tahel's voice and structure are preserved
- Base CV is exported as plain text from Drive and passed to Claude as the document to edit

### v1.4.0 — 2026-04-25
- Three-source company analysis (website + news + job description) produces much richer context than website alone
- GOOGLE_CV_TEMPLATE_ID env var avoids a Drive-wide search on every run

### v1.4.1 — 2026-04-25
- Company URL is now auto-discovered via Tavily if absent from the job posting
- Scraping multiple page types (homepage, about, product) gives Claude better context than homepage alone

### v2.3.0 — 2026-05-09
- Prompt tightening alone cannot fix LLM self-policing failures. Asking one Claude call to simultaneously pick the right achievement, write the summary, count words, and police a dozen rules means something always slips.
- Generator-critic pattern: decompose into focused stages (extract anchor → write → validate → score). Each Claude call has one job. Python handles what Python is reliable at (word count, regex pronoun detection, substring match).
- `_validate_and_fix` catches hard violations programmatically (pronouns, company name, banned phrases, word count) and uses a single targeted fix prompt — not a full rewrite. This is faster and more reliable than asking Claude to self-correct.
- Rubric-based scoring with retry loop: score → feedback → rewrite until threshold reached (≥7/10, max 5 attempts). The scorer's structured feedback is injected into the next write attempt — Claude knows exactly what to fix, not just "try again".
- `tailor_cv` should return bullets only; summary runs as a separate pipeline. Combining them in one call makes the prompt too broad.

### v2.2.0 — 2026-05-09
- Deployed to Railway (Hobby plan): `railway.toml` + root `requirements.txt` added
- `InstalledAppFlow` browser auth can't run on a server; solution: store `token.json` contents as `GOOGLE_TOKEN_JSON` env var; `_creds()` reconstructs `Credentials.from_authorized_user_info()` and auto-refreshes. Local OAuth flow untouched.
- HTTP Basic Auth via Starlette `BaseHTTPMiddleware` — only way to protect both API routes and `StaticFiles` mount. FastAPI `Depends` doesn't apply to `StaticFiles`.
- `local_config.json` is ephemeral on Railway — always set `GOOGLE_SHEET_ID` as an explicit env var for cloud deployments

### v2.1.2 — 2026-05-06
- Summary generation now runs 5 candidates through a word-count filter (≤70 words); best survivor selected by a second Claude call; fallback trims the shortest candidate if none pass
- Anchor rule: must be a genuine achievement (ranking, scale, revenue) — basic job duties are disallowed as anchors to prevent "trying too hard" tone
- `_trim_to_70` and `_pick_best_summary` helpers added to `analyzer.py`

### v2.1.1 — 2026-05-06
- Professional summary rules tightened: 70-word hard max; must anchor on one quantified verifiable fact from the base CV; banned filler words list; no soft-skill assertions; no company flattery
- `summary_rules` extracted as a named block in `tailor_cv` so both the edit path and the fallback path share identical summary instructions

### v2.1.0 — 2026-05-02
- Input redesigned: two separate fields (Job URL for tracker, Job Description for analysis) — no URL scraping
- `job_description` drives all analysis; `job_url` is stored in the tracker only
- `create_tailored_cv_doc` now returns `(cv_url, folder_url)` tuple; `folder_url` passed to the complete event
- Results section uses `display:flex; gap:18px` so cards have consistent spacing
- 4 CTA buttons in 2x2 grid, each colored: blue/green/amber/purple with emoji
- System status card hidden on results page, restored on reset
- Em dashes cleaned from output: prompts + JS `cleanText()` post-processor

### v2.0.0 — 2026-04-29
- Results page fully redesigned: single-column layout with 7 distinct cards replacing the old 3-column grid
- Score card shows company/title/level on left, colour-coded match score on right, and italic rationale below a divider
- Gaps card is hidden when no gaps are returned — avoids empty card flash
- News feed removed from results view; power keywords shown as pill badges
- Max-width narrowed to 700px; mobile breakpoint moved to 600px

### v1.5.0 — 2026-04-29
- Output formatting now matches the base .docx (fonts, sizes, bold headers) — uses python-docx to apply tailored content to the .docx template before uploading to Drive
- `tailor_cv` returns JSON dict (summary + bullets per company); replaces prior plain-text approach

### v1.4.3 — 2026-04-29
- Stray `);` in `app.js` caused silent JS parse failure — entire health check and submit flow was dead

### v1.4.2 — 2026-04-25
- Nav/footer link extraction is more reliable than guessing common paths — works even when a site uses non-standard URL structures
