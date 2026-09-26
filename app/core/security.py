"""Security utilities, validation, and sanitization for JurisLens AI."""

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


EXECUTABLE_MAGIC_HEADERS = [
    (b"MZ", "Windows PE executable"),
    (b"\x7fELF", "Linux ELF binary"),
    (b"\xca\xfe\xba\xbe", "Mach-O universal binary / Java bytecode"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit binary"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O binary"),
    (b"\xfe\xed\xfa\xcf", "Mach-O binary"),
    (b"\x00asm", "WebAssembly binary"),
]


def validate_file_upload(filename: str, file_bytes: bytes) -> Tuple[bool, str]:
    """
    Validates file extension, byte length, and file signatures (magic bytes).
    Prevents path traversal, executable masquerading, and DoS payloads.
    """
    if not filename:
        return False, "Filename cannot be empty."

    # Prevent path traversal and hidden files
    if ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
        return False, "Invalid filename detected."

    lower_name = filename.lower().strip()
    if lower_name.startswith("."):
        return False, "Hidden files are not permitted."

    if not any(lower_name.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        return False, f"Unsupported file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"

    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        return False, f"File exceeds maximum allowed size of {max_mb} MB."

    # Detect and block executable binaries masquerading under allowed extensions
    for magic_prefix, description in EXECUTABLE_MAGIC_HEADERS:
        if file_bytes.startswith(magic_prefix):
            return False, f"Dangerous executable header detected ({description}). Upload rejected."

    # Type-specific deep validation
    if lower_name.endswith((".txt", ".md", ".rtf")):
        # Pure text formats must not contain binary null bytes (common payload injection vector)
        if b"\x00" in file_bytes:
            return False, "Corrupt or binary content detected in text file."

    elif lower_name.endswith(".pdf"):
        # Standard PDF files must contain the %PDF- magic signature within the first 1024 bytes
        if b"%PDF-" not in file_bytes[:1024]:
            return False, "Invalid PDF structure: missing standard PDF header."

    elif lower_name.endswith(".docx"):
        # DOCX files are zipped XML archives and must begin with the PK zip header
        if not file_bytes.startswith(b"PK\x03\x04"):
            return False, "Invalid DOCX structure: missing standard archive header."

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
    Thread-safe in-memory IP rate limiter with bounded capacity (CWE-400 safe).
    Periodically purges inactive clients and evicts when max capacity is reached.
    """

    def __init__(self, requests_per_minute: int = 120, max_tracked_ips: int = 2048):
        self.rpm = requests_per_minute
        self.max_tracked_ips = max_tracked_ips
        self.clients: Dict[str, list] = {}
        import threading
        self._lock = threading.Lock()

    def check(self, client_ip: str) -> bool:
        with self._lock:
            now = time.time()
            minute_ago = now - 60

            # Prune current client timestamps
            timestamps = self.clients.get(client_ip, [])
            timestamps = [t for t in timestamps if t > minute_ago]

            if len(timestamps) >= self.rpm:
                self.clients[client_ip] = timestamps
                return False

            # Memory bound check: prune dormant IPs if table is getting full
            if len(self.clients) >= self.max_tracked_ips:
                stale_ips = [ip for ip, ts in self.clients.items() if not ts or ts[-1] <= minute_ago]
                for ip in stale_ips:
                    del self.clients[ip]

                # If still over capacity, evict oldest entry
                if len(self.clients) >= self.max_tracked_ips:
                    oldest_ip = min(self.clients.keys(), key=lambda k: self.clients[k][-1] if self.clients[k] else 0)
                    del self.clients[oldest_ip]

            timestamps.append(now)
            self.clients[client_ip] = timestamps
            return True

    def reset(self) -> None:
        """Reset rate limiter state (useful for test isolation)."""
        with self._lock:
            self.clients.clear()


rate_limiter = SimpleRateLimiter()
