"""Pydantic data models for JurisLens AI."""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk severity classification for legal clauses."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Clause(BaseModel):
    """Segmented clause with spatial and navigational coordinates."""
    clause_id: str = Field(..., description="Unique slug or identifier, e.g. 'clause_8.2'")
    number: str = Field(..., description="Clause label or number, e.g. '8.2' or 'Section 5'")
    title: str = Field(..., description="Clause heading or inferred title")
    text: str = Field(..., description="Full text of the clause")
    page_number: int = Field(default=1, description="Estimated or exact page number")
    line_start: int = Field(default=1, description="Starting line number")
    line_end: int = Field(default=1, description="Ending line number")
    category: str = Field(default="General", description="Topic category: Termination, IP, Compensation, etc.")


class ParsedDocument(BaseModel):
    """Structured representation of an ingested document."""
    document_id: str
    filename: str
    total_clauses: int
    estimated_pages: int
    raw_text: str
    clauses: List[Clause]


class RiskFinding(BaseModel):
    """Analysis finding detailing a specific risk or obligation."""
    clause_id: str = Field(..., description="Target clause id for verification")
    clause_title: str = Field(..., description="Title of the clause")
    clause_number: str = Field(..., description="E.g. '8.2'")
    risk_level: RiskLevel
    plain_summary: str = Field(..., description="Plain-language translation of the clause")
    original_snippet: str = Field(..., description="Verbatim snippet from document for grounding")
    potential_risk: str = Field(..., description="Why this matters or what harm/obligation it creates")
    action_item: str = Field(..., description="What the user should do, request, or verify")


class ObligationItem(BaseModel):
    """Actionable duty or deadline extracted from the document."""
    clause_id: str
    clause_number: str
    party: str = Field(..., description="Who owes this: Employee, Tenant, Recipient, etc.")
    obligation: str = Field(..., description="What must be done")
    deadline_or_trigger: str = Field(..., description="When it is due, e.g. 'Within 14 days of termination'")
    consequence: str = Field(..., description="Result if breached")


class MissingClauseAlert(BaseModel):
    """Flags critical provisions that are missing or omitted."""
    topic: str = Field(..., description="Missing topic: e.g. 'Stock Option Acceleration', 'Severance'")
    description: str = Field(..., description="Why this absence matters")
    significance: str = Field(..., description="Risk implication of the silence")
    suggested_inquiry: str = Field(..., description="Question to ask the other party")


class DocumentAnalysisResponse(BaseModel):
    """Complete grounded analysis output for a legal document."""
    document_id: str
    title: str
    document_type: str
    executive_summary: str
    overall_risk_score: int = Field(..., ge=0, le=100, description="0 (safest) to 100 (highest risk)")
    risk_level: RiskLevel
    key_findings: List[RiskFinding]
    obligations_checklist: List[ObligationItem]
    missing_protections: List[MissingClauseAlert]
    suggested_lawyer_questions: List[str]
    grounding_confidence: float = Field(..., ge=0, le=100)
    clauses: List[Clause]
    processed_by: str = "Google Gemini 2.5 Flash"
    disclaimer: str = (
        "JurisLens provides informational assistance and educational document navigation. "
        "It does not provide legal advice or create an attorney-client relationship. "
        "Always consult a qualified legal professional for binding legal decisions."
    )


class CitationMatch(BaseModel):
    """Grounded verbatim citation in original text."""
    clause_id: str
    clause_number: str
    page_number: int
    matched_snippet: str


class QARequest(BaseModel):
    """User question submitted against an ingested document."""
    document_id: str
    question: str
    user_role: str = "general"  # employee, tenant, freelancer, business, general


class QAResponse(BaseModel):
    """Grounded Q&A response with strict anti-hallucination handling."""
    question: str
    answer: str
    is_found_in_document: bool
    grounded_clauses: List[str]
    citations: List[CitationMatch]
    verification_guidance: str
    confidence: float
    lawyer_follow_up: Optional[str] = None
    disclaimer: str = "Informational answer only. Verify with referenced clauses and legal counsel."


class ComparisonRequest(BaseModel):
    """Request to compare two legal documents."""
    doc1_text: str
    doc2_text: str
    doc1_name: str = "Document A (Baseline)"
    doc2_name: str = "Document B (Proposed)"


class ComparisonDifference(BaseModel):
    """A distinct divergence between two documents."""
    category: str
    clause_title: str
    doc1_summary: str
    doc2_summary: str
    doc1_snippet: str
    doc2_snippet: str
    risk_shift: str  # MORE_FAVORABLE_DOC1, MORE_FAVORABLE_DOC2, NEUTRAL, CRITICAL_RISK_ADDED
    explanation: str


class ComparisonResponse(BaseModel):
    """Side-by-side comparison output."""
    comparison_summary: str
    doc1_name: str
    doc2_name: str
    differences: List[ComparisonDifference]
    verdict: str
    key_takeaways: List[str]
    processed_by: str = "Google Gemini 2.5 Flash"


class LawyerBriefRequest(BaseModel):
    """Request to generate a 1-page attorney consultation briefing sheet."""
    document_id: str
    user_notes: Optional[str] = None


class LawyerBriefResponse(BaseModel):
    """Structured lawyer consultation packet."""
    document_title: str
    document_type: str
    generated_date: str
    user_context: str
    top_risks_for_review: List[Dict[str, str]]
    critical_omissions: List[str]
    prepared_questions_for_counsel: List[str]
    statutory_jurisdiction_notes: str
    formatted_markdown: str
    disclaimer: str
