from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "jonas"
    version: str = "0.1.0"
    log_level: str = "debug"
    postgres_user: str = "jonas"
    postgres_password: str = "jonas"
    postgres_db: str = "jonas"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@postgres:5432/{self.postgres_db}"

    redis_url: str = "redis://redis:6379"
    telegram_bot_token: str = ""
    telegram_webhook_base_url: str = ""  # e.g. https://abc123.ngrok-free.app
    telegram_start_command: str = "start"
    telegram_teach_command: str = "teach"
    web_base_url: str = ""  # e.g. http://localhost:5173
    anthropic_api_key: str = ""
    openai_api_key: str = ""  # OPENAI_API_KEY
    default_model: str = "claude-haiku-4-5-20251001"
    # default_model: str = "gpt-5-mini-2025-08-07"
    triage_model: str = "claude-haiku-4-5-20251001"
    assignment_model: str = "claude-haiku-4-5-20251001"
    extraction_model: str = "claude-haiku-4-5-20251001"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "grammar_rules"
    embedding_model: str = "text-embedding-3-small"
    qdrant_similarity_threshold: float = 0.92
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_enabled: bool = True
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
