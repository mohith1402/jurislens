"""Security utilities, validation, and sanitization for JurisLens AI."""

import html
import re
import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings


def sanitize_text_input(text: str, max_length: int = 500000) -> str:
    """
    Sanitizes raw text input to prevent injection attacks and memory exhaustion.
    Preserves legal formatting, line breaks, and quotation symbols.
    """
    if not text:
        return ""

    if len(text) > max_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Input text exceeds maximum allowed limit of {max_length} characters.",
        )

    # Remove null bytes and hazardous control characters (preserving \n, \r, \t)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Clean HTML script tags or event handlers if any exist in text
    cleaned = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<\s*(?:iframe|object|embed|applet)[^>]*>.*?<\s*/\s*(?:iframe|object|embed|applet)\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"on\w+\s*=\s*['\"][^'\"]*['\"]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:javascript|vbscript|data):", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<!--#.*?-->", "", cleaned)  # Block Server-Side Include directives

    return cleaned.strip()


def validate_file_upload(filename: str, file_bytes: bytes) -> Tuple[bool, str]:
    """
    Validates file extension and byte length.
    Ensures zero arbitrary execution or path traversal vulnerabilities.
    """
    if not filename:
        return False, "Filename cannot be empty."

    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return False, "Invalid filename detected."

    lower_name = filename.lower()
    if not any(lower_name.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        return False, f"Unsupported file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"

    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        return False, f"File exceeds maximum allowed size of {max_mb} MB."

    return True, "Valid"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying strict OWASP-recommended security headers
    including CSP, HSTS, X-Content-Type-Options, and X-Frame-Options.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Standard OWASP Top 10 Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Content Security Policy (hardened with object-src, base-uri, form-action, and frame-ancestors)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )

        return response


class SimpleRateLimiter:
    """
    Lightweight in-memory IP rate limiter for API protection.
    """

    def __init__(self, requests_per_minute: int = 120):
        self.rpm = requests_per_minute
        self.clients: Dict[str, list] = {}

    def check(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60

        # Purge old records
        timestamps = self.clients.get(client_ip, [])
        timestamps = [t for t in timestamps if t > minute_ago]

        if len(timestamps) >= self.rpm:
            return False

        timestamps.append(now)
        self.clients[client_ip] = timestamps
        return True


rate_limiter = SimpleRateLimiter()
