# Doctor Assist Project — Implementation Plan

> Last updated: 2026-08-04
> Status: Design baseline. Implement in small, testable phases.
> Repository: `kimhs950627/doctor_assist_project`
> This document is the practical implementation plan. For security principles and high-level infrastructure, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Project Goal

Doctor Assist is an AI-enabled working system for a family physician. It is controlled from two places:

1. **Web dashboard** — detailed review, editing, printing, job monitoring, and administration.
2. **Telegram bot** — quick requests, notifications, lightweight review actions, and remote control.

The system supports three main areas:

- **Clinical assistance**: SOAP conversion, patient education handouts, differential-diagnosis support, and medication-related questions.
- **Evidence and research**: thorough collection and storage of medical evidence, papers, guidelines, and policy information.
- **Content workflow**: reusable drafts for Instagram, Tistory, and Naver Blog, with physician review before publication.

The long-term goal is not a generic chatbot. It is a maintainable, physician-controlled system that converts reliable medical evidence into reusable clinical handouts and public-facing medical content.

---

## 2. Non-Negotiable Principles

- **Human-in-the-loop**: no patient-facing material or public medical content is automatically finalized without physician review.
- **Privacy first**: do not send patient-identifying information (PHI) to OpenManus, Gemini, MedGemma, Telegram, public URLs, Git, or general research storage.
- **Evidence before prose**: for medical facts, collect and preserve evidence before asking Gemini or MedGemma to write polished text.
- **One business workflow**: web and Telegram are different user interfaces, not separate backends.
- **Simple first**: start with one worker, SQLite, local files, and explicit commands. Do not introduce Redis, Celery, Docker, or microservices until workload requires them.
- **Replaceable providers**: OpenManus, Gemini, MedGemma, PubMed, and future retrieval tools must be behind narrow interfaces so that one provider can be replaced without rewriting the UI.
- **No secrets in Git**: API keys, cookies, tokens, downloaded runtime data, and research artifacts stay outside commits.
- **API-only for MedGemma**: MedGemma is always called via external API (Google Vertex AI or Hugging Face Inference API). Local inference of MedGemma is explicitly out of scope.

---

## 3. Responsibility Split

### 3.1 Control towers

| Component | Main responsibility | Must not do directly |
|---|---|---|
| Web dashboard | Detailed request forms, evidence review, draft editing, print/export, job monitoring | Run long OpenManus work inside an HTTP request |
| Telegram bot | Start jobs, receive notifications, view short summaries, approve or open review links | Store full research artifacts in chat history |
| Shared router/service layer | Validate requests and call shared business services | Contain UI-specific formatting |

### 3.2 AI and research tools

| Tool/service | Responsibility | Not responsible for |
|---|---|---|
| OpenManus | Source discovery, multi-step web research, evidence collection, research outline | Final patient wording or publication-ready prose |
| Research library | Store, index, retrieve, and version research evidence assets | Making new medical claims |
| Gemini API without grounding | Source-constrained editorial writing, customization, summaries, channel-specific drafts | Searching the web or adding facts absent from selected evidence |
| Gemini direct mode | Fast non-research tasks such as SOAP formatting, plain-language rewriting, and daily vlog drafts | High-stakes or current factual medical research |
| **MedGemma API** | **Medical-domain QA, differential diagnosis reasoning, clinical text interpretation, medical terminology normalization** | **Web research, evidence collection, or final publication-ready prose** |
| Physician | Select purpose, review facts and wording, approve print/publish | Delegating final clinical responsibility |

### 3.3 Core rule

```text
Web / Telegram
  -> Research request or draft request
  -> OpenManus (only when thorough evidence is needed)
  -> Saved Research Asset
  -> Gemini without grounding reads selected asset only
  -> Draft / handout / content package
  -> Physician review and approval
  -> Print, export, or publish handoff

Clinical quick-assist path (no research job):
  -> Web / Telegram clinical query
  -> MedGemma API (medical-domain reasoning)
  -> Optional: Gemini for formatting/translation
  -> Physician review
```

---

## 4. User-Facing Tabs

The web dashboard should expose a small number of clear tabs. Avoid duplicating features under slightly different names.

