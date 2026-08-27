from dataclasses import dataclass
import os
from pathlib import Path


def _load_local_env() -> None:
    """Load simple KEY=VALUE pairs without adding a dotenv runtime dependency."""
    root = Path(__file__).resolve().parents[2]
    env_file = root / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./chatbi.db")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    wren_base_url: str = os.getenv("WREN_BASE_URL", "")
    wren_api_key: str = os.getenv("WREN_API_KEY", "")
    wren_timeout_seconds: float = float(os.getenv("WREN_TIMEOUT_SECONDS", "15"))


settings = Settings()

