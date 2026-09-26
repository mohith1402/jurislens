"""Pytest fixtures and configuration."""

import os
import pytest
from fastapi.testclient import TestClient

# Ensure test environment mode is active before loading app modules
os.environ["ENVIRONMENT"] = "test"

from app.main import app  # noqa: E402
from app.models.schemas import ParsedDocument  # noqa: E402
from app.services.document_parser import document_parser  # noqa: E402


@pytest.fixture
def client():
    """FastAPI Test Client."""
    return TestClient(app)


@pytest.fixture
def sample_employment_text():
    """Returns the sample employment agreement text."""
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "sample_documents",
        "employment_agreement_sample.txt",
    )
    with open(sample_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_standard_nda_text():
    """Returns the sample standard mutual NDA text."""
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "sample_documents",
        "nda_standard_mutual.txt",
    )
    with open(sample_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_aggressive_nda_text():
    """Returns the sample aggressive vendor NDA text."""
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "sample_documents",
        "nda_aggressive_vendor.txt",
    )
    with open(sample_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def parsed_employment_doc(sample_employment_text) -> ParsedDocument:
    """Pre-parsed employment document fixture."""
    return document_parser.parse_text(sample_employment_text, filename="test_employment.txt")
