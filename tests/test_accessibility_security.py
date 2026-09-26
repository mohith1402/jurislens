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
    """Verify path traversal, executable masquerading, and null bytes are blocked."""
    # 1. Path traversal attack
    valid, err = validate_file_upload("../../etc/passwd", b"malicious content")
    assert valid is False
    assert "Invalid filename" in err

    # 2. Executable extension
    valid, err = validate_file_upload("exploit.exe", b"binary content")
    assert valid is False
    assert "Unsupported file type" in err

    # 3. Executable masquerading (PE / Windows binary disguised as .txt)
    valid, err = validate_file_upload("contract.txt", b"MZ\x90\x00\x03\x00\x00\x00fake pe executable")
    assert valid is False
    assert "Dangerous executable header" in err

    # 4. Executable masquerading (Linux ELF binary disguised as .txt)
    valid, err = validate_file_upload("contract.txt", b"\x7fELF\x02\x01\x01\x00fake elf")
    assert valid is False
    assert "Dangerous executable header" in err

    # 5. Hidden files
    valid, err = validate_file_upload(".hidden_contract.txt", b"some text")
    assert valid is False
    assert "Hidden files" in err

    # 6. Null byte injection in text file
    valid, err = validate_file_upload("contract.txt", b"Clause 1 text\x00injected null byte")
    assert valid is False
    assert "binary content" in err

    # 7. Legitimate text file
    valid, err = validate_file_upload("agreement.txt", b"Safe contract text")
    assert valid is True


def test_rate_limiter_memory_bounds_and_pruning():
    """Verify SimpleRateLimiter enforces RPM, bounded memory table, and pruning."""
    from app.core.security import SimpleRateLimiter

    limiter = SimpleRateLimiter(requests_per_minute=2, max_tracked_ips=3)
    assert limiter.check("10.0.0.1") is True
    assert limiter.check("10.0.0.1") is True
    # 3rd request from same IP within window is rate-limited
    assert limiter.check("10.0.0.1") is False

    # Capacity capping: adding multiple new client IPs stays within max_tracked_ips
    limiter.check("10.0.0.2")
    limiter.check("10.0.0.3")
    limiter.check("10.0.0.4")
    assert len(limiter.clients) <= 3


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


def test_cors_explicit_headers_no_wildcard():
    """Verify CORS uses an explicit allowed header array without wildcard *."""
    from app.main import ALLOWED_CORS_HEADERS

    assert "*" not in ALLOWED_CORS_HEADERS
    assert "Authorization" in ALLOWED_CORS_HEADERS
    assert "Upgrade" in ALLOWED_CORS_HEADERS
    assert "Sec-WebSocket-Key" in ALLOWED_CORS_HEADERS
    assert "Content-Type" in ALLOWED_CORS_HEADERS
