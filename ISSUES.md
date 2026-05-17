# Issues Tracker

## Open Issues
_No open issues._

---

## Resolved Issues

### [#20] CV output over one page — spotted v2.5.2, fixed v2.6.0
`_replace_bullets_in_doc` inserts new paragraph objects when Claude returns more bullets than the original .docx had. With "2-4 bullets per role" and no length constraint, Claude frequently returned 4 per role across 3 roles, growing the doc beyond the original page count. Fixed by capping `new_bullets` to the length of the existing bullet paragraphs in `_replace_bullets_in_doc`, and adding a 15-22 word per-bullet length constraint to `tailor_cv`.

### [#19] "Summarising" SSE event had no matching frontend step — spotted v2.5.0, fixed v2.6.0
`main.py` fires a `summarising` SSE event but the STEPS array in `app.js` had no `{ id: "summarising", ... }` entry. The step silently had no effect — the "Tailoring CV content" step stayed active during summary generation with no visual feedback. Fixed by adding the step between "tailoring" and "creating".

### [#18] Stream closing without "complete" event left UI in silent hanging state — spotted v2.6.0, fixed v2.6.0
If the server disconnected mid-run (Railway timeout, network drop), the SSE reader loop exited but no error was shown. User had no indication anything went wrong and no way forward. Fixed by tracking a `completed` flag; if the loop exits without setting it, `markStepError` is called.

### [#17] Tone.md had old S1/S2 order, conflicting with v2.5.1 prompt — spotted v2.6.0, fixed v2.6.0
Tone.md "Professional Summary Rules" said S1=identity, S2=achievement. v2.5.1 switched these in the actual writing prompt. Since Tone.md is injected at the end of every `_write_summary` call, the conflict was live and contributing to template-feel outputs. Fixed by updating Tone.md to match the current structure.

### [#16] Summary pipeline wrote blind — missing cv_strategy, company context, tailored bullets — spotted v2.6.0, fixed v2.6.0
`generate_summary` had job title, keywords, base_cv_text, role_pillars, and gap_skills — but no knowledge of the tailoring strategy, the company's current focus, or what bullets were written. The summary couldn't echo the document's own themes. Fixed by passing `cv_strategy`, `company_context`, and the first bullet per employer (`tailored_bullets`) into `generate_summary` and through to `_write_summary`.

### [#15] tailor_cv had no explicit gap skill prohibition — spotted v2.5.0, fixed v2.6.0
Gap skills were embedded in the match_gaps JSON passed as strategy context, but there was no dedicated prohibition block. Claude could interpret the gaps as "things to address" and include them anyway. Fixed by extracting gap_skills before the tailor_cv call in main.py and passing them as an explicit `SKILLS SHE DOES NOT HAVE` block, matching the pattern already used in the summary pipeline.

### [#14] Summary hallucinated Salesforce despite gap analysis identifying it as missing — spotted v2.5.0, fixed v2.5.2
Gap analysis correctly flagged Salesforce as a skill Tahel doesn't have. Summary still claimed "Salesforce-driven pipeline forecasting" because `generate_summary` received ATS keywords (which included Salesforce from the JD) with no knowledge of the gap list. Fixed by extracting gap skill names from `match_gaps.gaps` in `main.py` and passing them as a prohibition block to Stage 1 (`_extract_ingredients`) and Stage 2 (`_write_summary`) of the summary pipeline.

---

## Resolved Issues

### [#13] Summary contained filler sentences and missing professional identity — spotted v2.3.0, fixed v2.4.0
Output passed all hard validation checks (no pronouns, no company name, word count OK) but contained sentences with no concrete information — "this record reflects consistent performance across full account lifecycles", "Partner success and account management expertise spans programmatic monetization across diverse publisher portfolios". Root cause: Stage 2 prompt gave only negative rules, leaving Claude free to fill space with vague-but-compliant filler. Second issue: no identity sentence (title + years + domain) in sentence 1, which ATS research shows is the highest-impact line. Fixed by: expanding Stage 1 to return identity/anchor/skills as a dict; rewriting Stage 2 with a 4-sentence structure guide and a voice contract banning template constructions; adding `professional_identity`, `information_density`, and `natural_voice` to the Stage 4 rubric.

### [#12] Summary generation produced third-person, over-limit, company-naming output — spotted v2.2.0, fixed v2.3.0
Single Claude call was doing too many jobs simultaneously: pick the anchor achievement, write the summary, self-police against a dozen rules, and count words accurately. Something always slipped — third-person pronouns ("she"), company name mentioned, >70 words, soft-skill assertions. Prompt tightening failed repeatedly. Fixed by decomposing into 4 focused stages: (1) isolated anchor-fact extraction, (2) single-job summary writing, (3) Python validation + targeted Claude fix, (4) rubric-based scorer with retry loop (up to 5 attempts, threshold 7/10).

---

## Resolved Issues