| Tab | Purpose | Typical actions |
|---|---|---|
| **Clinical** | Quick outpatient assistance | SOAP, patient explanation, differential diagnosis, drug question, free Gemini query, **MedGemma clinical QA** |
| **Patient Handouts** | Print saved handouts or create customized handouts | Search template, select research asset, customize language level, review, print/PDF |
| **Vlog & Publishing** | Create Instagram, Tistory, and Naver Blog content | Add topic/images, choose daily or evidence mode, create drafts, review, publish/handoff |
| **Research** | Run and inspect independent OpenManus research | Start research, monitor status, inspect sources/claims, save tags, export or reuse |
| **Library & Review** | Reuse saved assets and approve work | Search research history, drafts, handouts, approvals, version history |
| **Jobs & System** | Operational visibility | Queue status, failed jobs, retries, logs, configuration health |
| **Future: EMR Analytics** | Vendor-agnostic CSV/XLSX analytics | Upload de-identified export, validate mapping, view aggregate statistics |

Telegram is a companion control surface. It should use the same backend services, but show summaries and action links rather than large research documents.

---

## 5. Main Workflows

### 5.1 Daily vlog or non-medical content

Use this when the post is lifestyle, clinic culture, ordinary vlog material, or any content that does not need current medical fact checking.

```text
Topic + images
  -> Gemini direct mode
  -> Instagram / Tistory / Naver-specific drafts
  -> Physician review
  -> Official API publish or manual handoff
```

In **Vlog & Publishing**, this is `Research mode = OFF`.

### 5.2 Evidence-based medical content

Use this for public medical information, guideline updates, insurance/policy explanations, or factual articles where sources matter.

```text
Topic + audience + source policy + images
  -> Research mode = ON
  -> ResearchJob created
  -> OpenManus research worker
  -> Research Asset stored in library
  -> Gemini without grounding writes channel-specific drafts
  -> Physician reviews evidence and wording
  -> Publish or handoff
```

The content screen must not wait synchronously for OpenManus. It creates a job ID and displays progress.

### 5.3 Standalone research

Use this for paper review, literature discovery, guideline or policy checking, and research notes that may be reused later.

```text
Research tab or Telegram /research command
  -> same ResearchJobService
  -> same OpenManus worker
  -> same Research Asset library
  -> Web review + concise Telegram completion notice
```

A standalone research asset can later be used to create a blog draft, a patient handout, or a paper summary.

### 5.4 Patient handout from saved evidence

Example: a previous dyslipidemia guideline research should be reusable when creating a new dyslipidemia patient handout.

```text
Patient Handouts tab
  -> choose saved template or create new request
  -> search/select one or more Research Assets
  -> enter minimum necessary, de-identified customization details
  -> Gemini without grounding reads selected EvidenceBundle only
  -> physician review
  -> print/PDF/export
```

Patient-specific facts must not be sent to OpenManus. Research Assets contain general medical evidence only.

### 5.5 Clinical quick-assist with MedGemma

Use this for outpatient clinical queries that benefit from medical-domain reasoning: differential diagnosis generation, drug-drug interaction check, clinical note interpretation, or terminology clarification. No research job is created and no evidence asset is stored by default.

```text
Clinical tab or Telegram /medqa command
  -> de-identified clinical query
  -> MedGemma API (medgemma-27b-it via Vertex AI or HF Inference API)
  -> Optional: Gemini for Korean/plain-language reformatting
  -> Physician review (mandatory for patient-facing use)
```

**PHI rules for this path:**
- Strip patient name, date of birth, registration number, and institution name before sending.
- Use age group and sex only (e.g., "60대 남성", not exact birth date).
- Never send images with embedded patient metadata.

---

## 6. MedGemma API Integration

### 6.1 Why MedGemma as API, not local

MedGemma (Google DeepMind, 2025) is a medical-domain foundation model fine-tuned on medical text and medical images. It outperforms general-purpose LLMs on standard medical benchmarks (MedQA, MedMCQA, PubMedQA).

**Local inference is out of scope** because:
- The smallest medically capable variant (medgemma-27b-it) requires ~54 GB VRAM in bf16, exceeding the home mini PC spec.
- Quantized local inference degrades medical reasoning reliability.
- Google Vertex AI and Hugging Face Inference API provide on-demand access without hardware investment.

### 6.2 Available access methods

