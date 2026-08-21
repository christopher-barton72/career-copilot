# Career Copilot

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
- Never applies to a job or contacts employers
- Optionally adds an AI senior-headhunter assessment, evidence selection, and independent draft review

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

## Public-release privacy and security

Career Copilot binds only to `127.0.0.1` and does not fetch job URLs or contact employers. By default, all analysis remains local in the ignored `data/` directory. Ollama AI processing also stays on the computer through a loopback-only HTTP connection. If the optional OpenAI provider is selected, the master resume, verified facts, job posting, and generated drafts are sent to OpenAI with response storage disabled. Never commit real resumes, generated PDFs, secrets, or analysis exports. The server rejects cross-origin JSON writes, limits request size, disables caching, and sets restrictive browser security headers. This is a local single-user tool; do not expose its port to a network.

The saved master resume is immutable during analysis, tailoring, and export. Tailoring selects exact source facts, validates both evidence IDs and exact claim text, and reports SHA-256 before/after values. A mismatched claim fails closed. Generated materials are drafts and require human review.

## PDF export

`POST /api/export` with JSON `{ "kind": "resume" }` or `{ "kind": "cover_letter" }` returns a dependency-free, paginated PDF. Resume and cover-letter exports share a professional navy identity, centered contact header, restrained rules and shaded callouts, compact section hierarchy, protected bottom margins, and page numbering. Internal evidence IDs and Career Copilot validation labels are never printed in applicant-facing PDFs.

## Optional AI headhunter and drafting review

AI is opt-in. The deterministic analyzer remains authoritative for hard eligibility and preference blockers. When enabled, AI adds a separate senior-headhunter confidence score, selects the strongest verified facts for the resume and cover letter, and performs a second factual/professional review before drafts are released. Unknown evidence IDs and any draft rejected for unsupported claims fail closed. The master resume is never changed.

### Local AI with Ollama (recommended)

Install [Ollama for Windows](https://ollama.com/download/windows), then download a model:

```powershell
ollama pull llama3.2
```

Start Career Copilot from the same PowerShell window:

```powershell
$env:CAREER_COPILOT_AI = "true"
$env:CAREER_COPILOT_AI_PROVIDER = "ollama"
$env:CAREER_COPILOT_AI_MODEL = "llama3.2"
& "C:\Users\1lone\AppData\Local\Programs\Python\Python313\python.exe" -m career_copilot
```

Career Copilot calls Ollama only at the loopback address `http://127.0.0.1:11434`; remote Ollama URLs are rejected so resume data cannot be redirected to another host. No OpenAI key or per-request API charge is required. Local model quality and speed depend on the selected model and computer hardware.

### OpenAI API (optional cloud provider)

Set the variables only in the PowerShell session used to launch the app:

```powershell
$env:CAREER_COPILOT_AI = "true"
$env:CAREER_COPILOT_AI_PROVIDER = "openai"
$env:OPENAI_API_KEY = "your-api-key"
$env:CAREER_COPILOT_AI_MODEL = "gpt-5.2"  # optional
& "C:\Users\1lone\AppData\Local\Programs\Python\Python313\python.exe" -m career_copilot
```

Do not put the API key in the repository, a profile, a job posting, or a screenshot. OpenAI API use may incur charges. Remove the variables or set `CAREER_COPILOT_AI=false` to return to deterministic-only operation.

## Workflow

1. Paste the master resume and complete career preferences.
2. Review the extracted career-truth facts. Facts are marked verified because they come directly from the saved master resume; edit the resume and rebuild the profile if needed.
3. Paste a real job posting and analyze it.
4. Review the score, evidence, gaps, disqualifiers, and compensation labels.
5. Generate tailored materials. The master resume is never overwritten.

## Recommendation logic

The analyzer separates evidence overlap from explicit eligibility and preference compatibility. It checks required, preferred, and generally mentioned skills independently; evaluates explicit degree and minimum-experience language; compares job location and work mode with saved preferences; checks employment type, travel, and compensation; and shows each assessment in the recommendation view.

Explicit incompatibilities fail conservatively. A location mismatch for an on-site or hybrid role, an unacceptable employment type or work mode, compensation below the saved minimum, excessive travel, or a saved dealbreaker produces `SKIP`. One unsupported must-have caps the result at `STRETCH`; two unsupported must-haves or an unsupported required degree produce `SKIP`. Preferred qualifications are reported as gaps but are not treated as required.

This remains deterministic text analysis, not a semantic hiring decision. Ambiguous locations, equivalencies such as "degree or equivalent experience," transferable skills outside the known vocabulary, and nuanced requirement wording require human review. The tool never treats an unknown as verified evidence.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Architecture

- `career_copilot/models.py` — structured domain objects
- `career_copilot/profile.py` — fact extraction and career-truth creation
- `career_copilot/analyzer.py` — explainable deterministic scoring
- `career_copilot/ai.py` — opt-in Responses API boundary and strict structured outputs
- `career_copilot/tailor.py` — evidence-bound drafting
- `career_copilot/validator.py` — anti-hallucination checks
- `career_copilot/storage.py` — atomic local persistence
- `career_copilot/server.py` — JSON API and local UI server
- `web/` — dependency-free interface

The next sensible increments are interview-prep packets, a job/application tracker, URL fetching with explicit user review, and an LLM adapter that must return schema-valid JSON with fact citations.
