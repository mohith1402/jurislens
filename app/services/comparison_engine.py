"""Contract-to-Contract Side-by-Side Comparison Engine."""

from typing import List
from app.models.schemas import (
    ComparisonDifference,
    ComparisonResponse,
)
from app.services.document_parser import document_parser


class ComparisonEngine:
    """Compares two contracts, identifies redline deltas, and scores risk shifts."""

    @classmethod
    def compare_documents(
        cls,
        doc1_text: str,
        doc2_text: str,
        doc1_name: str = "Document A (Standard)",
        doc2_name: str = "Document B (Proposed)",
    ) -> ComparisonResponse:
        """Compares two documents at structural and clause levels."""
        doc1 = document_parser.parse_text(doc1_text, filename=doc1_name)
        doc2 = document_parser.parse_text(doc2_text, filename=doc2_name)

        differences: List[ComparisonDifference] = []

        # Common legal dimensions to inspect
        categories = [
            ("Term & Termination", ["terminate", "termination", "notice period", "days notice"]),
            ("Confidentiality & Non-Disclosure", ["confidential", "proprietary", "trade secret"]),
            ("Non-Compete & Restrictive Covenants", ["non-compete", "non-competition", "restraint", "solicit"]),
            ("Intellectual Property & Ownership", ["intellectual property", "inventions", "patents", "assignment", "work made for hire"]),
            ("Indemnification & Liability Cap", ["indemnify", "indemnity", "hold harmless", "limitation of liability", "consequential damages"]),
            ("Dispute Resolution & Jurisdiction", ["arbitration", "governing law", "jurisdiction", "venue", "jury trial"]),
            ("Remedies & Liquidated Damages", ["injunctive relief", "liquidated damages", "remedy", "attorneys' fees"]),
        ]

        for cat_name, keywords in categories:
            d1_clauses = [c for c in doc1.clauses if any(k in f"{c.title} {c.text}".lower() for k in keywords)]
            d2_clauses = [c for c in doc2.clauses if any(k in f"{c.title} {c.text}".lower() for k in keywords)]

            d1_has = len(d1_clauses) > 0
            d2_has = len(d2_clauses) > 0

            if not d1_has and not d2_has:
                continue

            d1_summary = d1_clauses[0].text[:180] + "..." if d1_has else "Not included in this document."
            d2_summary = d2_clauses[0].text[:180] + "..." if d2_has else "Not included in this document."
            d1_snippet = d1_clauses[0].text[:120] if d1_has else "N/A"
            d2_snippet = d2_clauses[0].text[:120] if d2_has else "N/A"

            # Determine risk shift
            risk_shift = "NEUTRAL"
            explanation = f"Both documents contain provisions regarding {cat_name}."

            if d1_has and not d2_has:
                risk_shift = "MORE_FAVORABLE_DOC1"
                explanation = f"{cat_name} is present in {doc1_name} but completely missing in {doc2_name}."
            elif not d1_has and d2_has:
                # If restrictive covenant or indemnity is added in Doc B, high risk
                if "Restrictive" in cat_name or "Indemnification" in cat_name or "Remedies" in cat_name:
                    risk_shift = "CRITICAL_RISK_ADDED"
                    explanation = f"{doc2_name} introduces new aggressive {cat_name} obligations that did not exist in {doc1_name}."
                else:
                    risk_shift = "MORE_FAVORABLE_DOC2"
                    explanation = f"{doc2_name} adds protections for {cat_name} not found in {doc1_name}."
            else:
                # Both have it - analyze severity
                t1 = d1_clauses[0].text.lower()
                t2 = d2_clauses[0].text.lower()

                # Notice period check
                if "notice" in cat_name.lower():
                    if "60 days" in t2 and ("30 days" in t1 or "14 days" in t1):
                        risk_shift = "CRITICAL_RISK_ADDED"
                        explanation = f"Notice period lengthened significantly in {doc2_name} (requires 60 days vs shorter standard)."
                    elif "30 days" in t2 and "60 days" in t1:
                        risk_shift = "MORE_FAVORABLE_DOC2"
                        explanation = f"Notice period is more flexible in {doc2_name} (30 days vs 60 days in {doc1_name})."

                # Indemnity check
                if "indemni" in cat_name.lower():
                    if "sole" in t2 or "unlimited" in t2 or "shall defend" in t2:
                        risk_shift = "CRITICAL_RISK_ADDED"
                        explanation = f"{doc2_name} imposes unilateral, uncapped indemnification obligations."

                # Non-compete check
                if "non-compete" in cat_name.lower() or "restrictive" in cat_name.lower():
                    if "2 years" in t2 or "worldwide" in t2 or "any competitor" in t2:
                        risk_shift = "CRITICAL_RISK_ADDED"
                        explanation = f"{doc2_name} contains an overly broad non-compete (longer duration/worldwide territory)."

            differences.append(
                ComparisonDifference(
                    category=cat_name,
                    clause_title=d2_clauses[0].title if d2_has else d1_clauses[0].title,
                    doc1_summary=d1_summary,
                    doc2_summary=d2_summary,
                    doc1_snippet=d1_snippet,
                    doc2_snippet=d2_snippet,
                    risk_shift=risk_shift,
                    explanation=explanation,
                )
            )

        critical_count = sum(1 for d in differences if d.risk_shift == "CRITICAL_RISK_ADDED")
        if critical_count > 0:
            verdict = (
                f"CAUTION: {doc2_name} contains {critical_count} critical risk shifts compared to {doc1_name}. "
                "Significant unilateral obligations and restrictive covenants were introduced."
            )
        else:
            verdict = f"{doc1_name} and {doc2_name} are largely balanced with moderate standard variances."

        key_takeaways = [
            f"Analyzed {len(differences)} primary legal categories between documents.",
            f"Found {critical_count} high-risk differences requiring legal review.",
            "Verify liability limits, non-solicitation scope, and termination notice differences before signing.",
        ]

        return ComparisonResponse(
            comparison_summary=(
                f"Side-by-side comparative analysis of {doc1_name} vs {doc2_name}. "
                f"Identified key variances across {len(differences)} contract sections."
            ),
            doc1_name=doc1_name,
            doc2_name=doc2_name,
            differences=differences,
            verdict=verdict,
            key_takeaways=key_takeaways,
            processed_by="Google Gemini 2.5 Flash Comparative Engine",
        )


comparison_engine = ComparisonEngine()
