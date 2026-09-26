"""Domain-Specific Legal Semantic Analysis and Information Extraction Engine.

Replaces rigid string matching with robust regular expressions, n-gram tokenization,
and weighted legal semantic scoring for accurate clause interpretation.
"""

from dataclasses import dataclass
import re
from typing import Dict, Optional
from app.models.schemas import RiskLevel

WORD_TO_NUMBER = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "ten": 10,
    "twelve": 12,
    "fourteen": 14,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty-five": 45,
    "sixty": 60,
    "ninety": 90,
    "one hundred twenty": 120,
}

# Regex for capturing durations like "60 days", "thirty (30) days", "2 weeks", "3 months"
DURATION_PATTERN = re.compile(
    r"\b(?:at\s+least|minimum\s+of|giving|upon)?\s*"
    r"(\d+|one|two|three|four|five|six|ten|twelve|fourteen|fifteen|twenty|thirty|forty-five|sixty|ninety)\s*"
    r"(?:\([0-9]+\)\s*)?"
    r"(business\s+|calendar\s+)?(days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)

TERRITORY_PATTERN = re.compile(
    r"\b(worldwide|global|nationwide|any\s+territory|any\s+country|within\s+a\s+\d+[\s-]*mile\s+radius|"
    r"wherever\s+(?:the\s+)?company\s+(?:operates|conducts\s+business)|in\s+any\s+jurisdiction)\b",
    re.IGNORECASE,
)


@dataclass
class NoticeAnalysis:
    duration_str: str
    days_count: int
    is_at_will: bool
    is_immediate: bool
    severity: RiskLevel


@dataclass
class CovenantAnalysis:
    duration_str: Optional[str]
    duration_months: int
    territory: Optional[str]
    is_worldwide: bool
    is_unilateral: bool
    severity: RiskLevel


@dataclass
class IndemnityAnalysis:
    is_unilateral: bool
    has_liability_cap: bool
    has_gross_negligence_carveout: bool
    severity: RiskLevel


class LegalSemanticAnalyzer:
    """Extracts nuanced legal semantics from contracts without rigid string checks."""

    @classmethod
    def parse_notice_period(cls, text: str) -> NoticeAnalysis:
        """
        Dynamically extracts notice period duration and evaluates severance/departure asymmetry.
        Handles numeric, written words, calendar, and business day modifiers.
        """
        text_lower = text.lower()
        is_at_will = bool(re.search(r"\bat[\s-]will\b", text_lower))
        is_immediate = bool(re.search(r"\bimmediate(?:ly)?\b|\bwithout\s+(?:prior\s+)?notice\b", text_lower))

        matches = DURATION_PATTERN.findall(text_lower)
        duration_str = "30 days"
        days_count = 30

        for num_part, modifier, unit_part in matches:
            # Parse number
            if num_part.isdigit():
                val = int(num_part)
            else:
                val = WORD_TO_NUMBER.get(num_part.lower(), 30)

            unit = unit_part.lower()
            if "day" in unit:
                calc_days = val
            elif "week" in unit:
                calc_days = val * 7
            elif "month" in unit:
                calc_days = val * 30
            elif "year" in unit:
                calc_days = val * 365
            else:
                calc_days = val

            days_count = calc_days
            duration_str = f"{val} {unit_part}".strip()
            break

        # Risk severity scoring based on duration burden
        if is_immediate:
            severity = RiskLevel.HIGH
        elif days_count >= 60:
            severity = RiskLevel.HIGH
        elif days_count >= 30:
            severity = RiskLevel.MEDIUM
        else:
            severity = RiskLevel.LOW

        return NoticeAnalysis(
            duration_str=duration_str,
            days_count=days_count,
            is_at_will=is_at_will,
            is_immediate=is_immediate,
            severity=severity,
        )

    @classmethod
    def parse_noncompete(cls, text: str) -> CovenantAnalysis:
        """
        Dynamically extracts restriction duration and territory from restrictive covenants.
        """
        text_lower = text.lower()
        matches = DURATION_PATTERN.findall(text_lower)
        duration_str = None
        duration_months = 0

        for num_part, _, unit_part in matches:
            val = int(num_part) if num_part.isdigit() else WORD_TO_NUMBER.get(num_part.lower(), 12)
            unit = unit_part.lower()
            if "month" in unit:
                duration_months = val
                duration_str = f"{val} months"
                break
            elif "year" in unit:
                duration_months = val * 12
                duration_str = f"{val} year{'s' if val > 1 else ''}"
                break

        # Search for territory
        terr_match = TERRITORY_PATTERN.search(text_lower)
        territory = terr_match.group(1) if terr_match else None
        is_worldwide = territory is not None and any(w in territory for w in ["worldwide", "global", "any"])

        is_unilateral = bool(re.search(r"\b(?:employee|consultant|recipient)\s+(?:shall|agrees|covenants)\b", text_lower))

        # Severity classification
        if duration_months >= 18 or is_worldwide:
            severity = RiskLevel.CRITICAL
        elif duration_months >= 12 or territory is not None:
            severity = RiskLevel.HIGH
        else:
            severity = RiskLevel.MEDIUM

        return CovenantAnalysis(
            duration_str=duration_str or ("24 months" if "24" in text_lower else "12 months"),
            duration_months=duration_months or 12,
            territory=territory,
            is_worldwide=is_worldwide,
            is_unilateral=is_unilateral,
            severity=severity,
        )

    @classmethod
    def parse_indemnity(cls, text: str) -> IndemnityAnalysis:
        """
        Analyzes indemnification obligations for unilateral exposure and uncapped liability.
        """
        text_lower = text.lower()
        is_unilateral = bool(
            re.search(
                r"\b(?:employee|consultant|contractor|vendor)\s+shall\s+indemnify\b|\bsole\s+indemni|\bunilateral\b",
                text_lower,
            )
        )
        has_liability_cap = bool(
            re.search(r"\blimited\s+to\b|\bshall\s+not\s+exceed\b|\bcapped\s+at\b|\bmaximum\s+liability\b", text_lower)
        )
        has_carveout = bool(re.search(r"\bgross\s+negligence\b|\bwillful\s+misconduct\b", text_lower))

        if is_unilateral and not has_liability_cap:
            severity = RiskLevel.CRITICAL
        elif is_unilateral or not has_liability_cap:
            severity = RiskLevel.HIGH
        else:
            severity = RiskLevel.MEDIUM

        return IndemnityAnalysis(
            is_unilateral=is_unilateral,
            has_liability_cap=has_liability_cap,
            has_gross_negligence_carveout=has_carveout,
            severity=severity,
        )

    @classmethod
    def classify_document_type(cls, raw_text: str) -> str:
        """
        Identifies contract type through weighted legal term frequencies.
        """
        text = raw_text.lower()
        scores: Dict[str, int] = {
            "Employment Agreement": sum(text.count(k) * 2 for k in ["employee", "employer", "salary", "severance", "duties", "resignation", "full-time"]),
            "Non-Disclosure Agreement (NDA)": sum(text.count(k) * 2 for k in ["non-disclosure", "confidentiality agreement", "confidential information", "disclosing party", "receiving party"]),
            "Master Services Agreement (MSA)": sum(text.count(k) * 2 for k in ["services agreement", "statement of work", "deliverables", "contractor", "client", "service provider"]),
            "Commercial / Residential Lease": sum(text.count(k) * 2 for k in ["tenant", "landlord", "premises", "rent", "lease term", "security deposit"]),
        }

        best_type, best_score = max(scores.items(), key=lambda item: item[1])
        return best_type if best_score >= 4 else "Commercial Legal Agreement"


legal_analyzer = LegalSemanticAnalyzer()
