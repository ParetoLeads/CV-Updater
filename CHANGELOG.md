# Changelog

All notable changes to CV Updater are documented here.
Format: `vMAJOR.MINOR.PATCH — YYYY-MM-DD`

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
