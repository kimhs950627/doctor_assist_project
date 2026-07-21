"""Shared Research Asset schema for Doctor Assist.

This module is intentionally provider- and UI-agnostic. Web Vlog, standalone
Research, Telegram, and future patient-handout workflows exchange the same
validated objects. It does not run OpenManus, call Gemini, or write files.

Privacy boundary: these schemas describe general medical evidence requests.
Do not place patient-identifying information or raw EMR content in ``topic``,
``notes``, source excerpts, or any other field persisted as a Research Asset.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


UTC = timezone.utc
RESEARCH_ID_PATTERN = r"^R-\d{8}-\d{3}(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?$"
CLAIM_ID_PATTERN = r"^C-\d{3,}$"
SOURCE_ID_PATTERN = r"^S-\d{3,}$"

ShortText = Annotated[str, Field(min_length=1, max_length=500)]
LongText = Annotated[str, Field(min_length=1, max_length=20_000)]


class ResearchType(str, Enum):
    """The evidence question determines the retrieval strategy, not the UI."""

    GUIDELINE = "guideline"
    LITERATURE = "literature"
    POLICY = "policy"
    MEDICAL_CONTENT = "medical_content"


class ResearchAudience(str, Enum):
    """Intended reader of a future derivative, not the OpenManus operator."""

    PHYSICIAN = "physician"
    PATIENT = "patient"
    PUBLIC = "public"


class ResearchEntryPoint(str, Enum):
    """Where the request started; all entries still share one backend flow."""

    RESEARCH_TAB = "research_tab"
    VLOG_PUBLISH = "vlog_publish"
    HANDOUT_SUPPORT = "handout_support"
    TELEGRAM = "telegram"


class ResearchJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    NORMALIZING = "normalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceType(str, Enum):
    PROFESSIONAL_GUIDELINE = "professional_guideline"
    GOVERNMENT = "government"
    REGULATORY = "regulatory"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    RANDOMIZED_TRIAL = "randomized_trial"
    OBSERVATIONAL_STUDY = "observational_study"
    PEER_REVIEWED_ARTICLE = "peer_reviewed_article"
    PUBMED_RECORD = "pubmed_record"
    UNIVERSITY_HOSPITAL = "university_hospital"
    PUBLIC_HEALTH = "public_health"
    SECONDARY_SUMMARY = "secondary_summary"
    OTHER = "other"


class EvidenceLevel(str, Enum):
    GUIDELINE = "guideline"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNSPECIFIED = "unspecified"


class ResearchRequest(BaseModel):
    """Validated, reusable request shared by Vlog and Research workflows."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: ShortText
    research_type: ResearchType
    audience: ResearchAudience
    entry_point: ResearchEntryPoint
    intended_reuse: list[str] = Field(default_factory=list, max_length=8)
    language: list[str] = Field(default_factory=lambda: ["ko", "en"], min_length=1, max_length=3)
    date_from: datetime | None = None
    date_to: datetime | None = None
    preferred_source_types: list[SourceType] = Field(default_factory=list)
    excluded_source_types: list[SourceType] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2_000)

    @field_validator("intended_reuse", "language")
    @classmethod
    def normalize_string_list(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values if value.strip()]
        return list(dict.fromkeys(normalized))

    @field_validator("preferred_source_types", "excluded_source_types")
    @classmethod
    def deduplicate_source_types(cls, values: list[SourceType]) -> list[SourceType]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_research_policy(self) -> "ResearchRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be later than date_to")
        overlap = set(self.preferred_source_types) & set(self.excluded_source_types)
        if overlap:
            names = ", ".join(item.value for item in sorted(overlap, key=lambda item: item.value))
            raise ValueError(f"source types cannot be both preferred and excluded: {names}")
        return self


class ResearchSource(BaseModel):
    """Citation metadata preserved independently from prose drafted later."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    title: ShortText
    url: str = Field(min_length=8, max_length=4_000)
    source_type: SourceType
    publication_or_update_date: datetime | None = None
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    short_excerpt: str | None = Field(default=None, max_length=2_000)
    quality_note: str | None = Field(default=None, max_length=1_000)

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("url must start with http:// or https://")
        return value


class EvidenceClaim(BaseModel):
    """A factual claim that Gemini may use only when linked to stored sources."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim_id: str = Field(pattern=CLAIM_ID_PATTERN)
    statement: LongText
    clinical_context: str | None = Field(default=None, max_length=2_000)
    evidence_level: EvidenceLevel = EvidenceLevel.UNSPECIFIED
    source_ids: list[str] = Field(min_length=1, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, values: list[str]) -> list[str]:
        values = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        invalid = [value for value in values if not re.fullmatch(SOURCE_ID_PATTERN, value)]
        if invalid:
            raise ValueError(f"invalid source IDs: {', '.join(invalid)}")
        if not values:
            raise ValueError("at least one source ID is required")
        return values


class EvidenceBundle(BaseModel):
    """Normalized evidence input for Gemini source-constrained editorial work."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: str = "1.0"
    research_id: str = Field(pattern=RESEARCH_ID_PATTERN)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    claims: list[EvidenceClaim] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list, max_length=20)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=20)
    suggested_outline: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_claim_source_links(self) -> "EvidenceBundle":
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source IDs must be unique within an EvidenceBundle")
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim IDs must be unique within an EvidenceBundle")
        known_sources = set(source_ids)
        missing = {
            source_id
            for claim in self.claims
            for source_id in claim.source_ids
            if source_id not in known_sources
        }
        if missing:
            raise ValueError(f"claims reference missing source IDs: {', '.join(sorted(missing))}")
        return self


class ResearchJob(BaseModel):
    """Durable job metadata. Runtime persistence belongs to research_store.py."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    research_id: str = Field(pattern=RESEARCH_ID_PATTERN)
    request: ResearchRequest
    status: ResearchJobStatus = ResearchJobStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    artifact_path: str | None = Field(default=None, max_length=4_000)
    error_summary: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "ResearchJob":
        terminal = {ResearchJobStatus.COMPLETED, ResearchJobStatus.FAILED, ResearchJobStatus.CANCELLED}
        if self.status in terminal and self.completed_at is None:
            raise ValueError("terminal jobs require completed_at")
        if self.completed_at and self.started_at and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.status == ResearchJobStatus.FAILED and not self.error_summary:
            raise ValueError("failed jobs require error_summary")
        return self


def make_research_id(sequence: int, *, at: datetime | None = None, slug: str | None = None) -> str:
    """Create a stable local ID, e.g. ``R-20260721-001-dyslipidemia-update``.

    The storage layer owns sequence allocation. This function only formats a
    validated identifier so both Vlog and Research use identical IDs.
    """
    if not 1 <= sequence <= 999:
        raise ValueError("sequence must be between 1 and 999")
    stamp = (at or datetime.now(UTC)).strftime("%Y%m%d")
    base = f"R-{stamp}-{sequence:03d}"
    if not slug:
        return base
    normalized = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    if not normalized:
        return base
    return f"{base}-{normalized[:80].rstrip('-')}"


def editorial_payload(bundle: EvidenceBundle) -> dict[str, Any]:
    """Return the exact evidence-only payload intended for Gemini editorial calls.

    Raw OpenManus execution traces are deliberately absent. This helper makes
    the source-constrained boundary explicit for every downstream consumer.
    """
    return bundle.model_dump(mode="json")
