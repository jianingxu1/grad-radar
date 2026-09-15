from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from secrets import compare_digest
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import Select, case, exists, func, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas import (
    HealthResponse,
    JobPageResponse,
    JobResponse,
    NotificationSettingsResponse,
    SourceFreshnessResponse,
    SourceResponse,
    TelegramLinkResponse,
)
from app.config.settings import get_settings
from app.database.models import JobPosting, JobPostingSource, Source, TelegramConnection
from app.database.session import get_session_factory
from app.services.auth import get_current_user
from app.services.notifications import (
    connection_state,
    consume_start,
    create_link_intent,
    disable_connection,
)
from app.services.telegram import TelegramClient
from app.sources.definitions import SOURCES, SourceName


def create_router(session_factory: sessionmaker[Session] | None = None) -> APIRouter:
    router = APIRouter()

    def get_session() -> Iterator[Session]:
        factory = get_session_factory() if session_factory is None else session_factory
        with factory() as session:
            yield session

    @router.get("/health", response_model=HealthResponse)
    def health(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
        try:
            session.execute(text("select 1"))
        except Exception as error:
            raise HTTPException(status_code=503, detail="database unavailable") from error
        return HealthResponse(status="ok")

    @router.get("/v1/jobs", response_model=JobPageResponse)
    def list_jobs(
        *,
        q: str | None = None,
        location: str | None = None,
        remote: bool | None = None,
        company: str | None = None,
        posted_within_hours: Annotated[int | None, Query(ge=1)] = None,
        listed_within_hours: Annotated[int | None, Query(ge=1)] = None,
        sources: Annotated[list[SourceName] | None, Query()] = None,
        sort_by: Literal["company_name", "listed_at"] = "listed_at",
        sort_direction: Literal["asc", "desc"] = "desc",
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        session: Annotated[Session, Depends(get_session)],
    ) -> JobPageResponse:
        current_source_link = (
            select(JobPostingSource.job_posting_id)
            .join(Source, JobPostingSource.source_id == Source.id)
            .where(
                JobPostingSource.job_posting_id == JobPosting.id,
                JobPostingSource.last_seen_at == Source.last_successful_sync_at,
            )
        )
        if sources:
            current_source_link = current_source_link.where(Source.name.in_(sources))
        source_priority = case(
            {str(source.name): source.priority for source in SOURCES}, value=Source.name, else_=999
        )
        source_position = (
            select(JobPostingSource.source_position)
            .join(Source, JobPostingSource.source_id == Source.id)
            .where(
                JobPostingSource.job_posting_id == JobPosting.id,
                JobPostingSource.last_seen_at == Source.last_successful_sync_at,
            )
            .order_by(source_priority, JobPostingSource.source_position.asc().nulls_last())
            .limit(1)
            .scalar_subquery()
        )
        source_order = (
            select(source_priority)
            .join(JobPostingSource, JobPostingSource.source_id == Source.id)
            .where(
                JobPostingSource.job_posting_id == JobPosting.id,
                JobPostingSource.last_seen_at == Source.last_successful_sync_at,
            )
            .order_by(source_priority, JobPostingSource.source_position.asc().nulls_last())
            .limit(1)
            .scalar_subquery()
        )
        if sources:
            source_position = source_position.where(Source.name.in_(sources))
            source_order = source_order.where(Source.name.in_(sources))
        statement: Select[tuple[JobPosting]] = select(JobPosting).where(exists(current_source_link))
        if q:
            pattern = f"%{q.strip()}%"
            statement = statement.where(
                or_(JobPosting.company_name.ilike(pattern), JobPosting.title.ilike(pattern))
            )
        if location:
            statement = statement.where(JobPosting.location.ilike(f"%{location.strip()}%"))
        if remote is not None:
            has_remote = JobPosting.location.ilike("%remote%")
            statement = statement.where(has_remote if remote else ~has_remote)
        if company:
            statement = statement.where(JobPosting.company_name.ilike(f"%{company.strip()}%"))
        if posted_within_hours:
            statement = statement.where(
                JobPosting.first_seen_at >= datetime.now(UTC) - timedelta(hours=posted_within_hours)
            )
        if listed_within_hours:
            statement = statement.where(
                JobPosting.listed_at >= datetime.now(UTC) - timedelta(hours=listed_within_hours)
            )
        total = session.scalar(select(func.count()).select_from(statement.subquery()))
        if sort_by == "listed_at":
            date_order = (
                JobPosting.listed_at.asc().nulls_last()
                if sort_direction == "asc"
                else JobPosting.listed_at.desc().nulls_last()
            )
            position_order = (
                source_position.desc().nulls_last()
                if sort_direction == "asc"
                else source_position.asc().nulls_last()
            )
            ordering = [date_order, source_order, position_order, JobPosting.id.desc()]
        else:
            company_order = (
                JobPosting.company_name.asc().nulls_last()
                if sort_direction == "asc"
                else JobPosting.company_name.desc().nulls_last()
            )
            ordering = [company_order, JobPosting.id.desc()]
        jobs = session.scalars(statement.order_by(*ordering).offset(offset).limit(limit)).all()
        sources_by_job = _sources_by_job(session, [job.id for job in jobs])
        return JobPageResponse(
            items=[_job_response(job, sources_by_job[job.id]) for job in jobs],
            offset=offset,
            limit=limit,
            total=total or 0,
            source_freshness=_source_freshness(session),
        )

    @router.get("/v1/me/notification-settings", response_model=NotificationSettingsResponse)
    def notification_settings(
        user_id: Annotated[str, Depends(get_current_user)],
        session: Annotated[Session, Depends(get_session)],
    ) -> NotificationSettingsResponse:
        state, expires_at = connection_state(session, UUID(user_id), datetime.now(UTC))
        return NotificationSettingsResponse(status=state, expires_at=expires_at)

    @router.post("/v1/me/telegram/link", response_model=TelegramLinkResponse)
    def create_telegram_link(
        user_id: Annotated[str, Depends(get_current_user)],
        session: Annotated[Session, Depends(get_session)],
    ) -> TelegramLinkResponse:
        settings = get_settings()
        if not settings.telegram_bot_username:
            raise HTTPException(status_code=503, detail="Telegram connection is unavailable")
        now = datetime.now(UTC)
        with session.begin():
            token, expires_at = create_link_intent(session, UUID(user_id), now)
        return TelegramLinkResponse(
            deep_link=f"https://t.me/{settings.telegram_bot_username}?start={token}",
            expires_at=expires_at,
        )

    @router.delete("/v1/me/telegram", status_code=204)
    def disconnect_telegram(
        user_id: Annotated[str, Depends(get_current_user)],
        session: Annotated[Session, Depends(get_session)],
    ) -> None:
        with session.begin():
            disable_connection(session, UUID(user_id), datetime.now(UTC))

    @router.post("/v1/integrations/telegram/webhook", status_code=200)
    def telegram_webhook(
        update: dict[object, object],
        session: Annotated[Session, Depends(get_session)],
        secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
    ) -> dict[str, bool]:
        settings = get_settings()
        if (
            not settings.telegram_webhook_secret
            or not secret
            or not compare_digest(secret, settings.telegram_webhook_secret)
        ):
            raise HTTPException(status_code=403, detail="invalid webhook secret")
        message = update.get("message")
        if not isinstance(message, dict):
            return {"ok": True}
        chat, sender, text = message.get("chat"), message.get("from"), message.get("text")
        if not isinstance(chat, dict) or not isinstance(sender, dict) or not isinstance(text, str):
            return {"ok": True}
        if (
            chat.get("type") != "private"
            or type(chat.get("id")) is not int
            or type(sender.get("id")) is not int
        ):
            return {"ok": True}
        reply: str | None = None
        now = datetime.now(UTC)
        with session.begin():
            if text.startswith("/start "):
                reply = (
                    "Telegram alerts connected."
                    if consume_start(
                        session, text.split(maxsplit=1)[1], sender["id"], chat["id"], now
                    )
                    else (
                        "That connection link is invalid or has expired. "
                        "Create a new link on GradRadar."
                    )
                )
            elif text.startswith("/stop"):
                connection = session.scalar(
                    select(TelegramConnection).where(
                        TelegramConnection.telegram_chat_id == chat["id"]
                    )
                )
                if connection:
                    disable_connection(session, connection.user_id, now)
                reply = "Telegram alerts stopped. You can reconnect from GradRadar settings."
            elif text.startswith("/help") or text.startswith("/settings"):
                reply = "Manage Telegram alerts at GradRadar notification settings."
        if reply and settings.telegram_bot_token:
            TelegramClient(settings.telegram_bot_token).send_message(reply, chat_id=str(chat["id"]))
        return {"ok": True}

    return router


def _sources_by_job(session: Session, job_ids: list[UUID]) -> dict[UUID, list[SourceResponse]]:
    sources_by_job: dict[UUID, list[SourceResponse]] = defaultdict(list)
    if not job_ids:
        return sources_by_job
    rows = session.execute(
        select(JobPostingSource.job_posting_id, Source.name, Source.url)
        .join(JobPostingSource, JobPostingSource.source_id == Source.id)
        .where(JobPostingSource.job_posting_id.in_(job_ids))
        .order_by(JobPostingSource.job_posting_id, Source.name)
    ).all()
    for job_id, name, url in rows:
        sources_by_job[job_id].append(SourceResponse(name=name, url=url))
    return sources_by_job


def _source_freshness(session: Session) -> list[SourceFreshnessResponse]:
    return [
        SourceFreshnessResponse(
            name=source.name,
            url=source.url,
            last_successful_sync_at=source.last_successful_sync_at,
        )
        for source in session.scalars(select(Source).order_by(Source.name))
    ]


def _job_response(job: JobPosting, sources: list[SourceResponse]) -> JobResponse:
    return JobResponse(
        id=job.id,
        company_name=job.company_name,
        title=job.title,
        apply_url=job.apply_url,
        location=job.location,
        listed_at=job.listed_at,
        first_seen_at=job.first_seen_at,
        sources=sources,
    )
