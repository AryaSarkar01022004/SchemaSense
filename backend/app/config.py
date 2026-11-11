import os
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = (
    os.getenv("SCHEMASENSE_DATA_DIR")
    or os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    or ""
).strip()

SETTINGS_FILE = os.path.join(_DATA_DIR or _BACKEND_ROOT, "llm_settings.json")


@dataclass
class Settings:
    DEBUG: bool = field(default_factory=lambda: os.getenv("DEBUG", "true").lower() in ("true", "1", "yes"))
    HOST: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # Persistent local SQLite paths (automatically use Railway volume when attached)
    DATA_DIR: str = field(default_factory=lambda: _DATA_DIR)
    APP_DB_PATH: str = field(
        default_factory=lambda: os.path.join(_DATA_DIR, "schemasense_app.db") if _DATA_DIR else "schemasense_app.db"
    )
    DEMO_DB_PATH: str = field(
        default_factory=lambda: os.path.join(_DATA_DIR, "demo_target.db") if _DATA_DIR else "demo_target.db"
    )

    # App Database (Postgres or SQLite)
    DATABASE_URL: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./schemasense_app.db"
    ))

    # Redis cache / message broker
    REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Master key for envelope encryption (32-byte hex or urlsafe string)
    MASTER_ENCRYPTION_KEY: str = field(default_factory=lambda: os.getenv(
        "MASTER_ENCRYPTION_KEY", "schemasense-master-secret-key-32b-min!!"
    ))

    # LLM Provider configuration ("lmstudio", "openai", "gemini", "anthropic", "mock")
    LLM_PROVIDER: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    LMSTUDIO_BASE_URL: str = field(default_factory=lambda: os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"))
    LMSTUDIO_API_KEY: str = field(default_factory=lambda: os.getenv("LMSTUDIO_API_KEY", "lm-studio"))
    OPENAI_API_KEY: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    GEMINI_API_KEY: Optional[str] = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    ANTHROPIC_API_KEY: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    LLM_MODEL: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    LLM_TIMEOUT_SECONDS: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT_SECONDS", "120")))

    # Limits & Safety
    DEFAULT_ROW_LIMIT: int = 1000
    HARD_CAP_ROW_LIMIT: int = 10000
    STATEMENT_TIMEOUT_MS: int = 10000  # 10s
    MAX_REPAIR_RETRIES: int = 2
    QUERY_CACHE_TTL_SECONDS: int = 300  # 5 minutes

    # Embedding config
    EMBEDDING_DIMENSION: int = 1536

    # Optional Gmail / SMTP Direct Export Configuration
    SMTP_HOST: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com"))
    SMTP_PORT: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    SMTP_USER: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_USER"))
    SMTP_PASSWORD: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))

    # File upload storage directory
    UPLOAD_DIR: str = field(default_factory=lambda: (
        os.path.join(_DATA_DIR, "uploads") if _DATA_DIR else os.path.join(_BACKEND_ROOT, "uploads")
    ))

    def __post_init__(self):
        self.load_persisted_llm_settings()

    def load_persisted_llm_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for key in (
                    "LLM_PROVIDER", "LMSTUDIO_BASE_URL", "LMSTUDIO_API_KEY",
                    "LLM_MODEL", "OPENAI_API_KEY", "GEMINI_API_KEY",
                    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"
                ):
                    if key in saved and saved[key] is not None:
                        setattr(self, key, saved[key])
            except Exception:
                pass

    def save_llm_settings(self, updates: Dict[str, Any]):
        allowed = {
            "provider": "LLM_PROVIDER",
            "lmstudio_base_url": "LMSTUDIO_BASE_URL",
            "lmstudio_api_key": "LMSTUDIO_API_KEY",
            "model": "LLM_MODEL",
            "openai_api_key": "OPENAI_API_KEY",
            "gemini_api_key": "GEMINI_API_KEY",
            "smtp_host": "SMTP_HOST",
            "smtp_port": "SMTP_PORT",
            "smtp_user": "SMTP_USER",
            "smtp_password": "SMTP_PASSWORD",
        }
        for req_key, attr in allowed.items():
            if req_key in updates and updates[req_key] is not None:
                val = updates[req_key]
                if isinstance(val, str):
                    val = val.strip()
                if attr == "SMTP_PORT":
                    val = int(val)
                # Avoid overwriting secret keys with empty masked placeholder
                if req_key in ("openai_api_key", "gemini_api_key", "smtp_password") and not val:
                    continue
                setattr(self, attr, val)

        payload = {
            "LLM_PROVIDER": self.LLM_PROVIDER,
            "LMSTUDIO_BASE_URL": self.LMSTUDIO_BASE_URL,
            "LMSTUDIO_API_KEY": self.LMSTUDIO_API_KEY,
            "LLM_MODEL": self.LLM_MODEL,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "GEMINI_API_KEY": self.GEMINI_API_KEY,
            "SMTP_HOST": self.SMTP_HOST,
            "SMTP_PORT": self.SMTP_PORT,
            "SMTP_USER": self.SMTP_USER,
            "SMTP_PASSWORD": self.SMTP_PASSWORD,
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)


settings = Settings()
