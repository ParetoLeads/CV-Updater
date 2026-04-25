# CV Updater — Claude Project Memory

## Project Purpose
A simple web application that takes a CV template and tailors it for a specific job position. Used privately by Nathan and his wife. Not public-facing.

## Repository
- GitHub: https://github.com/ParetoLeads/CV-Updater
- Local: /Users/nathanshapiro/Desktop/CV Updater

## Versioning Convention
- `v0.x.x` — foundation/pre-release
- `v1.x.x` — first working application
- `vX.0.0` — major redesign or breaking change
- `v1.X.0` — new feature
- `v1.0.X` — bug fix only

To revert to a version: `git checkout v2.0.0`
To list all versions: `git tag`

## Tech Stack
_To be decided as we build. Update this section when choices are made._

## File Structure
_To be updated as the project grows._

```
CV Updater/
├── CLAUDE.md         ← this file (Claude's memory)
├── CHANGELOG.md      ← version history
├── ISSUES.md         ← bug/problem tracker
└── ...               ← app files (TBD)
```

## Dev Commands
_To be added when app is built._

## Key Decisions
_Record important architectural or design choices here, with reasoning._

---

## Lessons Learned

### v0.1.0 — 2026-04-25
- Project foundations established: CLAUDE.md, CHANGELOG.md, ISSUES.md
- Versioning uses git tags for easy rollback
- CLAUDE.md is auto-loaded by Claude Code each session, making it the primary mechanism for continuity across sessions