| Method | Model ID | Endpoint style | Notes |
|---|---|---|---|
| **Google Vertex AI (Model Garden)** | `google/medgemma-27b-it` | OpenAI-compatible REST | Recommended for production; requires GCP project + billing |
| **Hugging Face Inference API** | `google/medgemma-27b-it` | HF serverless inference | Good for prototyping; rate-limited on free tier |
| **Google AI Studio (Gemini API)** | Not yet available as of 2026-08 | — | Monitor for future availability |

### 6.3 Provider module design

Add `modules/medgemma_provider.py` following the same replaceable-provider pattern used for Gemini and OpenManus.

```python
# modules/medgemma_provider.py

from enum import Enum
from typing import Optional
import httpx
from modules.research_schemas import ClinicalQuery, ClinicalAnswer

class MedGemmaBackend(str, Enum):
    VERTEX_AI = "vertex_ai"
    HF_INFERENCE = "hf_inference"

class MedGemmaProvider:
    """
    Calls MedGemma API (text-only, medgemma-27b-it).
    Never runs local inference.
    Never sends PHI.
    """

    def __init__(self, backend: MedGemmaBackend, api_key: str, project_id: Optional[str] = None):
        self.backend = backend
        self.api_key = api_key
        self.project_id = project_id  # required for Vertex AI

    async def ask(self, query: ClinicalQuery) -> ClinicalAnswer:
        if self.backend == MedGemmaBackend.VERTEX_AI:
            return await self._ask_vertex(query)
        elif self.backend == MedGemmaBackend.HF_INFERENCE:
            return await self._ask_hf(query)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    async def _ask_vertex(self, query: ClinicalQuery) -> ClinicalAnswer:
        # Vertex AI OpenAI-compatible endpoint
        url = (
            f"https://us-central1-aiplatform.googleapis.com/v1/projects/"
            f"{self.project_id}/locations/us-central1/endpoints/openapi/chat/completions"
        )
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "google/medgemma-27b-it",
            "messages": [
                {"role": "system", "content": MEDGEMMA_SYSTEM_PROMPT},
                {"role": "user", "content": query.text},
            ],
            "max_tokens": 1024,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        return ClinicalAnswer(
            text=data["choices"][0]["message"]["content"],
            model="medgemma-27b-it",
            backend=self.backend,
            query_id=query.query_id,
        )

    async def _ask_hf(self, query: ClinicalQuery) -> ClinicalAnswer:
        url = "https://api-inference.huggingface.co/models/google/medgemma-27b-it/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "google/medgemma-27b-it",
            "messages": [
                {"role": "system", "content": MEDGEMMA_SYSTEM_PROMPT},
                {"role": "user", "content": query.text},
            ],
            "max_tokens": 1024,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        return ClinicalAnswer(
            text=data["choices"][0]["message"]["content"],
            model="medgemma-27b-it",
            backend=self.backend,
            query_id=query.query_id,
        )


MEDGEMMA_SYSTEM_PROMPT = """
You are a medical AI assistant supporting a board-certified family physician.
Rules:
1. Respond with clinical reasoning, not general health advice.
2. Do not fabricate drug names, dosing, or guideline positions.
3. Always note when evidence is uncertain, conflicting, or outside your training data.
4. This output requires physician review before any clinical use.
5. Do not assume or request patient-identifying information.
"""
```

### 6.4 Schema additions

Add the following to `modules/research_schemas.py`:

```python
class ClinicalQuery(BaseModel):
    query_id: str                    # UUID
    text: str                        # de-identified clinical question
    query_type: str                  # differential | drug_check | soap | terminology | free
    created_at: datetime

class ClinicalAnswer(BaseModel):
    query_id: str
    text: str
    model: str                       # e.g. "medgemma-27b-it"
    backend: str                     # "vertex_ai" | "hf_inference"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    requires_physician_review: bool = True
```

### 6.5 .env.example additions

```dotenv
# MedGemma API
MEDGEMMA_BACKEND=vertex_ai          # vertex_ai | hf_inference
MEDGEMMA_API_KEY=your_key_here
MEDGEMMA_GCP_PROJECT_ID=your_gcp_project_id   # required for vertex_ai only
```

### 6.6 Use cases within Doctor Assist

| Clinical tab action | MedGemma role | Gemini role |
|---|---|---|
| Differential diagnosis | Generate ranked differentials with reasoning | Reformat into Korean patient-friendly list (optional) |
| Drug interaction check | Identify interactions and mechanism | — |
| SOAP note interpretation | Extract A/P suggestions from free-text note | Final clean SOAP formatting |
| Medical terminology | Translate/explain clinical term | Korean translation |
| Patient handout QA | Answer "is this claim medically accurate?" before publish | — |

