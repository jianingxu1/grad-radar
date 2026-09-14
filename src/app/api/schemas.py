from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SourceResponse(BaseModel):
    name: str
    url: str


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
