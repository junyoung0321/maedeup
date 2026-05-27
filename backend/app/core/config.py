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
    # true면 PAID_GEMINI_API_KEY 우선 사용. false(기본)면 free tier GEMINI_API_KEY만 사용.
    USE_PAID_GEMINI: bool = False

    # OpenAI GPT-4o-mini wrapper (K1-2). .env의 key 이름 그대로 (underscore 위치 주의).
    OPEN_AI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    # dominant cost site별 LLM 선택 toggle. "gemini" | "openai". 기본 = "gemini" (기존 동작 유지).
    LLM_PROVIDER_FOR_ANALYZER: str = "gemini"
    LLM_PROVIDER_FOR_ENTITY: str = "gemini"
    LLM_PROVIDER_FOR_INTENT: str = "gemini"
    # B 추가 dominant site 3개
    LLM_PROVIDER_FOR_PLACE_SCORING: str = "gemini"
    LLM_PROVIDER_FOR_SUMMARY: str = "gemini"
    LLM_PROVIDER_FOR_SOCIAL_SUMMARY: str = "gemini"
    # D 3-tier 자동 매핑. "gemini" | "openai".
    LLM_TIER_HIGH: str = "gemini"
    LLM_TIER_MID: str = "gemini"
    LLM_TIER_LOW: str = "gemini"
    KAKAO_API_KEY: str = ""
    KAKAO_REST_API_KEY: str = ""

    # 시연용 fallback. true면 personal_data_extractor가 Gemini 호출을 skip하고
    # backend/data/demo_extraction_canned.json을 사용. 졸업 시연 단일 최대 실패점인
    # 라이브 Gemini 호출에 대한 안전망.
    DEMO_FALLBACK_ENABLED: bool = False

    @property
    def effective_gemini_api_key(self) -> str:
        """USE_PAID_GEMINI=true면 PAID 우선, 아니면 free tier GEMINI_API_KEY 사용."""
        if self.USE_PAID_GEMINI and self.PAID_GEMINI_API_KEY:
            return self.PAID_GEMINI_API_KEY.strip()
        return self.GEMINI_API_KEY.strip()

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
