"""Document Ingestion and Clause Boundary Segmentation Service."""

import re
import uuid
from typing import Dict, List, Optional
from app.models.schemas import Clause, ParsedDocument

# In-memory document storage for session-based fast retrieval
DOCUMENTS_CACHE: Dict[str, ParsedDocument] = {}


class DocumentParser:
    """Intelligent legal document parser and structural clause segmenter."""

    CLAUSE_PATTERNS = [
        # Match "Section 1", "Article 2", "Clause 8.2"
        re.compile(r"^(?:Section|Article|Clause)\s+([0-9A-Za-z\.]+)[.:\s-]*(.*)$", re.IGNORECASE),
        # Match numbered outlines: "1.", "1.1", "8.2.1"
        re.compile(r"^([0-9]+\.[0-9]*(?:\.[0-9]+)*)[.:\s-]*(.*)$"),
        # Match standard numbered paragraphs: "1. ", "2. "
        re.compile(r"^([0-9]+)\.\s+([A-Z0-9].*)$"),
        # Match Roman numerals: "I. ", "IV. "
        re.compile(r"^([IVXLCDM]+)\.\s+(.*)$", re.IGNORECASE),
    ]

    CATEGORY_KEYWORDS = {
        "Termination": ["terminate", "termination", "notice period", "severance", "dismissal", "resignation"],
        "Compensation": ["salary", "compensation", "bonus", "equity", "stock", "shares", "benefits", "payment"],
        "Restrictive Covenants": ["non-compete", "non-competition", "compete", "competition", "non-solicitation", "non-disclosure", "restraint", "exclusive"],
        "Intellectual Property": ["intellectual property", "inventions", "patents", "copyright", "proprietary", "assignment"],
        "Confidentiality": ["confidential", "secrecy", "proprietary information", "trade secret"],
        "Liability & Indemnity": ["indemnify", "indemnification", "hold harmless", "limitation of liability", "damages"],
        "Dispute Resolution": ["governing law", "jurisdiction", "arbitration", "mediation", "venue"],
        "Duties & Scope": ["duties", "responsibilities", "role", "reporting", "services", "scope of work"],
        "Obligations": ["obligations", "compliance", "policies", "code of conduct"],
    }

    @classmethod
    def infer_category(cls, title: str, text: str) -> str:
        """Determines the legal category based on content keywords."""
        combined = f"{title} {text}".lower()
        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return category
        return "General Terms"

    @classmethod
    def parse_text(cls, raw_text: str, filename: str = "document.txt") -> ParsedDocument:
        """
        Parses raw text into discrete, numbered, navigable legal clauses.
        Estimates pages and lines for real-time split-screen synchronization.
        """
        lines = raw_text.splitlines()
        clauses: List[Clause] = []

        current_number = "Preamble"
        current_title = "Preamble & Recitals"
        current_lines: List[str] = []
        clause_start_line = 1
        clause_index = 0

        lines_per_page = 45  # Standard legal page density

        def flush_clause(end_line: int):
            nonlocal clause_index, current_lines
            text_body = "\n".join(current_lines).strip()
            if text_body:
                clause_index += 1
                clause_id = f"clause_{clause_index}"
                category = cls.infer_category(current_title, text_body)
                page_num = max(1, (clause_start_line // lines_per_page) + 1)

                clauses.append(
                    Clause(
                        clause_id=clause_id,
                        number=current_number,
                        title=current_title or f"Clause {current_number}",
                        text=text_body,
                        page_number=page_num,
                        line_start=clause_start_line,
                        line_end=end_line,
                        category=category,
                    )
                )
            current_lines = []

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                current_lines.append("")
                continue

            # Check if this line marks the beginning of a new clause
            matched = False
            for pattern in cls.CLAUSE_PATTERNS:
                m = pattern.match(stripped)
                if m:
                    # Flush previous clause
                    flush_clause(idx - 1)
                    current_number = m.group(1).strip()
                    raw_title = m.group(2).strip() if len(m.groups()) >= 2 else ""
                    if raw_title:
                        first_phrase = raw_title.split(".")[0].strip()
                        if len(first_phrase) >= 3 and len(first_phrase) <= 50:
                            current_title = first_phrase
                        elif len(raw_title) > 50:
                            current_title = raw_title[:47] + "..."
                        else:
                            current_title = raw_title
                    else:
                        current_title = f"Clause {current_number}"
                    clause_start_line = idx
                    current_lines.append(stripped)
                    matched = True
                    break

            # Also check for uppercase headings (e.g., "12. GOVERNING LAW")
            if not matched:
                if (stripped.isupper() and len(stripped) < 80 and not stripped.endswith(".")) or (
                    stripped.startswith("#")
                ):
                    flush_clause(idx - 1)
                    clause_start_line = idx
                    current_number = f"Sec-{clause_index + 1}"
                    current_title = stripped.lstrip("#").strip()
                    current_lines.append(stripped)
                    matched = True

            if not matched:
                current_lines.append(line)

        # Flush final clause
        flush_clause(len(lines))

        # If only a single preamble clause exists without other clauses, treat it as Section 1
        if len(clauses) == 1 and clauses[0].number == "Preamble":
            clauses[0].number = "1"
            clauses[0].title = "Section 1"

        # Fallback if no specific clauses were segmented (e.g. single block text)
        if not clauses and raw_text.strip():
            paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
            for p_idx, p in enumerate(paragraphs, start=1):
                clauses.append(
                    Clause(
                        clause_id=f"clause_{p_idx}",
                        number=str(p_idx),
                        title=f"Section {p_idx}",
                        text=p,
                        page_number=1,
                        line_start=1,
                        line_end=len(p.splitlines()),
                        category=cls.infer_category(f"Section {p_idx}", p),
                    )
                )

        doc_id = str(uuid.uuid4())
        estimated_pages = max(1, (len(lines) // lines_per_page) + 1)

        parsed = ParsedDocument(
            document_id=doc_id,
            filename=filename,
            total_clauses=len(clauses),
            estimated_pages=estimated_pages,
            raw_text=raw_text,
            clauses=clauses,
        )

        DOCUMENTS_CACHE[doc_id] = parsed
        return parsed

    @classmethod
    def get_document(cls, document_id: str) -> Optional[ParsedDocument]:
        """Retrieves an ingested document from cache."""
        return DOCUMENTS_CACHE.get(document_id)

    @classmethod
    def save_document(cls, doc: ParsedDocument) -> None:
        """Caches a parsed document."""
        DOCUMENTS_CACHE[doc.document_id] = doc


document_parser = DocumentParser()