### 6.7 Limitations and constraints

- **Text-only initially**: multimodal MedGemma (image input) requires separate implementation and stricter PHI controls for DICOM/ultrasound metadata.
- **No memory across sessions**: each API call is stateless. Clinical context must be included explicitly in the prompt.
- **Not a diagnostic device**: MedGemma output is a physician decision-support tool, not a regulatory-approved diagnostic system.
- **Rate limits**: Vertex AI charges per token; HF free tier limits concurrent requests. Monitor usage via GCP Console or HF dashboard.

---

## 7. Research Asset Design

### 7.1 Why an asset is needed

OpenManus output must not become an unsearchable chat transcript. Every completed research run becomes a reusable **Research Asset** with:

- Original request and research purpose
- OpenManus execution metadata and operational logs
- Normalized medical claims and sources
- Suggested outline and uncertainty notes
- Tags and searchable metadata
- Links to drafts and handouts created from the asset

The normalized evidence artifact is the default source for Gemini. Raw agent output is retained for debugging and provenance only.

### 7.2 Storage layout

```text
data/                              # Git ignored; protected local runtime data
├── doctor_assist.db               # SQLite job/index database
├── research/
│   └── R-YYYYMMDD-NNN_slug/
│       ├── manifest.json          # searchable metadata and lifecycle
│       ├── request.json           # validated input
│       ├── openmanus_raw.json     # raw final output / tool metadata when available
│       ├── evidence_bundle.json   # normalized input for Gemini
│       ├── sources.json           # source metadata list
│       ├── summary.md             # human-readable research summary
│       ├── outline.md             # suggested outline
│       ├── run.log                # sanitized operational stdout/stderr
│       └── artifacts/             # allowed downloaded PDFs/HTML snapshots
├── drafts/
│   └── D-YYYYMMDD-NNN_type.json
├── handouts/
│   ├── templates/
│   └── approved/
└── clinical_qa/                   # MedGemma query/answer log (de-identified only)
    └── Q-YYYYMMDD-NNN.json
```

`data/`, `*.log`, downloaded PDFs, browser profiles, tokens, and session files must be covered by `.gitignore`.

### 7.3 Research Asset lifecycle

```text
queued -> running -> normalizing -> completed
                    -> failed
queued/running -> cancelled
```

A `failed` asset still keeps a sanitized log and error metadata. It must not be silently deleted: this makes debugging and retry decisions possible.

### 7.4 Required JSON contracts

Use Pydantic models (or equivalent dataclasses with validation). Do not pass free-form dictionaries between layers.

```python
ResearchRequest
- topic
- research_type: guideline | literature | policy | medical_content
- audience: physician | patient | public
- entry_point: research_tab | vlog_publish | handout_support | telegram
- date_range
- preferred_source_types
- excluded_source_types
- language
- intended_reuse

ResearchJob
- research_id
- request
- status
- created_at / started_at / completed_at
- artifact_path
- error_summary

EvidenceBundle
- research_id
- retrieved_at
- claims[]
- sources[]
- conflicts[]
- unresolved_questions[]
- suggested_outline[]

EvidenceClaim
- claim_id
- statement
- clinical_context
- evidence_level
- source_ids[]
- limitations[]

ResearchSource
- source_id
- title
- url
- source_type
- publication_or_update_date
- accessed_at
- short_excerpt
- quality_note
```

### 7.5 Minimum evidence quality policy

For medical content, request and label sources in this order where possible:

1. Professional society guidelines, government agencies, regulatory bodies
2. Systematic reviews, meta-analyses, pivotal trials, peer-reviewed papers
3. PubMed/Europe PMC metadata and abstracts
4. Hospital, university, and public health institution pages
5. Secondary summaries only as discovery aids, not sole evidence for clinical claims

The system must preserve disagreements, uncertainty, missing evidence, and outdated-source warnings. It must not force a false single conclusion.

---

## 8. Gemini Editorial Contract

When a Research Asset is selected, Gemini runs **without web grounding** and follows this contract:

