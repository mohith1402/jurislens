"""Unit tests for the Gemini 2.5 Legal Intelligence Service."""

import pytest
from app.models.schemas import QARequest, RiskLevel
from app.services.gemini_service import gemini_service


@pytest.mark.asyncio
async def test_analyze_document_structure(parsed_employment_doc):
    """Verify Gemini legal service generates grounded analysis."""
    analysis = await gemini_service.analyze_document(parsed_employment_doc)

    assert analysis.document_id == parsed_employment_doc.document_id
    assert analysis.overall_risk_score > 0
    assert analysis.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    assert len(analysis.key_findings) >= 2
    assert len(analysis.obligations_checklist) >= 1
    assert len(analysis.missing_protections) >= 1
    assert analysis.grounding_confidence >= 90.0

    # Ensure disclaimer is included
    assert "not provide legal advice" in analysis.disclaimer.lower()


@pytest.mark.asyncio
async def test_qa_grounded_notice_period(parsed_employment_doc):
    """Verify QA grounds notice period question to Clause 8.2 with 60 days."""
    req = QARequest(
        document_id=parsed_employment_doc.document_id,
        question="What is the required notice period if I resign?",
        user_role="employee",
    )
    res = await gemini_service.answer_question(parsed_employment_doc, req)

    assert res.is_found_in_document is True
    assert "60 days" in res.answer.lower()
    assert any("8.2" in str(c) for c in res.grounded_clauses)
    assert len(res.citations) >= 1


@pytest.mark.asyncio
async def test_qa_missing_stock_options_anti_hallucination(parsed_employment_doc):
    """
    CRITICAL EVALUATION TEST (From Briefing):
    Verify that asking about stock options when absent from the document
    returns is_found_in_document=False, does NOT hallucinate terms,
    and recommends asking counsel.
    """
    req = QARequest(
        document_id=parsed_employment_doc.document_id,
        question="What happens to my stock options if I resign?",
        user_role="employee",
    )
    res = await gemini_service.answer_question(parsed_employment_doc, req)

    # Must be explicitly marked as not found
    assert res.is_found_in_document is False
    assert "cannot be determined" in res.answer.lower() or "does not contain" in res.answer.lower()
    assert len(res.grounded_clauses) == 0
    assert res.lawyer_follow_up is not None


def test_generate_lawyer_brief(parsed_employment_doc):
    """Verify generating a 1-page attorney consultation briefing sheet."""
    import asyncio
    analysis = asyncio.run(gemini_service.analyze_document(parsed_employment_doc))

    brief = gemini_service.generate_lawyer_brief(
        doc=parsed_employment_doc,
        analysis=analysis,
        user_notes="Review before signing offer letter",
    )

    assert brief.document_title == parsed_employment_doc.filename
    assert len(brief.top_risks_for_review) >= 1
    assert len(brief.critical_omissions) >= 1
    assert len(brief.prepared_questions_for_counsel) >= 1
    assert "LEGAL CONSULTATION BRIEFING PACKET" in brief.formatted_markdown
    assert "DISCLAIMER" in brief.formatted_markdown
