from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "jonas"
    version: str = "0.1.0"
    log_level: str = "debug"
    postgres_user: str = "jonas"
    postgres_password: str = "changeme"
    postgres_db: str = "jonas"
    redis_url: str = "redis://redis:6379"
    telegram_bot_token: str = ""
    telegram_allowed_chat_id: str = ""
    telegram_webhook_base_url: str = ""  # e.g. https://abc123.ngrok-free.app
    anthropic_api_key: str = ""
    openai_api_key: str = ""  # OPENAI_API_KEY
    default_model: str = "claude-haiku-4-5-20251001"
    # default_model: str = "gpt-5-mini-2025-08-07"
    triage_model: str = "claude-haiku-4-5-20251001"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
