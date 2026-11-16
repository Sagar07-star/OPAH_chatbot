"""Runtime configuration for CREATEchat.

Values come from the real process environment, then from ``.env`` files — the
repository root first, ``backend/.env`` last, so the backend's own file wins.
Blank assignments never shadow a real value. Parsing is done by python-dotenv;
the prototype never hardcodes secrets.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


def _find_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "createchat-prototype-kit").is_dir():
            return candidate
    return start.parent


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = _find_root(BACKEND_DIR)
KIT_DIR = PROJECT_ROOT / "createchat-prototype-kit"
VAR_DIR = BACKEND_DIR / "var"


def _load_env() -> dict[str, str]:
    """Merge .env files; ``backend/.env`` overrides the root one, blanks are skipped.

    Real environment variables always take precedence — see :func:`env`.
    """
    merged: dict[str, str] = {}
    for path in (PROJECT_ROOT / ".env", BACKEND_DIR / ".env"):
        if not path.is_file():
            continue
        for key, value in dotenv_values(path, encoding="utf-8").items():
            if not key or value is None or not value.strip():
                continue
            merged[key] = value.strip()
    return merged


_FILE_ENV = _load_env()


def env(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    if value is not None and value.strip() != "":
        return value.strip()
    return _FILE_ENV.get(key, default)


def _bool(key: str, default: bool) -> bool:
    raw = env(key, "true" if default else "false").lower()
    return raw in ("1", "true", "yes", "on")


def _int(key: str, default: int) -> int:
    try:
        return int(env(key, str(default)))
    except ValueError:
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(env(key, str(default)))
    except ValueError:
        return default


def _secret_key() -> str:
    configured = env("APP_SECRET_KEY")
    if configured:
        return configured
    # A stable development key so restarts keep the demo session valid.
    VAR_DIR.mkdir(parents=True, exist_ok=True)
    key_file = VAR_DIR / "dev_secret.key"
    if key_file.is_file():
        return key_file.read_text(encoding="utf-8").strip()
    generated = secrets.token_urlsafe(48)
    key_file.write_text(generated, encoding="utf-8")
    return generated


@dataclass(frozen=True)
class Settings:
    app_name: str = "CREATEchat"
    environment: str = field(default_factory=lambda: env("APP_ENV", "development"))
    openai_api_key: str = field(default_factory=lambda: env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: env("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str = field(default_factory=lambda: env("OPENAI_BASE_URL"))
    moderation_model: str = field(default_factory=lambda: env("OPENAI_MODERATION_MODEL", "omni-moderation-latest"))
    moderation_enabled: bool = field(default_factory=lambda: _bool("MODERATION_ENABLED", True))
    vision_enabled: bool = field(default_factory=lambda: _bool("VISION_ENABLED", True))
    secret_key: str = field(default_factory=_secret_key)
    session_days: int = field(default_factory=lambda: _int("SESSION_DAYS", 7))
    database_path: Path = field(default_factory=lambda: Path(env("DATABASE_PATH", str(VAR_DIR / "createchat.db"))))
    upload_dir: Path = field(default_factory=lambda: Path(env("UPLOAD_DIR", str(VAR_DIR / "uploads"))))
    max_upload_files: int = field(default_factory=lambda: _int("MAX_UPLOAD_FILES", 10))
    max_image_bytes: int = field(default_factory=lambda: _int("MAX_IMAGE_BYTES", 8 * 1024 * 1024))
    max_pdf_bytes: int = field(default_factory=lambda: _int("MAX_PDF_BYTES", 12 * 1024 * 1024))
    max_pdf_pages: int = field(default_factory=lambda: _int("MAX_PDF_PAGES", 30))
    max_pdf_text_chars: int = field(default_factory=lambda: _int("MAX_PDF_TEXT_CHARS", 20000))
    max_message_chars: int = field(default_factory=lambda: _int("MAX_MESSAGE_CHARS", 4000))
    max_tool_rounds: int = field(default_factory=lambda: _int("MAX_TOOL_ROUNDS", 4))
    transcript_limit: int = field(default_factory=lambda: _int("TRANSCRIPT_LIMIT", 20))
    transcript_char_budget: int = field(default_factory=lambda: _int("TRANSCRIPT_CHAR_BUDGET", 8000))
    transcript_keep: int = field(default_factory=lambda: _int("TRANSCRIPT_KEEP", 200))
    max_output_tokens: int = field(default_factory=lambda: _int("OPENAI_MAX_OUTPUT_TOKENS", 600))
    rate_client_per_minute: int = field(default_factory=lambda: _int("RATE_CLIENT_PER_MINUTE", 20))
    rate_client_per_hour: int = field(default_factory=lambda: _int("RATE_CLIENT_PER_HOUR", 200))
    rate_anon_per_minute: int = field(default_factory=lambda: _int("RATE_ANON_PER_MINUTE", 6))
    rate_anon_per_hour: int = field(default_factory=lambda: _int("RATE_ANON_PER_HOUR", 30))
    anon_lifetime_messages: int = field(default_factory=lambda: _int("ANON_LIFETIME_MESSAGES", 25))
    anon_lifetime_uploads: int = field(default_factory=lambda: _int("ANON_LIFETIME_UPLOADS", 3))
    request_timeout_seconds: float = field(default_factory=lambda: _float("OPENAI_TIMEOUT_SECONDS", 75.0))
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )

    @property
    def model_configured(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()

VAR_DIR.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
