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
    anthropic_api_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
