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
    PAID_GEMINI_API_KEY: str = ""
    KAKAO_API_KEY: str = ""
    KAKAO_REST_API_KEY: str = ""

    # 시연용 fallback. true면 personal_data_extractor가 Gemini 호출을 skip하고
    # backend/data/demo_extraction_canned.json을 사용. 졸업 시연 단일 최대 실패점인
    # 라이브 Gemini 호출에 대한 안전망.
    DEMO_FALLBACK_ENABLED: bool = False

    @property
    def effective_gemini_api_key(self) -> str:
        """PAID 키가 있으면 우선 사용 (free tier quota 우회)."""
        return (self.PAID_GEMINI_API_KEY or self.GEMINI_API_KEY).strip()

    # 모임 confirm 시 구성원 Google Calendar 자동 등록 여부.
    # 기본 True (운영 환경 안전). 시연 중 반복 confirm으로 캘린더 오염 방지 시 false 설정.
    AUTO_CALENDAR_PUSH: bool = True

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

        if not self.effective_gemini_api_key:
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
