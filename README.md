# Doctor Assist Project

> AI-assisted clinical, evidence, and content workflow for a family physician.
> **Two control towers:** Web dashboard for detailed review, Telegram bot for remote request and notification.
> Current implementation plan: [`doctor_assist_bot_plan.md`](doctor_assist_bot_plan.md)
> Architecture and security decisions: [`ARCHITECTURE.md`](ARCHITECTURE.md)

---

## What This Project Builds

Doctor Assist is a physician-controlled working system, not a general chatbot. It connects routine outpatient assistance, reusable medical evidence research, patient handouts, and public medical content workflow.

The system has three practical domains:

- **Clinical assistance** — SOAP conversion, patient explanation drafts, differential-diagnosis support, and medication-related questions.
- **Research library** — thorough collection, storage, search, and reuse of medical papers, guidelines, policy, and factual evidence.
- **Vlog & publishing** — drafts for Instagram, Tistory, and Naver Blog, reviewed by a physician before release.

All patient-facing and public medical outputs remain subject to physician review. Patient-identifying information must never be sent to general research tools, Telegram, Git, or unprotected logs.

---

## Core Workflow

For ordinary daily content, Gemini can directly create a draft. For medical factual content, the system separates evidence gathering from writing.

```text
Web Dashboard / Telegram Bot
            |
            +-- Daily content or lightweight task
            |      -> Gemini direct mode
            |
            +-- Medical research / evidence-based content
                   -> OpenManus research worker
                   -> Saved Research Asset (evidence, sources, metadata)
                   -> Gemini without grounding, constrained to selected evidence
                   -> Physician review
                   -> Print, export, publish, or manual handoff
```

| Component | Primary role |
|---|---|
| Web dashboard | Detailed forms, source review, draft editing, printing/export, job monitoring |
| Telegram bot | Fast requests, job status, notifications, links to review pages |
| OpenManus | Source discovery and thorough evidence collection |
| Research Library | Persistent JSON artifacts, source metadata, search index, reuse links |
| Gemini API | Editorial drafting, customization, summarization, channel-specific wording |
| Physician | Medical judgment, review, final approval |

Gemini must not introduce new medical facts when a saved Research Asset is selected. It writes only from the normalized evidence bundle and explicitly flags missing evidence or uncertainty.

---

## Web Dashboard Tabs

| Tab | Purpose | Current/planned actions |
|---|---|---|
| **Clinical** | Quick outpatient support | SOAP, patient explanation, differential diagnosis, drug question, free Gemini query |
| **Patient Handouts** | Create or print patient materials | Saved templates, customization, research-asset reuse, print/PDF |
| **Vlog & Publishing** | Produce public content | Instagram/Tistory/Naver drafts, images, review, publish/handoff |
| **Research** | Run standalone thorough research | Start OpenManus jobs, inspect evidence, sources, and uncertainty |
| **Library & Review** | Reuse prior work | Search research assets, drafts, handouts, approvals, versions |
| **Jobs & System** | Operational status | Queue, failures, retry, logs, health check |
| **Future: EMR Analytics** | Vendor-neutral operations analytics | De-identified CSV/XLSX upload and aggregate reporting |

### Vlog research mode

In **Vlog & Publishing**, the user selects the appropriate path:

| Mode | Use case | Pipeline |
|---|---|---|
| `Research mode OFF` | Daily vlog, lifestyle, clinic culture, non-medical posts | Topic/images -> Gemini -> draft -> review |
| `Research mode ON` | Medical facts, guideline updates, insurance/policy explanation | Topic -> OpenManus -> Research Asset -> Gemini without grounding -> review |

OpenManus work is asynchronous. The UI creates a job ID and shows progress rather than blocking while research runs.

---

## Research Assets

Every OpenManus research run is stored as a reusable **Research Asset**, not an unsearchable chat transcript. This allows one dyslipidemia research run, for example, to support a blog post today and a patient handout later.

```text
data/                              # Runtime data; never commit to Git
├── doctor_assist.db               # SQLite job and search index
├── research/
│   └── R-YYYYMMDD-NNN_slug/
│       ├── manifest.json          # ID, topic, tags, status, timestamps
│       ├── request.json           # Validated research request
│       ├── openmanus_raw.json     # Raw final provider output for provenance
│       ├── evidence_bundle.json   # Normalized Gemini input
│       ├── sources.json           # URLs, source type, dates, excerpts
│       ├── summary.md             # Human-readable summary
│       ├── outline.md             # Suggested outline
│       ├── run.log                # Sanitized execution log
│       └── artifacts/             # Allowed downloaded PDFs/HTML snapshots
├── drafts/
└── handouts/
```

