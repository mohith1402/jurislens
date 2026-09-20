"""Integration tests for FastAPI REST Endpoints."""

import io


def test_api_health(client):
    """Test health check endpoint."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "JurisLens AI"
    assert data["gemini_model"] == "gemini-2.5-flash"


def test_api_samples(client):
    """Test retrieval of pre-packaged sample contracts."""
    res = client.get("/api/samples")
    assert res.status_code == 200
    data = res.json()
    assert "samples" in data
    assert len(data["samples"]) >= 2
    sample_ids = [s["id"] for s in data["samples"]]
    assert "sample_employment" in sample_ids


def test_api_analyze_text(client, sample_employment_text):
    """Test analyzing contract text via API."""
    res = client.post(
        "/api/analyze-text",
        json={"text": sample_employment_text, "title": "API Test Employment Contract"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "API Test Employment Contract"
    assert data["overall_risk_score"] > 0
    assert len(data["clauses"]) >= 5
    assert len(data["key_findings"]) >= 1

    doc_id = data["document_id"]

    # Test retrieval of document clauses by ID
    doc_res = client.get(f"/api/document/{doc_id}")
    assert doc_res.status_code == 200
    assert doc_res.json()["document_id"] == doc_id


def test_api_analyze_text_validation_failure(client):
    """Test short/empty text rejection."""
    res = client.post("/api/analyze-text", json={"text": "Too short", "title": "Bad"})
    assert res.status_code == 400


def test_api_file_upload(client, sample_standard_nda_text):
    """Test file upload endpoint with a .txt contract."""
    file_bytes = io.BytesIO(sample_standard_nda_text.encode("utf-8"))
    res = client.post(
        "/api/upload",
        files={"file": ("nda_test.txt", file_bytes, "text/plain")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "document_id" in data
    assert len(data["clauses"]) >= 2


def test_api_qa_flow(client, sample_employment_text):
    """Test grounded QA endpoint."""
    # First ingest document
    ingest_res = client.post(
        "/api/analyze-text",
        json={"text": sample_employment_text, "title": "QA Test Doc"},
    )
    doc_id = ingest_res.json()["document_id"]

    # Ask grounded notice question
    qa_res = client.post(
        "/api/qa",
        json={
            "document_id": doc_id,
            "question": "What is the notice period for resigning?",
            "user_role": "employee",
        },
    )
    assert qa_res.status_code == 200
    qa_data = qa_res.json()
    assert qa_data["is_found_in_document"] is True
    assert "60 days" in qa_data["answer"].lower()

    # Ask missing question (stock options)
    qa_missing = client.post(
        "/api/qa",
        json={
            "document_id": doc_id,
            "question": "What happens to my stock options if I resign?",
            "user_role": "employee",
        },
    )
    assert qa_missing.status_code == 200
    missing_data = qa_missing.json()
    assert missing_data["is_found_in_document"] is False


def test_api_compare_contracts(client, sample_standard_nda_text, sample_aggressive_nda_text):
    """Test comparison endpoint."""
    res = client.post(
        "/api/compare",
        json={
            "doc1_text": sample_standard_nda_text,
            "doc2_text": sample_aggressive_nda_text,
            "doc1_name": "Standard Mutual",
            "doc2_name": "Aggressive Vendor",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["differences"]) >= 2
    assert "verdict" in data


def test_api_lawyer_brief(client, sample_employment_text):
    """Test generating lawyer consultation briefing packet."""
    ingest_res = client.post(
        "/api/analyze-text",
        json={"text": sample_employment_text, "title": "Consultation Doc"},
    )
    doc_id = ingest_res.json()["document_id"]

    res = client.post(
        "/api/lawyer-brief",
        json={"document_id": doc_id, "user_notes": "Want to negotiate non-compete"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "top_risks_for_review" in data
    assert "critical_omissions" in data
    assert "prepared_questions_for_counsel" in data
    assert "formatted_markdown" in data
