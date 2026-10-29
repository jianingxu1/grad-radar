from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SourceResponse(BaseModel):
    name: str
    url: str


class SourceFreshnessResponse(SourceResponse):
    last_successful_sync_at: datetime | None


class SourceDetailResponse(SourceFreshnessResponse):
    id: UUID
    platform: str
    board_name: str | None
    company_name: str | None
    enabled: bool
    filter_config: dict[str, list[str]]
    last_sync_status: str | None


class SourceCreateRequest(BaseModel):
    platform: Literal["greenhouse", "ashby", "lever"]
    board_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    company_name: str = Field(min_length=1, max_length=100)
    filter_config: dict[str, list[str]] | None = None

    @field_validator("company_name")
    @classmethod
    def require_company_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("company name cannot be blank")
        return value.strip()


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