### [#11] Nixpacks ignored `-r backend/requirements.txt` include — spotted v2.2.0, fixed v2.2.0
Root `requirements.txt` used `-r backend/requirements.txt` to delegate to the backend file. Nixpacks parsed but didn't recursively follow the include, so `python-docx` (and other packages) were never installed. App crashed on startup with `ModuleNotFoundError: No module named 'docx'`. Fixed by copying the full package list directly into root `requirements.txt`.

---

## Resolved Issues

### [#10] Output CV lost all formatting — spotted v1.3.0, fixed v1.5.0
`create_tailored_cv_doc` was deleting all content from the copied Google Doc and inserting plain text, destroying all fonts, sizes, bold headers, and spacing. Fixed by downloading the Base CV as `.docx`, applying tailored content with python-docx (replacing only paragraph text, preserving run formatting), and uploading/converting back to Google Doc.

---

### [#9] JS syntax error blocked entire app — spotted v1.4.2, fixed v1.4.3
Stray `);` on line 264 of `app.js` (leftover from when `processRequest` was an inline addEventListener callback, before it was extracted to a named function). Caused the whole JS file to fail parsing — health check never ran, status items stayed grey, submit button stayed permanently disabled.
Fixed by changing `});` to `}` to correctly close the function declaration.

---

### [#8] Company page discovery unreliable — guessing common paths — spotted v1.4.0, fixed v1.4.2
Scraper was trying hardcoded paths like `/about`, `/about-us`, `/product`, `/solutions` to find company pages.
Broke on any site that used non-standard URL structures (e.g. `/who-we-are`, `/platform`, `/our-story`).
Fixed by extracting internal links from the homepage's nav, header, and footer elements, then scoring them by keyword match. Falls back to common paths only if nav extraction returns nothing.

---

### [#7] Company URL not discovered when absent from job posting — spotted v1.3.0, fixed v1.4.1
If the job description didn't mention the company website, the scraper had no URL to work with.
Company analysis step would proceed with no website data, producing generic output.
Fixed by calling Tavily with `"{company_name}" official website` to auto-discover the URL when missing.

---

### [#6] CV quality poor when generated from scratch — spotted v1.2.0, fixed v1.3.0
Asking Claude to write Tahel's CV from scratch produced generic, overly polished output that didn't sound like her.
Structure and formatting drifted from her actual Base CV, making it harder to apply directly.
Fixed by reading the Base CV as plain text from Google Drive and passing it to Claude as the document to edit.
Claude now rewrites bullet points and the summary, but preserves section order, job titles, dates, and facts.

---

### [#5] Health check was slow and expensive — live API call on every load — spotted v1.3.0, fixed v1.4.0
`check_anthropic()` was making a real API call (`client.messages.create`) on every health check to verify connectivity.
Added latency, consumed tokens, and could fail for transient reasons unrelated to the key being valid.
Fixed by replacing the live call with key format validation (`starts with sk-ant-`). Fast and free.

---

### [#4] Python 3.9 incompatibility in `check_duplicate` — spotted v1.2.0, fixed v1.2.0
`check_duplicate` used `dict | None` union type hint, which is only valid in Python 3.10+.
App crashed at startup on Python 3.9 with `TypeError: unsupported operand type(s) for |`.
Fixed by removing the return type annotation entirely.

---

### [#3] LinkedIn URLs caused silent failure — spotted v0.4.0, fixed v0.5.0
Submitting a LinkedIn job URL caused the scraper to hang or return empty content (LinkedIn requires auth).
No user-facing error — the pipeline would proceed with blank job text and produce garbage output.
Fixed by detecting LinkedIn URLs explicitly, raising `LinkedInURLError`, and switching the UI to paste mode with a clear explanation.

---

### [#2] Google credentials path resolution broken — spotted v0.3.0, fixed v0.5.0
`google_client.py` used a relative path to find `client_secrets.json` and `token.json`.
When the server was started from the project root (via `start.sh`), the working directory was `backend/`, making the relative path resolve to the wrong location.
Fixed by resolving all credential paths relative to the file's location (`__file__`) rather than the working directory.

---

### [#1] Progress screen broken on submit — spotted v0.2.0, fixed v0.4.0
Steps were added to the DOM dynamically as events arrived from the SSE stream.
On first click, the progress section appeared empty until the first event fired — jarring visual.
Duplicate step name `"researching"` appeared twice because two different events used the same label.
No elapsed timer, so users had no sense of how long the process was taking.
Fixed by pre-rendering all 9 steps as `pending` on submit, adding a live elapsed timer, and correcting all step labels.

---

## How to Use This File
- When a bug or problem is spotted, add it under **Open Issues** with the date and a short description
- When it's fixed, move it to **Resolved Issues** and note which version fixed it

### Open Issue Format
```
### [#N] Short description — YYYY-MM-DD
Description of the problem and how to reproduce it.
```

### Resolved Issue Format
```
### [#N] Short description — spotted vX.X.X, fixed vX.X.X
What the problem was and how it was resolved.
```
