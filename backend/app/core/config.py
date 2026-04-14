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
    KAKAO_API_KEY: str = ""
    KAKAO_REST_API_KEY: str = ""

    def required_env_fields(self) -> list[str]:
        required = [
            "GEMINI_API_KEY",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "GOOGLE_REDIRECT_URI",
            "KAKAO_REST_API_KEY",
        ]
        if self.APP_ENV.lower() not in {"development", "dev"} and self.JWT_SECRET == "change-me-in-production":
            required.append("JWT_SECRET")
        return required

    def validate_startup_settings(self) -> None:
        missing: list[str] = []

        if not self.GEMINI_API_KEY.strip():
            missing.append("GEMINI_API_KEY")
        if not self.GOOGLE_CLIENT_ID.strip():
            missing.append("GOOGLE_CLIENT_ID")
        if not self.GOOGLE_CLIENT_SECRET.strip():
            missing.append("GOOGLE_CLIENT_SECRET")
        if not self.GOOGLE_REDIRECT_URI.strip():
            missing.append("GOOGLE_REDIRECT_URI")
        if not self.KAKAO_REST_API_KEY.strip() and not self.KAKAO_API_KEY.strip():
            missing.append("KAKAO_REST_API_KEY (or KAKAO_API_KEY)")
        if self.APP_ENV.lower() not in {"development", "dev"} and self.JWT_SECRET == "change-me-in-production":
            missing.append("JWT_SECRET")

        if missing:
            raise RuntimeError(
                "Missing required startup configuration: "
                + ", ".join(missing)
                + ". Set these environment variables before starting the API."
            )


settings = Settings()
