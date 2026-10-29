import warnings
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    # Uploaded memory files: relative paths resolve against the backend working dir
    UPLOAD_DIR: Path = Path("uploads")
    MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    MAX_AUDIO_BYTES: int = 50 * 1024 * 1024
    MAX_VIDEO_BYTES: int = 200 * 1024 * 1024
    MAX_FILES_PER_UPLOAD: int = 10

    # "fake" swaps the models for deterministic stand-ins so the app can be driven
    # end to end (Playwright) where there is no Ollama. It is development only.
    AI_BACKEND: Literal["ollama", "fake"] = "ollama"

    @model_validator(mode="after")
    def _fake_ai_only_in_development(self) -> Self:
        if self.AI_BACKEND == "fake" and self.FASTAPI_ENV != "development":
            raise ValueError(
                "AI_BACKEND=fake answers with canned text and is only allowed "
                "when FASTAPI_ENV=development"
            )
        return self

    # Local Ollama: chat model extracts and answers, embedding model powers search,
    # vision model describes photos. Whisper transcribes audio and video.
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "llama3.1"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_VISION_MODEL: str = "llava:7b"
    # Local models are slow on CPU, so be generous before giving up
    OLLAMA_TIMEOUT_SECONDS: float = 300
    WHISPER_MODEL: str = "base"
    # Longer recordings are refused: file size limits do not bound compressed audio
    MAX_MEDIA_SECONDS: float = 3600
    # How many extracted memories are retrieved to answer a question
    RETRIEVAL_TOP_K: int = 5
    # Cosine similarity a retrieved memory needs before it may be used in an answer
    MIN_RELEVANCE_SCORE: float = 0.45
    # Extracted items the model is less sure about than this are dropped
    MIN_EXTRACTION_CONFIDENCE: float = 0.3
    # Confirmed quotes sent to the persona prompt as examples of how they spoke
    PERSONA_STYLE_EXAMPLES: int = 5
    # Earlier messages of the open conversation sent along with a new one
    PERSONA_HISTORY_TURNS: int = 6
    # A conversation nobody has written in for this long is ended and summarized
    CONVERSATION_IDLE_MINUTES: int = 30
    # How often the app looks for idle conversations; 0 turns the check off
    CONVERSATION_SWEEP_SECONDS: int = 60

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.FASTAPI_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        for host in self.DATABASE_URL.hosts():
            self._check_default_secret("DATABASE_URL password", host["password"])
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
