# Career Copilot MVP

A private, local-first career assistant that behaves like a skeptical senior headhunter. It analyzes jobs, explains every match using verified career facts, and drafts tailored materials without applying or inventing experience.

## What this MVP does

- Stores a persistent career profile separately from the unchanged master resume
- Accepts a pasted job description (and records an optional source URL)
- Scores experience, skills, seniority, and preferences
- Maps claims to verified fact IDs and flags gaps/disqualifiers
- Separates employer-posted pay from a clearly labeled market estimate
- Recommends `PRIORITY APPLY`, `APPLY`, `STRETCH`, or `SKIP`
- Produces a tailored resume and cover letter using only verified facts
- Runs anti-hallucination validation before showing generated materials
- Never applies to a job or sends anything externally

## Run locally

Requires Python 3.10 or newer. No package installation is needed.

From the project folder, run the Windows launcher. It does not require PowerShell script permissions:

```powershell
.\start-career-copilot.cmd
```

Or launch it directly with Python:

```powershell
cd "C:\Users\1lone\Documents\Codex\2026-08-16\referenced-chatgpt-conversation-this-is-an"
& "C:\Users\1lone\AppData\Local\Programs\Python\Python313\python.exe" -m career_copilot
```

Then open <http://127.0.0.1:8765>. Data is stored in `data/`, which is created on first run.

To use a different port:

```powershell
$env:CAREER_COPILOT_PORT = "9000"
python -m career_copilot
```

## Optional AI drafting

The MVP deliberately works without an external model. The architecture leaves `career_copilot/llm.py` as the integration boundary for adding an approved model provider. The current release keeps all processing local and deterministic so its evidence and safety behavior are easy to test before adding model variability.

## Workflow

1. Paste the master resume and complete career preferences.
2. Review the extracted career-truth facts. Facts are marked verified because they come directly from the saved master resume; edit the resume and rebuild the profile if needed.
3. Paste a real job posting and analyze it.
4. Review the score, evidence, gaps, disqualifiers, and compensation labels.
5. Generate tailored materials. The master resume is never overwritten.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Architecture

- `career_copilot/models.py` — structured domain objects
- `career_copilot/profile.py` — fact extraction and career-truth creation
- `career_copilot/analyzer.py` — explainable deterministic scoring
- `career_copilot/tailor.py` — evidence-bound drafting
- `career_copilot/validator.py` — anti-hallucination checks
- `career_copilot/storage.py` — atomic local persistence
- `career_copilot/server.py` — JSON API and local UI server
- `web/` — dependency-free interface

The next sensible increments are interview-prep packets, a job/application tracker, URL fetching with explicit user review, and an LLM adapter that must return schema-valid JSON with fact citations.
