"""Unit tests for Citation Engine and Grounding Verifier."""

from app.services.citation_engine import citation_engine


def test_resolve_clause(parsed_employment_doc):
    """Test resolving clause numbers to concrete Clause objects."""
    clause = citation_engine.resolve_clause("8.2", parsed_employment_doc)
    assert clause is not None
    assert "8.2" in clause.number
    assert "notice" in clause.text.lower()


def test_snippet_overlap_verification(parsed_employment_doc):
    """Test snippet textual overlap verification."""
    clause = citation_engine.resolve_clause("8.2", parsed_employment_doc)
    assert clause is not None

    exact_snippet = "provide sixty (60) calendar days prior written notice"
    score_exact = citation_engine.verify_snippet_in_clause(exact_snippet, clause)
    assert score_exact == 1.0

    unrelated_snippet = "quantum teleportation and dark matter bosons"
    score_unrelated = citation_engine.verify_snippet_in_clause(unrelated_snippet, clause)
    assert score_unrelated == 0.0


def test_match_citations_in_text(parsed_employment_doc):
    """Test extracting citation coordinates from text."""
    ai_text = "According to [Clause 8.2], you must provide notice. Furthermore, Clause 9.1 restricts competition."
    matches = citation_engine.match_citations(ai_text, parsed_employment_doc)

    assert len(matches) >= 2
    clause_nums = [m.clause_number for m in matches]
    assert any("8.2" in n for n in clause_nums)
    assert any("9.1" in n for n in clause_nums)


def test_topic_presence_and_absence(parsed_employment_doc):
    """
    Critical Test: Ensure topic presence checker detects existing topics
    and correctly flags missing topics (like stock options/equity).
    """
    # 1. Termination is present
    has_term, term_clauses = citation_engine.check_presence_of_topic(["termination", "notice"], parsed_employment_doc)
    assert has_term is True
    assert len(term_clauses) > 0

    # 2. Equity/stock option is completely absent from the agreement
    has_equity, equity_clauses = citation_engine.check_presence_of_topic(["stock option", "esop", "equity vesting"], parsed_employment_doc)
    assert has_equity is False
    assert len(equity_clauses) == 0
