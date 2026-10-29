import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SourceResponse(BaseModel):
    name: str
    url: str
    apply_url: str | None = None


class SourceFreshnessResponse(BaseModel):
    name: str
    url: str
    last_successful_sync_at: datetime | None


class SourceDetailResponse(SourceFreshnessResponse):
    id: UUID
    platform: str
    board_name: str | None
    company_name: str | None
    enabled: bool
    filter_config: dict[str, list[str]]
    platform_config: dict[str, str] | None
    last_sync_status: str | None


class SourceCreateRequest(BaseModel):
    platform: Literal["greenhouse", "ashby", "lever", "oracle", "smartrecruiters"]
    board_name: str = Field(min_length=1, max_length=100)
    company_name: str = Field(min_length=1, max_length=100)
    filter_config: dict[str, list[str]] | None = None
    platform_config: dict[str, str] | None = None

    @field_validator("board_name")
    @classmethod
    def require_safe_board_name(cls, value: str, info: object) -> str:
        value = value.strip()
        platform = getattr(info, "data", {}).get("platform")
        pattern = (
            r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,99}"
            if platform == "ashby"
            else r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}"
        )
        if not re.fullmatch(pattern, value):
            raise ValueError("invalid board name")
        return value

    @field_validator("company_name")
    @classmethod
    def require_company_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("company name cannot be blank")
        return value.strip()

    @field_validator("platform_config")
    @classmethod
    def validate_platform_config(
        cls, value: dict[str, str] | None, info: object
    ) -> dict[str, str] | None:
        platform = getattr(info, "data", {}).get("platform")
        if platform == "oracle":
            from app.sources.ats import validate_oracle_config

            return validate_oracle_config(value)
        if value is not None:
            raise ValueError("platform_config is only supported for Oracle sources")
        return None


class SourceUpdateRequest(BaseModel):
    enabled: bool | None = None
    filter_config: dict[str, list[str]] | None = None


class SourceAdminResponse(BaseModel):
    is_admin: bool


class HealthResponse(BaseModel):
    status: str


class JobResponse(BaseModel):
    id: UUID
    company_name: str
    title: str
    apply_url: str
    location: str
    listed_at: datetime | None
    first_seen_at: datetime
    sources: list[SourceResponse]


class JobPageResponse(BaseModel):
    items: list[JobResponse]
    offset: int
    limit: int
    total: int
    source_freshness: list[SourceFreshnessResponse]


class NotificationSettingsResponse(BaseModel):
    status: str
    expires_at: datetime | None = None


class TelegramLinkResponse(BaseModel):
    deep_link: str
    expires_at: datetime
