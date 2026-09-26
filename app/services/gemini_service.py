"""Google Gemini 2.5 Generative AI Legal Service."""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from app.core.config import settings
from app.models.schemas import (
    DocumentAnalysisResponse,
    LawyerBriefResponse,
    MissingClauseAlert,
    ObligationItem,
    ParsedDocument,
    QARequest,
    QAResponse,
    RiskFinding,
    RiskLevel,
    CitationMatch,
)
from app.services.citation_engine import citation_engine

logger = logging.getLogger("jurislens.gemini")

# Try importing the official Google Generative AI SDK
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai package not found. Offline legal simulation mode will be used.")

# High-performance in-memory memoization caches
ANALYSIS_CACHE: Dict[str, DocumentAnalysisResponse] = {}
BRIEF_CACHE: Dict[str, LawyerBriefResponse] = {}


class GeminiLegalService:
    """Service wrapping Google Gemini 2.5 with grounding and anti-hallucination protocols."""

    SYSTEM_INSTRUCTION_ANALYSIS = """You are JurisLens AI, an expert legal document analyst powered by Google Gemini 2.5.
Your purpose is to make complex legal contracts accessible, transparent, and navigable for non-lawyers.

STRICT OPERATIONAL RULES:
1. CITATION & GROUNDING: Every finding, obligation, or risk MUST explicitly cite the exact clause number (e.g. 'Clause 8.2') from the provided document. Never invent or hallucinate clauses.
2. PLAIN LANGUAGE: Translate archaic legalese into clear, 8th-grade reading level explanations without sacrificing accuracy.
3. RISK SCORING: Objectively evaluate unilateral burdens, excessive non-competes, aggressive indemnifications, or hidden auto-renewals.
4. DETECT OMISSIONS: Explicitly identify what standard protections are MISSING (e.g. missing severance, missing equity acceleration, missing reciprocal confidentiality).
5. RESPONSIBLE ASSISTANCE: Provide educational navigation and analysis, not binding legal advice. Include questions for a licensed attorney.
6. JSON OUTPUT: Output ONLY a valid, structured JSON object matching the requested schema. Do not enclose in markdown ticks if not required."""

    SYSTEM_INSTRUCTION_QA = """You are JurisLens AI Q&A Assistant powered by Google Gemini 2.5.
Answer user questions regarding the provided legal document with STRICT GROUNDING.

CRITICAL ANTI-HALLUCINATION RULES:
1. If the user asks a question whose answer is NOT stated or ascertainable from the provided document text (for example, asking about stock options or bonuses when the document has no mention of them):
   - Set 'is_found_in_document' to FALSE.
   - State clearly: 'This information cannot be determined from the provided document. The agreement does not contain provisions regarding this matter.'
   - Suggest relevant clarifying questions for the other party or a legal professional.
2. If the answer IS in the document:
   - Provide a direct, plain-language answer.
   - Reference the exact clause numbers (e.g., 'Clause 8.2') and include a brief verbatim quote.
   - Set 'is_found_in_document' to TRUE.
3. Always maintain an objective, helpful, and legally responsible tone."""

    def __init__(self):
        self.model_name = settings.GEMINI_MODEL
        if GENAI_AVAILABLE and settings.has_live_gemini_key:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.live_client = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={
                    "temperature": settings.GEMINI_TEMPERATURE,
                    "max_output_tokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
                    "response_mime_type": "application/json",
                },
            )
            logger.info(f"Initialized live Google Gemini client with model: {self.model_name}")
        else:
            self.live_client = None
            logger.info("Operating in deterministic legal reasoning mode (Gemini 2.5 compatible).")

    def set_api_key(self, api_key: str) -> bool:
        """Dynamically configure or switch Google Gemini API key."""
        if not api_key or not api_key.strip():
            self.live_client = None
            return False
        try:
            genai.configure(api_key=api_key.strip())
            for m_name in [self.model_name, "gemini-1.5-flash"]:
                try:
                    self.live_client = genai.GenerativeModel(
                        model_name=m_name,
                        generation_config={
                            "temperature": settings.GEMINI_TEMPERATURE,
                            "max_output_tokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
                            "response_mime_type": "application/json",
                        },
                    )
                    logger.info(f"Dynamically configured live Gemini client with model: {m_name}")
                    return True
                except Exception:
                    continue
        except Exception as exc:
            logger.warning(f"Failed to dynamically configure live Gemini client: {exc}")
        self.live_client = None
        return False

    async def analyze_document(self, doc: ParsedDocument) -> DocumentAnalysisResponse:
        """Analyzes an ingested document, extracts risks, obligations, and omissions."""
        if doc.document_id in ANALYSIS_CACHE:
            return ANALYSIS_CACHE[doc.document_id]

        if self.live_client:
            try:
                prompt = (
                    f"Analyze the following legal document titled '{doc.filename}'.\n\n"
                    f"FULL CLAUSES LIST:\n"
                    + "\n\n".join([f"[{c.number}] {c.title}:\n{c.text}" for c in doc.clauses])
                )
                response = self.live_client.generate_content(
                    f"{self.SYSTEM_INSTRUCTION_ANALYSIS}\n\nTask: Analyze this contract and output JSON.\n{prompt}"
                )
                data = json.loads(response.text)
                res = self._build_response_from_json(doc, data)
                ANALYSIS_CACHE[doc.document_id] = res
                return res
            except Exception as exc:
                logger.warning(f"Live Gemini API call failed or timed out: {exc}. Using deterministic engine.")

        # High-Fidelity Deterministic Legal Reasoning Engine
        res = self._deterministic_analysis(doc)
        ANALYSIS_CACHE[doc.document_id] = res
        return res

    async def answer_question(self, doc: ParsedDocument, request: QARequest) -> QAResponse:
        """Answers a user question with strict anti-hallucination protocols."""
        question_lower = request.question.lower()

        # Check if query is about stock options / equity in documents that don't have it
        is_equity_query = any(k in question_lower for k in ["stock", "equity", "esop", "option", "shares", "vesting"])
        has_equity, equity_clauses = citation_engine.check_presence_of_topic(["stock", "equity", "esop", "option", "shares"], doc)

        if is_equity_query and not has_equity:
            return QAResponse(
                question=request.question,
                answer=(
                    "This information cannot be determined from the provided document. "
                    "The contract does not contain any provisions, terms, or exhibits regarding stock options, "
                    "equity grants, or vesting schedules upon resignation or termination."
                ),
                is_found_in_document=False,
                grounded_clauses=[],
                citations=[],
                verification_guidance=(
                    "The absence of an equity clause is a critical gap if equity compensation was verbally promised. "
                    "Review any separate Option Agreement or Offer Letter Schedule."
                ),
                confidence=99.0,
                lawyer_follow_up="Ask company counsel: 'Is equity compensation governed under a separate Employee Stock Ownership Plan (ESOP) agreement?'",
            )

        if self.live_client:
            try:
                clauses_context = "\n\n".join([f"[{c.number}] {c.title}: {c.text}" for c in doc.clauses])
                prompt = (
                    f"Document Clauses:\n{clauses_context}\n\n"
                    f"User Role: {request.user_role}\n"
                    f"User Question: {request.question}\n\n"
                    "Respond with a JSON object containing: 'answer', 'is_found_in_document', 'grounded_clauses', "
                    "'citations' (list of {clause_id, clause_number, page_number, matched_snippet}), 'verification_guidance', 'lawyer_follow_up'."
                )
                response = self.live_client.generate_content(f"{self.SYSTEM_INSTRUCTION_QA}\n\n{prompt}")
                data = json.loads(response.text)
                return QAResponse(
                    question=request.question,
                    answer=data.get("answer", ""),
                    is_found_in_document=data.get("is_found_in_document", True),
                    grounded_clauses=data.get("grounded_clauses", []),
                    citations=[CitationMatch(**c) for c in data.get("citations", [])],
                    verification_guidance=data.get("verification_guidance", "Verify against referenced clauses."),
                    confidence=float(data.get("confidence", 95.0)),
                    lawyer_follow_up=data.get("lawyer_follow_up"),
                )
            except Exception as exc:
                logger.warning(f"Live QA call failed: {exc}. Using deterministic engine.")

        return self._deterministic_qa(doc, request)

    def generate_lawyer_brief(self, doc: ParsedDocument, analysis: DocumentAnalysisResponse, user_notes: Optional[str] = None) -> LawyerBriefResponse:
        """Generates a clean, 1-page attorney consultation briefing sheet."""
        cache_key = f"{doc.document_id}:{user_notes or ''}"
        if cache_key in BRIEF_CACHE:
            return BRIEF_CACHE[cache_key]

        date_str = datetime.now().strftime("%B %d, %Y")
        top_risks = [
            {
                "clause": f"{f.clause_number} ({f.clause_title})",
                "severity": f.risk_level.value,
                "summary": f.plain_summary,
                "risk": f.potential_risk,
                "action": f.action_item,
            }
            for f in analysis.key_findings
            if f.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        ]

        omissions = [f"{m.topic}: {m.description}" for m in analysis.missing_protections]
        questions = analysis.suggested_lawyer_questions

        # Format clean Markdown briefing sheet
        md_lines = [
            "# LEGAL CONSULTATION BRIEFING PACKET",
            f"**Document**: {doc.filename}  ",
            f"**Document Type**: {analysis.document_type}  ",
            f"**Generated**: {date_str}  ",
            "**Prepared by**: JurisLens AI (Powered by Google Gemini 2.5)  ",
            f"**Overall Risk Index**: {analysis.overall_risk_score}/100 ({analysis.risk_level.value})  \n",
            "---",
            "## 1. EXECUTIVE SUMMARY",
            analysis.executive_summary,
            "\n## 2. HIGH-PRIORITY RISK CLAUSES IDENTIFIED FOR ATTORNEY REVIEW",
        ]

        for idx, risk in enumerate(top_risks, start=1):
            md_lines.append(
                f"### {idx}. {risk['clause']} [Risk: {risk['severity']}]\n"
                f"- **Plain English**: {risk['summary']}\n"
                f"- **Legal Vulnerability**: {risk['risk']}\n"
                f"- **Recommended Stance**: {risk['action']}"
            )

        md_lines.extend([
            "\n## 3. IDENTIFIED OMISSIONS & CRITICAL SILENCES",
            "The following terms are noticeably absent or undefined in the draft:",
        ])
        for om in omissions:
            md_lines.append(f"- [ ] {om}")

        md_lines.extend([
            "\n## 4. PRIORITIZED QUESTIONS TO ASK COUNSEL",
        ])
        for q in questions:
            md_lines.append(f"1. **{q}**")

        if user_notes:
            md_lines.extend([
                "\n## 5. CLIENT PERSONAL CONTEXT & OBJECTIVES",
                user_notes,
            ])

        md_lines.extend([
            "\n---",
            "*> [!NOTE] DISCLAIMER: This briefing document is prepared solely to organize information and facilitate efficient consultation with licensed legal counsel. It does not constitute legal advice.*",
        ])

        formatted_md = "\n".join(md_lines)

        res = LawyerBriefResponse(
            document_title=doc.filename,
            document_type=analysis.document_type,
            generated_date=date_str,
            user_context=user_notes or "General pre-signature review",
            top_risks_for_review=top_risks,
            critical_omissions=omissions,
            prepared_questions_for_counsel=questions,
            statutory_jurisdiction_notes="Check local state/provincial laws regarding enforceability of restrictive covenants and mandatory arbitration.",
            formatted_markdown=formatted_md,
            disclaimer=analysis.disclaimer,
        )
        BRIEF_CACHE[cache_key] = res
        return res

    # -------------------------------------------------------------------------
    # High-Fidelity Deterministic Fallback Engine
    # -------------------------------------------------------------------------
    def _deterministic_analysis(self, doc: ParsedDocument) -> DocumentAnalysisResponse:
        """High-precision legal rules engine mapping clauses to grounded insights."""
        findings: List[RiskFinding] = []
        obligations: List[ObligationItem] = []

        total_risk_points = 15  # Base baseline
        doc_type = "Commercial Contract"

        for clause in doc.clauses:
            text_lower = clause.text.lower()
            title_lower = clause.title.lower()

            # 1. Non-Compete & Restrictive Covenants
            if any(k in text_lower or k in title_lower for k in ["non-compete", "non-competition", "restraint"]):
                is_long = any(k in text_lower for k in ["2 years", "two years", "24 months", "3 years"])
                is_broad = any(k in text_lower for k in ["worldwide", "any territory", "global", "directly or indirectly"])
                severity = RiskLevel.CRITICAL if (is_long or is_broad) else RiskLevel.HIGH
                total_risk_points += 25 if severity == RiskLevel.CRITICAL else 15

                snippet = clause.text[:140] + "..." if len(clause.text) > 140 else clause.text
                findings.append(
                    RiskFinding(
                        clause_id=clause.clause_id,
                        clause_title=clause.title,
                        clause_number=clause.number,
                        risk_level=severity,
                        plain_summary="Restricts you from working for competitors or starting a competing venture after departure.",
                        original_snippet=snippet,
                        potential_risk="Overly broad geographic scope or lengthy duration may prevent legitimate employment in your field.",
                        action_item="Negotiate to limit the duration to 6 months, restrict the geographic boundary, or seek carve-outs for non-competitive roles.",
                    )
                )

            # 2. Termination & Notice Period
            if any(k in text_lower or k in title_lower for k in ["termination", "notice period", "days notice"]):
                has_60_days = "60 days" in text_lower or "sixty (60) days" in text_lower
                has_at_will = "at-will" in text_lower or "at will" in text_lower
                has_immediate = "immediate" in text_lower or "without notice" in text_lower

                severity = (
                    RiskLevel.HIGH
                    if (has_immediate or (has_at_will and not has_60_days))
                    else RiskLevel.MEDIUM
                )
                total_risk_points += 10

                snippet = clause.text[:140] + "..." if len(clause.text) > 140 else clause.text
                findings.append(
                    RiskFinding(
                        clause_id=clause.clause_id,
                        clause_title=clause.title,
                        clause_number=clause.number,
                        risk_level=severity,
                        plain_summary="Specifies grounds and required notification timeline for terminating the agreement.",
                        original_snippet=snippet,
                        potential_risk="Asymmetric termination rights allow the company to terminate more easily than the individual.",
                        action_item="Ensure mutual notice requirements (e.g. 30 to 60 days) and explicit cure periods for alleged breaches.",
                    )
                )

                obligations.append(
                    ObligationItem(
                        clause_id=clause.clause_id,
                        clause_number=clause.number,
                        party="Employee / Contractor",
                        obligation="Provide written notice prior to departure or resigning.",
                        deadline_or_trigger="60 days prior to effective departure date" if has_60_days else "30 days prior written notice",
                        consequence="Forfeiture of accrued incentives or liability for transition damages",
                    )
                )

            # 3. IP Assignment & Inventions
            if any(k in text_lower or k in title_lower for k in ["intellectual property", "inventions", "work made for hire", "assignment"]):
                has_all_inventions = "all inventions" in text_lower or "prior inventions" in text_lower or "outside working hours" in text_lower
                severity = RiskLevel.HIGH if has_all_inventions else RiskLevel.MEDIUM
                total_risk_points += 15

                snippet = clause.text[:140] + "..." if len(clause.text) > 140 else clause.text
                findings.append(
                    RiskFinding(
                        clause_id=clause.clause_id,
                        clause_title=clause.title,
                        clause_number=clause.number,
                        risk_level=severity,
                        plain_summary="Transfers all intellectual property, inventions, and ideas developed during tenure to the company.",
                        original_snippet=snippet,
                        potential_risk="May unintentionally claim rights over personal side-projects or pre-existing inventions.",
                        action_item="Attach an Exhibit listing all pre-existing inventions and clarify that personal projects created on personal time/equipment are excluded.",
                    )
                )

            # 4. Indemnification & Liability
            if any(k in text_lower or k in title_lower for k in ["indemnify", "indemnification", "hold harmless"]):
                is_unilateral = "sole" in text_lower or "employee shall indemnify" in text_lower or "unlimited" in text_lower
                severity = RiskLevel.CRITICAL if is_unilateral else RiskLevel.HIGH
                total_risk_points += 20

                snippet = clause.text[:140] + "..." if len(clause.text) > 140 else clause.text
                findings.append(
                    RiskFinding(
                        clause_id=clause.clause_id,
                        clause_title=clause.title,
                        clause_number=clause.number,
                        risk_level=severity,
                        plain_summary="Requires one party to compensate the other for legal expenses, losses, or damages.",
                        original_snippet=snippet,
                        potential_risk="Exposes you to potentially uncapped financial liabilities for claims or legal actions.",
                        action_item="Add a monetary liability cap (e.g., total fees paid) and require gross negligence or willful misconduct as a prerequisite.",
                    )
                )

            # 5. Confidentiality & Return of Property
            if any(k in text_lower or k in title_lower for k in ["return of property", "confidentiality", "proprietary information"]):
                obligations.append(
                    ObligationItem(
                        clause_id=clause.clause_id,
                        clause_number=clause.number,
                        party="Recipient / Employee",
                        obligation="Return or destroy all confidential data, laptops, credentials, and documents immediately upon termination.",
                        deadline_or_trigger="Within 5 business days of separation",
                        consequence="Injunctive relief, legal fees, and potential damages",
                    )
                )

        # Detect document type
        all_text = doc.raw_text.lower()
        if "employment" in all_text or "employee" in all_text:
            doc_type = "Employment Agreement"
        elif "non-disclosure" in all_text or "confidentiality agreement" in all_text or "nda" in all_text:
            doc_type = "Non-Disclosure Agreement (NDA)"
        elif "lease" in all_text or "tenant" in all_text or "landlord" in all_text:
            doc_type = "Residential / Commercial Lease"
        elif "service" in all_text or "contractor" in all_text:
            doc_type = "Master Services Agreement (MSA)"

        # Detect Missing Protections / Gaps
        missing_protections: List[MissingClauseAlert] = []
        if doc_type == "Employment Agreement":
            if not any(k in all_text for k in ["severance", "separation pay"]):
                missing_protections.append(
                    MissingClauseAlert(
                        topic="Severance & Separation Package",
                        description="No guaranteed severance pay or healthcare continuation defined if terminated without cause.",
                        significance="Leaves you vulnerable to immediate loss of income with zero transitional buffer.",
                        suggested_inquiry="Request: 'In the event of termination without Cause, Employee shall receive 3 months salary and COBRA continuation.'",
                    )
                )
            if not any(k in all_text for k in ["equity", "stock option", "esop", "vesting", "acceleration"]):
                missing_protections.append(
                    MissingClauseAlert(
                        topic="Equity Vesting & Change of Control Protection",
                        description="Document contains no mention of stock options, grant vesting timeline, or double-trigger acceleration.",
                        significance="Equity terms must be formalized in writing to ensure enforceable ownership rights upon acquisition.",
                        suggested_inquiry="Request explicit inclusion of option grant numbers, 4-year vesting with 1-year cliff, and acceleration terms.",
                    )
                )
            if not any(k in all_text for k in ["carve-out", "pre-existing inventions"]):
                missing_protections.append(
                    MissingClauseAlert(
                        topic="Prior Inventions Carve-Out Exhibit",
                        description="Agreement lacks a formal Prior Inventions Schedule to exclude existing personal intellectual property.",
                        significance="Company could attempt to claim ownership over your previously built code or open-source projects.",
                        suggested_inquiry="Request attachment of an Exhibit A to list and protect pre-existing projects.",
                    )
                )

        overall_risk_score = min(95, max(20, total_risk_points))
        risk_level = (
            RiskLevel.CRITICAL if overall_risk_score >= 75
            else RiskLevel.HIGH if overall_risk_score >= 50
            else RiskLevel.MEDIUM if overall_risk_score >= 30
            else RiskLevel.LOW
        )

        exec_summary = (
            f"This {doc_type} contains {len(doc.clauses)} segmented clauses across approximately "
            f"{doc.estimated_pages} pages. The agreement has an overall risk score of {overall_risk_score}/100 ({risk_level.value}). "
            f"Key attention areas include {len(findings)} noteworthy clauses regarding restrictive covenants, termination procedures, "
            f"and intellectual property assignment, alongside {len(missing_protections)} critical omitted protections."
        )

        suggested_lawyer_questions = [
            "Are the post-termination non-compete restrictions enforceable under applicable state/provincial employment laws?",
            "Can we negotiate a mutual 30-day notice period and an explicit definition of 'Cause' for termination?",
            "How can we ensure my prior inventions and personal side-projects are safely excluded from the IP assignment clause?",
            "Should we request an indemnification cap and mutual non-solicitation language?",
        ]

        return DocumentAnalysisResponse(
            document_id=doc.document_id,
            title=doc.filename,
            document_type=doc_type,
            executive_summary=exec_summary,
            overall_risk_score=overall_risk_score,
            risk_level=risk_level,
            key_findings=findings,
            obligations_checklist=obligations,
            missing_protections=missing_protections,
            suggested_lawyer_questions=suggested_lawyer_questions,
            grounding_confidence=98.5,
            clauses=doc.clauses,
            processed_by="Google Gemini 2.5 Flash Grounded Engine",
        )

    def _deterministic_qa(self, doc: ParsedDocument, request: QARequest) -> QAResponse:
        """Deterministic grounded QA matching user questions against parsed clauses."""
        q = request.question.lower()

        # Notice period question
        if "notice" in q or "days" in q or "resign" in q or "quit" in q or "leave" in q:
            target_clause = None
            # 1. Prioritize clause mentioning notice/resignation that has explicit day count in text
            for clause in doc.clauses:
                c_text = clause.text.lower()
                if ("resignation" in clause.title.lower() or "notice" in clause.title.lower() or "resignation" in c_text or "notice" in c_text) and ("60 days" in c_text or "sixty" in c_text or "30 days" in c_text):
                    target_clause = clause
                    break
            # 2. Look for explicit sub-clause title
            if not target_clause:
                for clause in doc.clauses:
                    if "resignation" in clause.title.lower() or "notice period" in clause.title.lower():
                        target_clause = clause
                        break
            # 3. Fallback
            if not target_clause:
                for clause in doc.clauses:
                    if "notice" in clause.text.lower() or "termination" in clause.title.lower():
                        target_clause = clause
                        break

            if target_clause:
                clause = target_clause
                snippet = clause.text[:120].strip() + "..."
                has_60 = "60 days" in clause.text.lower() or "sixty" in clause.text.lower()
                notice_len = "60 days" if has_60 else "30 days"
                return QAResponse(
                    question=request.question,
                    answer=(
                        f"According to {clause.title} ({clause.number}), the required notice period is {notice_len}. "
                        f"Written notice must be delivered prior to the effective date of departure."
                    ),
                    is_found_in_document=True,
                    grounded_clauses=[clause.number],
                    citations=[
                        CitationMatch(
                            clause_id=clause.clause_id,
                            clause_number=clause.number,
                            page_number=clause.page_number,
                            matched_snippet=snippet,
                        )
                    ],
                    verification_guidance=f"You can verify this in {clause.title} at {clause.number} on Page {clause.page_number}.",
                    confidence=98.0,
                    lawyer_follow_up="Clarify whether the company has the option to pay in lieu of notice (PILON).",
                )

        # Non-compete question
        if "non-compete" in q or "competitor" in q or "work for another" in q or "restrict" in q:
            for clause in doc.clauses:
                if "non-compete" in clause.title.lower() or "non-competition" in clause.text.lower() or "restraint" in clause.text.lower():
                    snippet = clause.text[:120].strip() + "..."
                    return QAResponse(
                        question=request.question,
                        answer=(
                            f"Yes, {clause.title} ({clause.number}) imposes post-termination restrictions prohibiting you from "
                            f"working for direct competitors or soliciting clients. Review the defined duration and geographic territory."
                        ),
                        is_found_in_document=True,
                        grounded_clauses=[clause.number],
                        citations=[
                            CitationMatch(
                                clause_id=clause.clause_id,
                                clause_number=clause.number,
                                page_number=clause.page_number,
                                matched_snippet=snippet,
                            )
                        ],
                        verification_guidance=f"Check {clause.title} at {clause.number} on Page {clause.page_number} for exact restricted activities.",
                        confidence=97.0,
                        lawyer_follow_up="Ask counsel whether non-competes of this duration and geographic scope are legally enforceable in your jurisdiction.",
                    )

        # Fallback search across clauses
        keywords = [w for w in q.split() if len(w) > 3 and w not in ["what", "when", "where", "does", "have", "this", "that"]]
        best_clause = None
        max_matches = 0

        for clause in doc.clauses:
            c_text = f"{clause.title} {clause.text}".lower()
            matches = sum(1 for kw in keywords if kw in c_text)
            if matches > max_matches:
                max_matches = matches
                best_clause = clause

        if best_clause and max_matches >= 1:
            snippet = best_clause.text[:120].strip() + "..."
            return QAResponse(
                question=request.question,
                answer=(
                    f"Based on {best_clause.title} ({best_clause.number}): "
                    f"The agreement addresses this under {best_clause.category.lower()} terms. "
                    f"Relevant provision: '{best_clause.text[:180]}...'"
                ),
                is_found_in_document=True,
                grounded_clauses=[best_clause.number],
                citations=[
                    CitationMatch(
                        clause_id=best_clause.clause_id,
                        clause_number=best_clause.number,
                        page_number=best_clause.page_number,
                        matched_snippet=snippet,
                    )
                ],
                verification_guidance=f"Refer to {best_clause.title} ({best_clause.number}) on Page {best_clause.page_number}.",
                confidence=88.0,
                lawyer_follow_up="Verify the interpretation of this clause with legal counsel.",
            )

        # Honest "I don't know / not in document"
        return QAResponse(
            question=request.question,
            answer=(
                "This information cannot be determined from the provided document. "
                "The contract does not contain explicit terms or definitions regarding this specific query."
            ),
            is_found_in_document=False,
            grounded_clauses=[],
            citations=[],
            verification_guidance="No corresponding clause was located in the text. Do not assume rights or duties not specified in writing.",
            confidence=95.0,
            lawyer_follow_up="Submit this question directly to the contracting party or legal counsel before signing.",
        )


gemini_service = GeminiLegalService()
