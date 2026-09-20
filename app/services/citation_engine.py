"""Verification and Grounding Citation Engine for JurisLens AI."""

import re
from typing import Dict, List, Optional, Tuple
from app.models.schemas import Clause, ParsedDocument, CitationMatch


class CitationEngine:
    """Verifies citations, detects hallucinations, and anchors AI findings to source text."""

    # Pre-compiled static regex patterns (avoids runtime compilation overhead)
    CITATION_PATTERNS = [
        re.compile(r"\[(?:Clause|Section)\s+([0-9A-Za-z\.]+)\]", re.IGNORECASE),
        re.compile(r"\b(?:Clause|Section|Article)\s+([0-9A-Za-z\.]+)\b", re.IGNORECASE),
        re.compile(r"\bclause_([0-9]+)\b", re.IGNORECASE),
    ]
    CLEAN_PREFIX_PATTERN = re.compile(r"^(?:Clause|Section|Article|Sec|Art)\s*", re.IGNORECASE)
    WORD_PATTERN = re.compile(r"\w+")
    STOP_WORDS = frozenset({"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "as", "is", "was", "are", "were", "be", "been"})

    @classmethod
    def resolve_clause(cls, citation_str: str, doc: ParsedDocument) -> Optional[Clause]:
        """
        Resolves references like '8.2', 'Clause 8.2', 'Section 4' to a concrete Clause object.
        Leverages pre-computed O(1) lookup table when available for sub-microsecond resolution.
        """
        raw_clean = citation_str.strip().rstrip(".:;")
        lower_clean = raw_clean.lower()

        # 1. Fast O(1) index lookup
        lookup = getattr(doc, "_lookup", None)
        if lookup:
            if lower_clean in lookup:
                return lookup[lower_clean]
            num_only = cls.CLEAN_PREFIX_PATTERN.sub("", lower_clean)
            if num_only in lookup:
                return lookup[num_only]

        # 2. Linear scan fallback
        cleaned = cls.CLEAN_PREFIX_PATTERN.sub("", raw_clean).rstrip(".:;")

        # Direct match on number
        for clause in doc.clauses:
            if clause.number.lower() == cleaned.lower() or clause.clause_id.lower() == citation_str.lower():
                return clause

        # Partial match on clause number prefix or title
        for clause in doc.clauses:
            if cleaned.lower() in clause.number.lower() or cleaned.lower() in clause.title.lower():
                return clause

        return None

    @classmethod
    def verify_snippet_in_clause(cls, snippet: str, clause: Clause) -> float:
        """
        Measures the textual overlap between an AI-provided citation snippet and the clause text.
        Returns a grounding ratio between 0.0 and 1.0.
        """
        if not snippet or not clause.text:
            return 0.0

        # Exact substring match (fastest path)
        snippet_lower = snippet.lower()
        clause_lower = clause.text.lower()
        if snippet_lower in clause_lower:
            return 1.0

        # Word-level overlap score (excluding common stop words for legal precision)
        snippet_words = {w for w in cls.WORD_PATTERN.findall(snippet_lower) if w not in cls.STOP_WORDS}
        if not snippet_words:
            return 0.0

        clause_words = {w for w in cls.WORD_PATTERN.findall(clause_lower) if w not in cls.STOP_WORDS}
        overlap = snippet_words.intersection(clause_words)
        return len(overlap) / len(snippet_words)

    @classmethod
    def match_citations(cls, text: str, doc: ParsedDocument) -> List[CitationMatch]:
        """
        Extracts all clause references embedded in text and attaches exact verification matches.
        """
        matches: List[CitationMatch] = []
        found_ids = set()

        for pattern in cls.CITATION_PATTERNS:
            for m in pattern.finditer(text):
                num_str = m.group(1)
                clause = cls.resolve_clause(num_str, doc)
                if clause and clause.clause_id not in found_ids:
                    found_ids.add(clause.clause_id)
                    # Extract a representative snippet
                    preview = clause.text[:120].strip() + ("..." if len(clause.text) > 120 else "")
                    matches.append(
                        CitationMatch(
                            clause_id=clause.clause_id,
                            clause_number=clause.number,
                            page_number=clause.page_number,
                            matched_snippet=preview,
                        )
                    )

        return matches

    @classmethod
    def calculate_grounding_score(cls, citations_count: int, total_findings: int) -> float:
        """Calculates verification confidence based on citation density."""
        if total_findings == 0:
            return 100.0
        ratio = min(1.0, citations_count / max(1, total_findings))
        return round(ratio * 100, 1)

    @classmethod
    def check_presence_of_topic(cls, topic_keywords: List[str], doc: ParsedDocument) -> Tuple[bool, List[Clause]]:
        """
        Checks if a given topic exists in the document text.
        Returns (is_present, relevant_clauses).
        """
        found_clauses = []
        for clause in doc.clauses:
            clause_content = f"{clause.title} {clause.text}".lower()
            if any(kw.lower() in clause_content for kw in topic_keywords):
                found_clauses.append(clause)

        return (len(found_clauses) > 0, found_clauses)


citation_engine = CitationEngine()
