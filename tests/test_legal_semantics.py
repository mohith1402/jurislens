"""Unit tests for the dynamic Legal Semantic Analyzer."""

from app.models.schemas import RiskLevel
from app.services.legal_semantics import legal_analyzer


def test_parse_notice_period_various_formats():
    """Verify notice parser dynamically extracts numbers, words, and units."""
    # 1. Numeric days with modifier
    n1 = legal_analyzer.parse_notice_period("Either party may terminate upon giving 45 business days written notice.")
    assert n1.duration_str == "45 days"
    assert n1.days_count == 45
    assert n1.severity in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    # 2. Written word with parentheses (typical legal drafting)
    n2 = legal_analyzer.parse_notice_period("Termination requires sixty (60) days prior written notice.")
    assert n2.duration_str == "60 days"
    assert n2.days_count == 60
    assert n2.severity == RiskLevel.HIGH

    # 3. Months duration
    n3 = legal_analyzer.parse_notice_period("Subject to three months advance notice.")
    assert n3.duration_str == "3 months"
    assert n3.days_count == 90
    assert n3.severity == RiskLevel.HIGH

    # 4. At-will and immediate termination
    n4 = legal_analyzer.parse_notice_period("Employment is strictly at-will and subject to immediate termination without notice.")
    assert n4.is_at_will is True
    assert n4.is_immediate is True
    assert n4.severity == RiskLevel.HIGH


def test_parse_noncompete_duration_and_territory():
    """Verify non-compete parser extracts durations and geographic constraints."""
    # 1. Broad worldwide covenant
    cov1 = legal_analyzer.parse_noncompete(
        "Employee shall not engage in competing activities for a period of 2 years worldwide."
    )
    assert cov1.duration_str == "2 years"
    assert cov1.duration_months == 24
    assert cov1.is_worldwide is True
    assert cov1.severity == RiskLevel.CRITICAL

    # 2. Reasonable regional covenant
    cov2 = legal_analyzer.parse_noncompete(
        "Consultant covenants not to compete for 6 months within a 25-mile radius."
    )
    assert cov2.duration_str == "6 months"
    assert cov2.duration_months == 6
    assert cov2.is_worldwide is False
    assert cov2.severity in (RiskLevel.MEDIUM, RiskLevel.HIGH)


def test_parse_indemnity_unilateral_and_caps():
    """Verify indemnity parser identifies unilateral exposure and liability caps."""
    # 1. Aggressive unilateral uncapped indemnity
    ind1 = legal_analyzer.parse_indemnity(
        "Vendor shall indemnify and hold harmless Customer against all claims and damages."
    )
    assert ind1.is_unilateral is True
    assert ind1.has_liability_cap is False
    assert ind1.severity == RiskLevel.CRITICAL

    # 2. Balanced mutual indemnity with liability cap and carveout
    ind2 = legal_analyzer.parse_indemnity(
        "Each party indemnifies the other, capped at total fees paid, except for gross negligence."
    )
    assert ind2.is_unilateral is False
    assert ind2.has_liability_cap is True
    assert ind2.has_gross_negligence_carveout is True
    assert ind2.severity == RiskLevel.MEDIUM


def test_classify_document_type():
    """Verify document classifier distinguishes contracts by weighted terminology."""
    emp_sample = "Employment agreement between Employer and Employee detailing salary, duties, and severance."
    nda_sample = "Non-Disclosure Agreement between Disclosing Party and Receiving Party protecting confidential information."

    assert legal_analyzer.classify_document_type(emp_sample) == "Employment Agreement"
    assert legal_analyzer.classify_document_type(nda_sample) == "Non-Disclosure Agreement (NDA)"