```text
Input:
- Output purpose, target audience, language, and requested format
- Selected EvidenceBundle JSON
- Optional physician outline and formatting preferences

Rules:
1. Use only factual medical claims present in the EvidenceBundle.
2. Do not add prevalence, effect sizes, dosing, recommendations, guideline positions,
   or references that are not present in the EvidenceBundle.
3. Preserve uncertainty and limitations from the source material.
4. If evidence is missing, write an explicit evidence-needed marker instead of guessing.
5. Return claim-to-paragraph mapping for review.
6. Do not include PHI.
```

The response should be structured:

```json
{
  "draft_markdown": "...",
  "claim_mapping": [
    {"paragraph_index": 1, "claim_ids": ["C-001", "C-004"]}
  ],
  "unsupported_sentences": [],
  "warnings": []
}
```

This mapping allows the web UI to show "view evidence" for each factual paragraph.

---

## 9. OpenManus Integration Boundary

OpenManus must remain a separate runtime from Doctor Assist.

```text
~/services/
├── doctor_assist_project/
└── OpenManus/
    ├── .venv/
    └── config/
```

### Initial integration method

```text
Doctor Assist ResearchWorker
  -> starts OpenManus with subprocess
  -> applies timeout and captures sanitized stdout/stderr
  -> receives final output
  -> normalizes result into EvidenceBundle
  -> writes artifact files and updates SQLite state
```

Do not import OpenManus internals into the web server. A subprocess boundary prevents dependency conflicts and allows independent updates.

### Provider interface

Keep OpenManus behind a small interface so it can be replaced or complemented later.

```python
class ResearchProvider(Protocol):
    async def research(self, request: ResearchRequest) -> EvidenceBundle:
        ...

class OpenManusResearchProvider:
    ...

class PubMedResearchProvider:
    ...

class GeminiGroundedResearchProvider:
    ...
```

Future hybrid research may combine structured PubMed retrieval with OpenManus web discovery. The UI and Research Asset schema should not need to change when this happens.

---

## 10. Job Queue and Runtime Rules

### 10.1 MVP implementation

Use durable state first, not a complex distributed queue.

| Need | Initial implementation |
|---|---|
| Source of truth | SQLite |
| Artifact store | Protected local filesystem |
| Worker | One long-running Python worker process |
| Concurrency | 1 OpenManus job at a time |
| Web progress | Poll job-status API initially |
| Telegram | Completion/failure notification and action links |
| Timeout | Configurable, initially 10–20 minutes |
| Retry | Manual retry first; bounded automatic retry later |
| Restart recovery | Mark stale running jobs and offer retry |

Do not rely on only `asyncio.Queue`: queued items are lost after a process restart. SQLite is the durable source of truth; the worker polls or claims queued jobs from SQLite.

### 10.2 Why not direct execution

Never run OpenManus inside a FastAPI request handler or Telegram update handler. It can block the user interface, make timeout handling unclear, and lose work after restarts.

### 10.3 Hardware deployment

Start with the Galaxy Note20 only for low-volume proof-of-concept work:

- FastAPI web control
- Telegram bot
- SQLite and artifact index
- Gemini requests
- MedGemma API requests (stateless HTTP, low resource)
- Single OpenManus worker with strict resource limits

If browser automation, heat, memory pressure, or research volume makes it unreliable, keep the Note20 as the control plane and move only the OpenManus worker to a home PC, mini PC, or Linux VM. The web and Telegram workflows should remain unchanged.

---

## 11. Telegram Commands

Start with explicit commands. Natural-language flags can be added after the command workflow is stable.

| Command | Action |
|---|---|
| `/research <topic>` | Create thorough research job |
| `/research_status <R-ID>` | Show job status |
| `/research_show <R-ID>` | Return concise summary and web review link |
| `/research_search <keyword>` | Search saved Research Assets |
| `/draft_from_research <R-ID>` | Create a Gemini draft from a selected asset |
| `/handout_from_research <R-ID>` | Start handout creation using selected evidence |
| `/post <topic>` | Daily/non-research content draft |
| `/post_research <topic>` | Evidence-based content request |
| `/medqa <question>` | **MedGemma clinical quick-assist (de-identified only)** |
| `/status` | System health and queue summary |

After completion, Telegram should send a short message with buttons/links, not a full research transcript.

---

## 12. Repository Layout Target

Keep new modules focused and avoid overlapping responsibilities.

