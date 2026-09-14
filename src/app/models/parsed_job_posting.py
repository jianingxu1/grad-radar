from datetime import UTC, datetime

from pydantic import BaseModel, HttpUrl, field_validator

from app.sources.definitions import SourceName


class ParsedJobPosting(BaseModel):
    source_name: SourceName
    company_name: str
    title: str
    apply_url: str
    application_key: str
    location: str
    listed_at: datetime | None
    source_position: int

    @field_validator("company_name", "title", "application_key", "location")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value

    @field_validator("apply_url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        HttpUrl(value)
        return value

    @field_validator("listed_at")
    @classmethod
    def require_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        ):
            raise ValueError("listed_at must be UTC")
        return value

    @field_validator("source_position")
    @classmethod
    def require_nonnegative_source_position(cls, value: int) -> int:
        if value < 0:
            raise ValueError("source_position must not be negative")
        return value
