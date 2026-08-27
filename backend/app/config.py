from dataclasses import dataclass
import os


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