```text
doctor_assist_project/
├── control_tower/
│   ├── router.py                    # Shared UI-facing business actions
│   ├── services/
│   │   ├── research_jobs.py          # Job lifecycle and orchestration
│   │   ├── research_library.py       # Search/reuse/index operations
│   │   ├── evidence_normalizer.py    # Raw provider output -> EvidenceBundle
│   │   ├── editorial_service.py      # Gemini source-constrained drafting
│   │   └── clinical_qa_service.py    # MedGemma clinical query routing
│   ├── workers/
│   │   └── openmanus_worker.py       # Durable worker / subprocess caller
│   ├── web_dashboard/
│   │   └── app.py                    # Web UI/API only
│   └── telegram_bot/
│       └── bot_main.py               # Commands and notifications only
├── modules/
│   ├── research_schemas.py           # Shared validated models (incl. ClinicalQuery/Answer)
│   ├── research_store.py             # SQLite + file artifact storage
│   ├── openmanus_provider.py         # OpenManus adapter only
│   ├── gemini_module.py              # Existing Gemini wrapper
│   ├── medgemma_provider.py          # MedGemma API adapter (Vertex AI / HF)
│   ├── blog_helpers.py               # Existing content utilities
│   └── blog_poster.py                # Existing publishing adapters
├── docs/
│   ├── prompts/
│   ├── research/
│   │   ├── evidence_bundle_schema.md
│   │   ├── source_quality_policy.md
│   │   └── runbook.md
│   └── feature_specs/
├── tests/
│   ├── fixtures/                     # Synthetic research JSON only
│   └── ...
├── data/                             # Ignored runtime data
├── ARCHITECTURE.md
├── doctor_assist_bot_plan.md         # This implementation plan
└── .env.example
```

---

## 13. Security and Data Boundaries

| Data type | Allowed location | Notes |
|---|---|---|
| General medical research | `data/research/` | Long-term library; review freshness periodically |
| Generic approved handouts | `data/handouts/approved/` | Version and physician approval required |
| Draft content | `data/drafts/` | Link to source Research Asset when applicable |
| **Clinical QA logs (MedGemma)** | **`data/clinical_qa/`** | **De-identified only; no PHI ever** |
| Patient-specific handouts | Protected local store | Minimum retention, separate access logging |
| EMR exports | Separate encrypted storage | Never mix with general research library |
| API keys/tokens/cookies | `.env` / protected secret store | Never commit or log |

Rules:

- Do not put PHI in `ResearchRequest`, OpenManus prompts, MedGemma prompts, research JSON, Telegram messages, or logs.
- Sanitize logs before persistence; do not retain secrets or raw request headers.
- Record action metadata (who, when, job ID, approval status) but not sensitive prompt content unnecessarily.
- Keep Naver publishing as manual final handoff unless an official supported publishing API becomes available and is policy-compliant.

---

## 14. Phased Implementation Roadmap

### Phase 0 — Foundation and contracts

**Goal:** make the data model and safety boundary explicit before invoking OpenManus.

- Add `data/` and runtime artifact rules to `.gitignore`.
- Define Pydantic schemas for `ResearchRequest`, `ResearchJob`, `EvidenceBundle`, claims, and sources.
- **Add `ClinicalQuery` and `ClinicalAnswer` schemas.**
- Create SQLite schema and file storage helper.
- Write source-quality policy and Gemini editorial prompt contract.
- Add synthetic fixtures and unit tests for JSON validation.

**Done when:** a synthetic EvidenceBundle can be stored, searched, loaded, and used to produce a source-constrained Gemini draft without OpenManus installed.

### Phase 1 — Research Library MVP

**Goal:** one robust research job produces one reusable asset folder.

- Implement `research_store.py`, `research_jobs.py`, and `openmanus_provider.py`.
- Implement a single worker that claims SQLite jobs and invokes OpenManus by subprocess.
- Save manifest, request, raw result, normalized evidence, sources, summary, and logs.
- Add timeout, cancellation, failure status, and manual retry.

**Done when:** a test request creates a stable `R-ID` and a valid EvidenceBundle under `data/research/`.

### Phase 1.5 — MedGemma API integration *(new)*

**Goal:** add medical-domain clinical QA capability via API.