### Research Asset rules

- `evidence_bundle.json` is the standard input to Gemini for source-constrained drafting.
- `openmanus_raw.json` is for debugging and provenance, not default editorial input.
- Save source URL, source type, publication/update date, retrieval date, claim linkage, limitations, and conflicts.
- Store general medical evidence only; do not store PHI or raw EMR data in the research library.
- `data/`, logs, PDFs, browser sessions, and secrets must be Git ignored.

---

## Repository Layout

The repository currently contains the initial control-tower modules. The target layout below shows the planned, maintainable structure.

```text
doctor_assist_project/
├── control_tower/
│   ├── router.py                    # Shared actions used by web and Telegram
│   ├── services/
│   │   ├── research_jobs.py          # Job lifecycle and orchestration
│   │   ├── research_library.py       # Search and reuse operations
│   │   ├── evidence_normalizer.py    # Provider result -> EvidenceBundle
│   │   └── editorial_service.py      # Gemini source-constrained drafting
│   ├── workers/
│   │   └── openmanus_worker.py       # Worker and subprocess integration
│   ├── web_dashboard/
│   │   └── app.py                    # Web UI/API
│   └── telegram_bot/
│       └── bot_main.py               # Telegram commands and notifications
├── modules/
│   ├── gemini_module.py              # Gemini API wrapper
│   ├── telegram_module.py            # Telegram wrapper
│   ├── instagram_module.py           # Instagram/Threads wrapper
│   ├── blog_helpers.py               # Content/image helper functions
│   ├── blog_poster.py                # Posting adapters
│   ├── research_schemas.py           # Planned validated research models
│   ├── research_store.py             # Planned SQLite/file storage
│   └── openmanus_provider.py         # Planned OpenManus adapter
├── docs/                             # Prompts, feature specs, operating guides
├── data/                             # Runtime artifacts; ignored by Git
├── ARCHITECTURE.md                   # Architecture and security decisions
├── doctor_assist_bot_plan.md         # Detailed implementation roadmap
├── .env.example                      # Required environment variable names
└── requirements.txt
```

Web and Telegram must call the same router/service methods. Do not copy research, drafting, or publishing business logic into both UI layers.

---

## Quick Start

### Prerequisites

- Python 3.11+ recommended
- Gemini API key for Gemini features
- Telegram bot token only when the Telegram control tower is enabled
- Platform API credentials only for the publishing channels being tested
- OpenManus installed separately only when implementing Research Worker phases

### 1. Clone and enter the project

```bash
git clone https://github.com/kimhs950627/doctor_assist_project.git
cd doctor_assist_project
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows PowerShell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env. Never commit this file.
```

At minimum, set `GEMINI_API_KEY` for Gemini-dependent functions. Keep `DRY_RUN=true` while testing publishing integrations.

### 4. Run the web control tower

```bash
uvicorn control_tower.web_dashboard.app:app --host 0.0.0.0 --port 7860 --reload
```

Then open `http://localhost:7860` locally. Do not expose a dashboard to the internet before configuring an authenticated access layer.

### 5. Run the Telegram control tower

```bash
python control_tower/telegram_bot/bot_main.py
```

For a home server, run the web server and bot in separate supervised processes. The future research worker must also run as a separate process.

---

## Current Commands

The following commands reflect the current bot implementation; Research commands are planned and should be added only after the durable Research Asset foundation is complete.

| Command | Purpose | Status |
|---|---|---|
| `/start` | Start/help message | Current |
| `/soap <note>` | Convert a short note to SOAP format | Current |
| `/ddx <symptoms>` | Differential-diagnosis support | Current |
| `/edu <diagnosis>` | Patient education draft | Current |
| `/drug <current meds> \| <new med>` | Medication interaction question | Current |
| `/post <topic>` | Daily/non-research content draft | Current/planned refinement |
| `/status` | Basic module health | Current |
| `/research <topic>` | Create thorough research job | Planned |
| `/research_status <R-ID>` | Show research job status | Planned |
| `/research_show <R-ID>` | Show summary and review link | Planned |
| `/research_search <keyword>` | Search saved research assets | Planned |
| `/draft_from_research <R-ID>` | Create Gemini draft from selected evidence | Planned |
| `/handout_from_research <R-ID>` | Create handout using selected evidence | Planned |

