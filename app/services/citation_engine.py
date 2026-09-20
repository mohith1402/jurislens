"""Verification and Grounding Citation Engine for JurisLens AI."""

import re
from typing import Dict, List, Optional, Tuple
from app.models.schemas import Clause, ParsedDocument, CitationMatch


class CitationEngine:
    """Verifies citations, detects hallucinations, and anchors AI findings to source text."""

    @classmethod
    def resolve_clause(cls, citation_str: str, doc: ParsedDocument) -> Optional[Clause]:
        """
        Resolves references like '8.2', 'Clause 8.2', 'Section 4' to a concrete Clause object.
        """
        cleaned = re.sub(r"^(?:Clause|Section|Article|Sec|Art)\s*", "", citation_str.strip(), flags=re.IGNORECASE)
        cleaned = cleaned.rstrip(".:;")

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

        # Exact substring match
        if snippet.lower() in clause.text.lower():
            return 1.0

        # Word-level overlap score (excluding common stop words for legal precision)
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "as", "is", "was", "are", "were", "be", "been"}
        snippet_words = {w for w in re.findall(r"\w+", snippet.lower()) if w not in stop_words}
        clause_words = {w for w in re.findall(r"\w+", clause.text.lower()) if w not in stop_words}

        if not snippet_words:
            return 0.0

        overlap = snippet_words.intersection(clause_words)
        return len(overlap) / len(snippet_words)

    @classmethod
    def match_citations(cls, text: str, doc: ParsedDocument) -> List[CitationMatch]:
        """
        Extracts all clause references embedded in text and attaches exact verification matches.
        """
        matches: List[CitationMatch] = []
        found_ids = set()

        # Find patterns like [Clause 8.2], (Section 5), Clause 3.1
        patterns = [
            re.compile(r"\[(?:Clause|Section)\s+([0-9A-Za-z\.]+)\]", re.IGNORECASE),
            re.compile(r"\b(?:Clause|Section|Article)\s+([0-9A-Za-z\.]+)\b", re.IGNORECASE),
            re.compile(r"\bclause_([0-9]+)\b", re.IGNORECASE),
        ]

        for pattern in patterns:
            for m in pattern.finditer(text):
                num_str = m.group(1)
                clause = cls.resolve_clause(num_str, doc)
                if clause and clause.clause_id not in found_ids:
                    found_ids.add(clause.clause_id)
                    # Extract a representative 100-character snippet
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
