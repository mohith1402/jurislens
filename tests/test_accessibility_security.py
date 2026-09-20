"""Tests for Security Headers, Input Sanitization, and WCAG Accessibility."""

import os
from app.core.security import sanitize_text_input, validate_file_upload


def test_security_headers_present(client):
    """Verify OWASP-recommended security headers are returned on all responses."""
    res = client.get("/api/health")
    headers = res.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers


def test_sanitize_text_strips_scripts():
    """Verify input sanitization removes hazardous script injection vectors."""
    dirty_input = "Contract Clause 1 <script>alert('pwned')</script> and normal terms."
    sanitized = sanitize_text_input(dirty_input)
    assert "<script>" not in sanitized
    assert "alert('pwned')" not in sanitized
    assert "Contract Clause 1" in sanitized
    assert "normal terms" in sanitized


def test_validate_file_upload_security():
    """Verify path traversal and disallowed extensions are blocked."""
    # 1. Path traversal attack
    valid, err = validate_file_upload("../../etc/passwd", b"malicious content")
    assert valid is False
    assert "Invalid filename" in err

    # 2. Executable payload
    valid, err = validate_file_upload("exploit.exe", b"binary content")
    assert valid is False
    assert "Unsupported file type" in err

    # 3. Legitimate text file
    valid, err = validate_file_upload("agreement.txt", b"Safe contract text")
    assert valid is True


def test_html_accessibility_elements():
    """Verify index.html contains essential WCAG 2.1 AA accessibility structures."""
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "index.html")
    assert os.path.exists(index_path)

    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 1. Skip Link for keyboard navigation
    assert 'class="skip-link"' in html_content
    assert 'href="#main-content"' in html_content

    # 2. Semantic landmarks
    assert "<header" in html_content and 'role="banner"' in html_content
    assert "<main" in html_content and 'role="main"' in html_content
    assert "<footer" in html_content and 'role="contentinfo"' in html_content

    # 3. Screen reader live region
    assert 'aria-live="polite"' in html_content

    # 4. Accessible theme toggle and modals
    assert 'aria-label=' in html_content
    assert 'role="dialog"' in html_content
    assert 'aria-modal="true"' in html_content
