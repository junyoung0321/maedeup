from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://maedeup:maedeup@localhost:5432/maedeup"
    REDIS_URL: str = "redis://localhost:6379/0"
    APP_ENV: str = "development"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    JWT_SECRET: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"

    GEMINI_API_KEY: str = ""
    KAKAO_REST_API_KEY: str = ""


settings = Settings()
