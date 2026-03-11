from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://maedeup:maedeup@localhost:5432/maedeup"
    REDIS_URL: str = "redis://localhost:6379/0"
    APP_ENV: str = "development"


settings = Settings()