---

## Environment Variables

Copy `.env.example` to `.env` and populate only the integrations you use.

| Variable | Purpose | Required when |
|---|---|---|
| `GEMINI_API_KEY` | Gemini API access | Gemini functions are enabled |
| `GEMINI_MODEL` | Default Gemini model | Optional configuration |
| `GROUNDING_MODEL` | Existing quick-grounding model setting | Quick research path is enabled |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | Telegram control tower is enabled |
| `BOT_OWNER_CHAT_ID` | Authorized Telegram chat ID | Telegram control tower is enabled |
| `TISTORY_ACCESS_TOKEN` | Tistory API token | Tistory publishing is enabled |
| `TISTORY_BLOG_NAME` | Tistory blog identifier | Tistory publishing is enabled |
| `INSTAGRAM_ACCESS_TOKEN` | Meta long-lived token | Instagram publishing is enabled |
| `INSTAGRAM_USER_ID` | Instagram business account ID | Instagram publishing is enabled |
| `NAVER_BLOG_ID` | Naver blog identifier | Naver handoff/session workflow is enabled |
| `NAVER_SESSION_PATH` | Local protected browser session path | Browser-assisted Naver workflow is enabled |
| `THREADS_ACCESS_TOKEN` | Threads token | Threads publishing is enabled |
| `THREADS_USER_ID` | Threads account ID | Threads publishing is enabled |
| `DRY_RUN` | Prevent real publishing when `true` | Recommended during development |
| `LOG_LEVEL` | Application log level | Optional |

Never show, print, commit, or place actual credentials in source code, documentation, issue trackers, or research artifacts.

---

## OpenManus Setup Boundary

OpenManus is a separate runtime, not a Python import inside the web server. This prevents dependency conflicts and lets it be updated independently.

```text
~/services/
├── doctor_assist_project/
└── OpenManus/
    ├── .venv/
    └── config/
```

The planned worker will call OpenManus through a subprocess with timeout, sanitized logs, and structured output normalization. It will not run inside a FastAPI request handler or Telegram update handler.

Initial runtime plan:

- SQLite is the durable job/status source of truth.
- Local protected files store research JSON and permitted source artifacts.
- One OpenManus job runs at a time initially.
- Telegram sends completion/failure notices; web UI provides detailed review.
- If Galaxy Note20 becomes unreliable for browser-heavy research, move only the worker to a home PC or Linux VM while keeping the same web/Telegram controls.

---

## Development Order

Do not begin by connecting an OpenManus button directly to the Vlog UI. Build the reusable evidence layer first.

1. Add `ResearchRequest`, `ResearchJob`, and `EvidenceBundle` schemas.
2. Add SQLite + artifact-folder storage and a synthetic test fixture.
3. Create jobs, list jobs, load assets, and search assets without OpenManus.
4. Add the isolated OpenManus worker and normalize output into `EvidenceBundle`.
5. Add Telegram research commands and web Research/Library tabs.
6. Add Vlog `Research mode` and evidence-based drafting.
7. Add patient-handout reuse, print/PDF, versioning, and evidence review.
8. Add scaling, scheduled refresh, and PubMed/official-source adapters only when needed.

The complete phase definitions, data contracts, safety rules, and definition-of-done checklist are in [`doctor_assist_bot_plan.md`](doctor_assist_bot_plan.md).

---

## Safety Notes

- This project assists physician work; it does not replace clinical judgment.
- Review all differential diagnoses, medication content, patient handouts, and public medical posts before use.
- Do not upload or log patient-identifying information in research workflows.
- For evidence-based output, use saved Research Assets and retain source/uncertainty links.
- Keep automated public posting in dry-run/review mode until each platform integration and its terms are validated.
- Use manual final publishing for Naver Blog unless a supported, policy-compliant official publishing API is available.

---

## Related Project

The original shared integration approach was adapted from [sns-doctor-branding](https://github.com/kimhs950627/sns-doctor-branding). In this repository, integrations are organized for direct use by the two Doctor Assist control towers.
