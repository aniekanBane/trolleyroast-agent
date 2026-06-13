import functools
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LoggingSettings(BaseModel):
    """Logging configurations."""

    default_level: LogLevel = "INFO"
    file_directory: Path | None = None
    file_default_level: LogLevel = "WARNING"


class SupabaseSetting(BaseModel):
    """Supabase configurations."""

    project_url: HttpUrl
    ingest_path: str
    api_key: str | None = None
    agent_key: str | None = None

    @computed_field
    @property
    def ingest_url(self) -> str:
        base = str(self.project_url).rstrip("/")
        path = self.ingest_path.lstrip("/")
        return f"{base}/{path}"


class FastcrwSettings(BaseModel):
    """Fastcrw configurations."""

    endpoint_url: HttpUrl
    api_key: str | None = None


class ResendEmailSettings(BaseModel):
    """Resend email configurations."""

    api_key: str
    audience_id: str | None = None


class SmtpEmailSettings(BaseModel):
    """SMTP email configurations."""

    host: str
    port: int = Field(ge=1, le=65535)
    require_tls: bool = False
    username: str | None = Field(default=None, validation_alias="user")
    password: str | None = None


class EmailSettings(BaseModel):
    """Email configurations."""

    provider: Literal["resend", "smtp"] = "resend"
    default_sender: str | None = None
    resend: ResendEmailSettings | None = None
    smtp: SmtpEmailSettings | None = None


class ScraperSettings(BaseModel):
    """Scraper configurations."""

    trolley_uk_base_url: HttpUrl
    price_drop_threshold: float = Field(default=0.08, ge=0.0, le=1.0)
    max_item_failures: int = Field(default=20, ge=1, le=50)
    rate_limit_seconds: float = Field(default=2.5, gt=1.0, lt=60.0)


class AppSettings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        str_strip_whitespace=True,
    )

    CONTENT_ROOT_PATH: ClassVar[Path] = Path(__file__).parent.parent.resolve()

    debug: bool = Field(default=False, frozen=True)
    tz: str = Field(default="Europe/London", frozen=True)

    logging: LoggingSettings = Field(default=LoggingSettings(), frozen=True)
    supabase: SupabaseSetting
    fastcrw: FastcrwSettings
    scraper: ScraperSettings
    email: EmailSettings

    state_file_path: Path = Path("./state.json")

    @field_validator("email", mode="after")
    @classmethod
    def validate_email_settings(cls, v: EmailSettings):
        match v.provider:
            case "resend":
                if v.resend is None:
                    raise ValueError(
                        "Resend email settings are required for resend provider."
                    )
            case "smtp":
                if v.smtp is None:
                    raise ValueError(
                        "SMTP email settings are required for SMTP provider."
                    )
        return v


@functools.lru_cache
def get_settings() -> AppSettings:
    """Return a singleton instance of the application settings."""
    return AppSettings()


if __name__ == "__main__":
    import pprint

    from pydantic import ValidationError

    try:
        settings = get_settings()
        if settings.debug:
            pprint.pp(settings.model_dump())
    except ValidationError as e:
        pprint.pp(e)
    else:
        print("Configuration settings loaded successfully.")