- Implement `modules/medgemma_provider.py` with Vertex AI backend.
- Add `ClinicalQuery` / `ClinicalAnswer` schemas to `research_schemas.py`.
- Add `control_tower/services/clinical_qa_service.py`.
- Add `MEDGEMMA_*` keys to `.env.example`.
- Add Clinical tab action "Ask MedGemma" in web dashboard.
- Add `/medqa` Telegram command.
- Log all queries and answers to `data/clinical_qa/` (de-identified only).
- Write unit tests with mocked HTTP responses.

**Done when:** a de-identified clinical question sent via Telegram `/medqa` returns a MedGemma-generated clinical reasoning text and is logged locally.

### Phase 2 — Telegram research control

**Goal:** start and monitor research from anywhere.

- Add `/research`, `/research_status`, `/research_show`, and `/research_search`.
- Send completion/failure notifications with a web review link.
- Keep full evidence review in the web UI.

**Done when:** Telegram starts a job, job completion persists after restart, and the user can open or reuse the saved asset.

### Phase 3 — Web Research and Library tabs

**Goal:** make evidence assets discoverable and inspectable.

- Add research request form and job monitor.
- Add source/claim viewer, tags, search filters, and stale-evidence warnings.
- Add `Use for blog` and `Use for handout` actions.

**Done when:** a prior dyslipidemia research asset can be found and selected from the dashboard.

### Phase 4 — Vlog & Publishing integration

**Goal:** support both fast daily content and evidence-based medical content in one tab.

- Add `Research mode` checkbox to the content request form.
- Keep `OFF` path as existing Gemini-only daily draft.
- Make `ON` path wait for selected/completed Research Asset before editorial drafting.
- Generate platform-specific drafts with evidence claim mapping.
- Require physician approval before any publish/handoff action.

**Done when:** one Research Asset can generate Instagram, Tistory, and Naver-ready drafts while preserving the evidence link.

### Phase 5 — Patient Handouts integration

**Goal:** turn approved evidence into printable, understandable patient materials.

- Add template library, custom handout form, version history, and print/PDF export.
- Allow selecting saved Research Assets.
- Provide literacy-level and language controls.
- Require a review screen that exposes evidence links and freshness warnings.

**Done when:** an existing dyslipidemia research asset creates a customized patient handout with traceable claims.

### Phase 6 — Reliability and scale only when needed

**Goal:** improve operations without premature complexity.

- Move OpenManus worker to a home PC/VM if Note20 is unreliable.
- Add a dedicated queue only if multiple concurrent or scheduled jobs require it.
- Add scheduled research refresh and evidence freshness reminders.
- Add PubMed/official-source adapters for deterministic medical metadata retrieval.
- **Evaluate MedGemma multimodal (image) API for ultrasound report assistance.**
- Add monitoring, backup, restore test, and retention tasks.

**Done when:** workers can restart safely, artifacts are backed up, and stale evidence is flagged before reuse.

---

## 15. Definition of Done Checklist

A feature is not complete merely because it runs once.

- [ ] Input validation and PHI boundary are documented.
- [ ] Web and Telegram use the same shared service method.
- [ ] Job has durable status in SQLite.
- [ ] Runtime files are Git ignored.
- [ ] Failure, timeout, cancellation, and manual retry are handled.
- [ ] Result has an artifact ID and searchable metadata.
- [ ] Medical factual output has a source/evidence link or explicit uncertainty.
- [ ] Gemini editorial mode does not silently ground/search when an asset is selected.
- [ ] **MedGemma queries are de-identified before sending to external API.**
- [ ] Physician review is required before print/publish where appropriate.
- [ ] Synthetic tests cover schema validation and failure paths.
- [ ] README/runbook explains how a new developer starts, tests, and troubleshoot it.

---

## 16. First Development Task

Do **not** start by editing the Vlog UI. Start with the reusable core:

1. Create `modules/research_schemas.py` (include `ClinicalQuery` and `ClinicalAnswer`).
2. Create `modules/research_store.py` with SQLite and artifact-folder support.
3. Add `.gitignore` coverage for `data/` and runtime artifacts.
4. Add a synthetic `EvidenceBundle` fixture and test search/load behavior.
5. Add a minimal `ResearchJobService` that can create and list jobs before OpenManus is connected.
6. **Add `modules/medgemma_provider.py` stub with HF Inference backend for early testing.**

Once this foundation is stable, OpenManus, Telegram commands, the Research tab, MedGemma clinical QA, Vlog research checkbox, and patient-handout reuse become small integrations rather than separate systems.
