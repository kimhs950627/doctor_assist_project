"""Tests for the provider/UI-agnostic Research Asset contracts."""
from datetime import datetime, timezone
import unittest

from pydantic import ValidationError

from modules.research_schemas import (
    EvidenceBundle,
    EvidenceClaim,
    ResearchAudience,
    ResearchEntryPoint,
    ResearchRequest,
    ResearchSource,
    ResearchType,
    SourceType,
    editorial_payload,
    make_research_id,
)


class ResearchSchemasTest(unittest.TestCase):
    def test_vlog_and_research_share_one_request_contract(self) -> None:
        vlog_request = ResearchRequest(
            topic="Dyslipidemia guideline update",
            research_type=ResearchType.MEDICAL_CONTENT,
            audience=ResearchAudience.PUBLIC,
            entry_point=ResearchEntryPoint.VLOG_PUBLISH,
            intended_reuse=["blog", "handout", "BLOG"],
        )
        research_request = vlog_request.model_copy(update={"entry_point": ResearchEntryPoint.RESEARCH_TAB})
        self.assertEqual(vlog_request.intended_reuse, ["blog", "handout"])
        self.assertEqual(research_request.topic, vlog_request.topic)
        self.assertEqual(research_request.entry_point, ResearchEntryPoint.RESEARCH_TAB)

    def test_bundle_rejects_claim_with_unknown_source(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle(
                research_id="R-20260721-001-dyslipidemia",
                claims=[EvidenceClaim(claim_id="C-001", statement="Test claim", source_ids=["S-999"])],
                sources=[ResearchSource(
                    source_id="S-001", title="Example guideline", url="https://example.org/guideline",
                    source_type=SourceType.PROFESSIONAL_GUIDELINE,
                )],
            )

    def test_editorial_payload_has_normalized_evidence_only(self) -> None:
        bundle = EvidenceBundle(
            research_id="R-20260721-001-dyslipidemia",
            claims=[EvidenceClaim(claim_id="C-001", statement="Evidence-supported statement", source_ids=["S-001"])],
            sources=[ResearchSource(
                source_id="S-001", title="Example guideline", url="https://example.org/guideline",
                source_type=SourceType.PROFESSIONAL_GUIDELINE,
            )],
        )
        payload = editorial_payload(bundle)
        self.assertEqual(payload["research_id"], "R-20260721-001-dyslipidemia")
        self.assertEqual(payload["claims"][0]["source_ids"], ["S-001"])
        self.assertNotIn("openmanus_raw", payload)

    def test_research_id_format(self) -> None:
        identifier = make_research_id(1, at=datetime(2026, 7, 21, tzinfo=timezone.utc), slug="Dyslipidemia Update")
        self.assertEqual(identifier, "R-20260721-001-dyslipidemia-update")


if __name__ == "__main__":
    unittest.main()
