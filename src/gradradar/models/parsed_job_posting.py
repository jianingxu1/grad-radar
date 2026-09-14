from datetime import UTC, datetime

from pydantic import BaseModel, HttpUrl, field_validator


class ParsedJobPosting(BaseModel):
    source_name: str
    company_name: str
    title: str
    apply_url: str
    application_key: str
    location: str
    listed_at: datetime | None

    @field_validator("source_name", "company_name", "title", "application_key", "location")
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
