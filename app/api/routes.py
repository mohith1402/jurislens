"""API Route Handlers for JurisLens AI."""

import os
from typing import Optional
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import sanitize_text_input, validate_file_upload
from app.models.schemas import (
    ComparisonRequest,
    ComparisonResponse,
    DocumentAnalysisResponse,
    LawyerBriefRequest,
    LawyerBriefResponse,
    ParsedDocument,
    QARequest,
    QAResponse,
)
from app.services.comparison_engine import comparison_engine
from app.services.document_parser import document_parser
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/api", tags=["Legal Intelligence"])


class AnalyzeTextInput(BaseModel):
    """Input payload for direct text analysis."""
    text: str
    title: Optional[str] = "Pasted Contract Document"


@router.get("/health")
async def health_check():
    """System health check and runtime capabilities report."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "gemini_model": settings.GEMINI_MODEL,
        "live_gemini_connected": settings.has_live_gemini_key,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/samples")
async def get_sample_documents():
    """Returns pre-packaged legal documents for rapid 1-click evaluation."""
    samples = []
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_documents")

    catalog = [
        {
            "id": "sample_employment",
            "name": "Employment Agreement (Executive Tech Role)",
            "file": "employment_agreement_sample.txt",
            "description": "Realistic 25-clause contract containing a 60-day notice, aggressive 24-month non-compete, and omitting stock options.",
        },
        {
            "id": "sample_nda_standard",
            "name": "Mutual NDA (Balanced Standard)",
            "file": "nda_standard_mutual.txt",
            "description": "Standard balanced 2-year mutual non-disclosure agreement.",
        },
        {
            "id": "sample_nda_aggressive",
            "name": "Vendor NDA & Indemnity (Aggressive One-Sided)",
            "file": "nda_aggressive_vendor.txt",
            "description": "Perpetual duration, unilateral unlimited indemnification, and liquidated damages.",
        },
    ]

    for item in catalog:
        filepath = os.path.join(sample_dir, item["file"])
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            samples.append({**item, "content": content})

    return {"samples": samples}


@router.post("/analyze-text", response_model=DocumentAnalysisResponse)
async def analyze_text(payload: AnalyzeTextInput):
    """
    Parses pasted text, segments into numbered clauses, and generates grounded Gemini 2.5 analysis.
    """
    sanitized = sanitize_text_input(payload.text)
    if not sanitized or len(sanitized.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contract text is too short or empty to parse meaningful legal clauses.",
        )

    parsed_doc = document_parser.parse_text(sanitized, filename=payload.title or "Contract Document")
    analysis = await gemini_service.analyze_document(parsed_doc)
    return analysis


@router.post("/upload", response_model=DocumentAnalysisResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Safely uploads and parses a contract document (.txt, .md, .pdf, .docx).
    """
    content_bytes = await file.read()
    is_valid, err_msg = validate_file_upload(file.filename or "", content_bytes)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    try:
        raw_text = content_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unable to decode text from uploaded file: {exc}",
        )

    sanitized = sanitize_text_input(raw_text)
    parsed_doc = document_parser.parse_text(sanitized, filename=file.filename or "Uploaded Document")
    analysis = await gemini_service.analyze_document(parsed_doc)
    return analysis


@router.get("/document/{document_id}", response_model=ParsedDocument)
async def get_parsed_document(document_id: str):
    """Retrieves an ingested document and its segmented clauses."""
    doc = document_parser.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document ID not found or expired.")
    return doc


@router.post("/qa", response_model=QAResponse)
async def ask_question(payload: QARequest):
    """
    Answers a question about a document with strict verification and anti-hallucination.
    """
    doc = document_parser.get_document(payload.document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    sanitized_q = sanitize_text_input(payload.question, max_length=1000)
    if not sanitized_q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty.")

    payload.question = sanitized_q
    qa_response = await gemini_service.answer_question(doc, payload)
    return qa_response


@router.post("/compare", response_model=ComparisonResponse)
async def compare_documents(payload: ComparisonRequest):
    """
    Compares two contracts side-by-side and returns redline risk shifts.
    """
    doc1_text = sanitize_text_input(payload.doc1_text)
    doc2_text = sanitize_text_input(payload.doc2_text)

    if not doc1_text or not doc2_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both documents are required for comparison.")

    return comparison_engine.compare_documents(
        doc1_text=doc1_text,
        doc2_text=doc2_text,
        doc1_name=payload.doc1_name,
        doc2_name=payload.doc2_name,
    )


@router.post("/lawyer-brief", response_model=LawyerBriefResponse)
async def generate_lawyer_brief(payload: LawyerBriefRequest):
    """
    Generates a structured 1-page attorney consultation brief packet.
    """
    doc = document_parser.get_document(payload.document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    analysis = await gemini_service.analyze_document(doc)
    notes = sanitize_text_input(payload.user_notes or "", max_length=2000)
    return gemini_service.generate_lawyer_brief(doc, analysis, user_notes=notes)
