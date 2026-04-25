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
GOOGLE_SHEET_ID=            ← auto-created on first run if blank
```

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

## Key Decisions
- **SSE streaming**: used for real-time progress (not polling) — better UX for a ~60s process
- **tahel_profile.md as source of truth**: Claude is instructed to never invent experience
- **Base CV as edit target**: Claude edits the actual Base CV text rather than writing from scratch — better output quality, preserves Tahel's voice and structure
- **Base CV is read-only**: the app copies it, edits the copy — the original is never modified
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
- Google service account preferred over OAuth for simplicity in a private tool
- Tavily API used for news (designed for AI agents, cleaner than raw search)
- local_config.json stores auto-created Sheet ID without polluting .env
