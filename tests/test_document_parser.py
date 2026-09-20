"""Unit tests for the Document Parser and Clause Segmenter."""

from app.services.document_parser import document_parser


def test_parse_sample_employment_clauses(sample_employment_text):
    """Verify document parser extracts numbered clauses from the sample contract."""
    doc = document_parser.parse_text(sample_employment_text, filename="employment.txt")

    assert doc.document_id is not None
    assert doc.total_clauses >= 10
    assert doc.estimated_pages >= 1

    clause_numbers = [c.number for c in doc.clauses]
    # Check that key clauses are segmented
    assert "8.2" in clause_numbers or any("8.2" in n for n in clause_numbers)
    assert "9.1" in clause_numbers or any("9.1" in n for n in clause_numbers)
    assert "3.1" in clause_numbers or any("3.1" in n for n in clause_numbers)


def test_category_inference():
    """Test category classifier correctly identifies legal topics."""
    cat_termination = document_parser.infer_category("Termination", "Either party may terminate on 60 days notice.")
    assert cat_termination == "Termination"

    cat_ip = document_parser.infer_category("Work Product", "All intellectual property and patents are assigned.")
    assert cat_ip == "Intellectual Property"

    cat_covenant = document_parser.infer_category("Non-Competition", "Shall not engage in a competing business.")
    assert cat_covenant == "Restrictive Covenants"


def test_empty_and_minimal_text_parsing():
    """Verify parser handles minimal single-paragraph input cleanly."""
    single_p = "This is a simple one-sentence contract with no numbered sections."
    doc = document_parser.parse_text(single_p, filename="short.txt")

    assert doc.total_clauses == 1
    assert doc.clauses[0].number == "1"
    assert doc.clauses[0].text == single_p


def test_document_cache_retrieval(sample_employment_text):
    """Test retrieving parsed document by ID from in-memory cache."""
    doc = document_parser.parse_text(sample_employment_text, filename="cached_doc.txt")
    retrieved = document_parser.get_document(doc.document_id)

    assert retrieved is not None
    assert retrieved.document_id == doc.document_id
    assert retrieved.total_clauses == doc.total_clauses
