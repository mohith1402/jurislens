"""Main FastAPI Application Entrypoint for JurisLens AI."""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.security import SecurityHeadersMiddleware, rate_limiter

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "JurisLens AI makes legal documents transparent, accessible, and grounded using Google Gemini 2.5. "
        "Provides interactive side-by-side clause verification, anti-hallucination detection, "
        "contract comparison, and lawyer consultation briefing packets."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Apply GZip Response Compression (Optimizes efficiency and network transfer)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Apply OWASP Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

ALLOWED_CORS_HEADERS = [
    "Content-Type",
    "Authorization",
    "Accept",
    "X-Requested-With",
    "Cache-Control",
    "Pragma",
    "Origin",
    "User-Agent",
    "X-Forwarded-For",
    "X-Forwarded-Proto",
    "Upgrade",
    "Connection",
    "Sec-WebSocket-Key",
    "Sec-WebSocket-Version",
    "Sec-WebSocket-Extensions",
]

# Apply CORS Protection
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "X-Requested-With",
        "Cache-Control",
        "Pragma",
        "Origin",
        "User-Agent",
        "X-Forwarded-For",
        "X-Forwarded-Proto",
        "Upgrade",
        "Connection",
        "Sec-WebSocket-Key",
        "Sec-WebSocket-Version",
        "Sec-WebSocket-Extensions",
    ],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Enforce basic IP rate limiting for API endpoints."""
    if request.url.path.startswith("/api/"):
        try:
            client_ip = request.client.host if request.client else "127.0.0.1"
        except Exception:
            client_ip = "127.0.0.1"

        if not rate_limiter.check(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down your requests."},
            )

    try:
        return await call_next(request)
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. An unexpected error occurred."},
        )


# Include API Endpoints
app.include_router(api_router)

# Mount Static Files (UI)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serves the main accessible single-page web UI."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "JurisLens AI API is running. Visit /docs for OpenAPI documentation."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
