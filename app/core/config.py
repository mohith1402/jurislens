"""Application configuration settings using Pydantic Settings."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration management for JurisLens AI."""

    # Application Information
    APP_NAME: str = "JurisLens AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Google Generative AI (Gemini) Settings
    # Default model set to Gemini 2.5 Flash as requested
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.1  # Low temperature for deterministic legal precision
    GEMINI_MAX_OUTPUT_TOKENS: int = 4096

    # Security & Upload Controls
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ]
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB maximum
    ALLOWED_EXTENSIONS: List[str] = [".txt", ".md", ".pdf", ".docx", ".rtf"]

    # Evaluation & Fallback Mode
    # If True or if no API key is present, uses the offline deterministic legal reasoning engine
    ENABLE_FALLBACK_SIMULATION: bool = True

    # Caching & Horizontal Scalability (CWE-400 / CWE-770 Prevention)
    CACHE_BACKEND: str = "memory"  # Options: "memory" or "redis"
    REDIS_URL: str = ""  # Redis connection URL for distributed horizontal scaling
    CACHE_MAX_ENTRIES: int = 256  # Bounded memory ceiling
    CACHE_DEFAULT_TTL_SECONDS: int = 3600  # 1-hour TTL expiration

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def has_live_gemini_key(self) -> bool:
        """Verify whether a real Gemini API key is configured."""
        if self.ENVIRONMENT.lower() == "test":
            return False
        if not self.GEMINI_API_KEY:
            return False
        placeholder_values = {"your_gemini_api_key_here", "dummy", "placeholder", "none"}
        return self.GEMINI_API_KEY.strip().lower() not in placeholder_values


# Global singleton settings instance
settings = Settings()
