from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration from env vars prefixed with `TIDALWAVE_`."""

    model_config = SettingsConfigDict(
        env_prefix="TIDALWAVE_",
        case_sensitive=False,
        populate_by_name=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://tidalwave:tidalwave@localhost:5432/tidalwave"

    lastfm_api_key: str = ""
    lastfm_api_secret: str = ""
    # Public base URL used to build the Last.fm callback (cb=) parameter.
    public_base_url: str = "http://localhost:8080"

    # Where the backend fetches the frontend's index.html to serve /s/<token>
    # with link-preview tags. Empty: /s/<token> answers with a small page that
    # carries the tags and forwards to /?share=<token>.
    frontend_url: str = ""

    registration_mode: Literal["open", "allowlist"] = "allowlist"
    registration_allowlist: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Secret used to sign the session cookie. MUST be overridden in production.
    session_secret: str = "dev-insecure-change-me"

    log_level: str = "INFO"

    @field_validator("registration_allowlist", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v
