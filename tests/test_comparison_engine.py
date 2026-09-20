"""Unit tests for Contract-to-Contract Comparison Engine."""

from app.services.comparison_engine import comparison_engine


def test_compare_standard_vs_aggressive_nda(sample_standard_nda_text, sample_aggressive_nda_text):
    """Verify comparison detects redline changes and critical risk additions."""
    res = comparison_engine.compare_documents(
        doc1_text=sample_standard_nda_text,
        doc2_text=sample_aggressive_nda_text,
        doc1_name="Standard Mutual NDA",
        doc2_name="Aggressive Vendor NDA",
    )

    assert res.doc1_name == "Standard Mutual NDA"
    assert res.doc2_name == "Aggressive Vendor NDA"
    assert len(res.differences) >= 3

    # Check for critical risk additions (e.g. indemnity or non-compete added)
    risk_shifts = [d.risk_shift for d in res.differences]
    assert "CRITICAL_RISK_ADDED" in risk_shifts

    # Check verdict contains caution
    assert "CAUTION" in res.verdict or "critical risk" in res.verdict.lower()
    assert len(res.key_takeaways) >= 2


def test_compare_identical_documents(sample_standard_nda_text):
    """Verify comparing identical documents yields neutral risk shift."""
    res = comparison_engine.compare_documents(
        doc1_text=sample_standard_nda_text,
        doc2_text=sample_standard_nda_text,
        doc1_name="Copy A",
        doc2_name="Copy B",
    )

    assert len(res.differences) >= 1
    # No critical risk should be added when documents are identical
    risk_shifts = [d.risk_shift for d in res.differences]
    assert "CRITICAL_RISK_ADDED" not in risk_shifts
