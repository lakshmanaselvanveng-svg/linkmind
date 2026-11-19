from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LinkMind Google Chat Prototype"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    chat_auth_mode: str = "disabled"  # Use "id_token" in production.
    chat_auth_audience: str = ""
    max_page_bytes: int = 1_000_000
    fetch_timeout_seconds: float = 12.0
    max_redirects: int = 4
    max_article_chars: int = 24_000
    model_timeout_seconds: float = 20.0
    allowed_test_hosts: str = "example.com,www.example.com"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
