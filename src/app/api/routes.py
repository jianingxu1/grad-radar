import logging
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from secrets import compare_digest
from typing import Annotated, Literal, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas import (
    HealthResponse,
    JobPageResponse,
    JobResponse,
    NotificationSettingsResponse,
    SourceAdminResponse,
    SourceCreateRequest,
    SourceDetailResponse,
    SourceFreshnessResponse,
    SourceResponse,
    SourceUpdateRequest,
    TelegramLinkResponse,
)
from app.config.settings import get_settings
from app.database.models import JobPosting, JobPostingSource, Source, TelegramConnection
from app.database.session import get_session_factory
from app.services.auth import get_current_user, get_source_admin
from app.services.notifications import (
    connection_state,
    consume_start,
    create_link_intent,
    disable_connection,
)
from app.services.telegram import TelegramClient
from app.sources.ats import Platform, board_url, fetch_board
from app.sources.board_filter import DEFAULT_FILTER, validate_filter

logger = logging.getLogger(__name__)


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
            logger.exception("api.health.failed error=%s", error)
            raise HTTPException(status_code=503, detail="database unavailable") from error
        return HealthResponse(status="ok")

    @router.get("/v1/sources", response_model=list[SourceDetailResponse])
    def list_sources(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[SourceDetailResponse]:
        return [
            _source_detail(source)
            for source in session.scalars(select(Source).order_by(Source.priority, Source.name))
        ]

    @router.get("/v1/me/source-admin", response_model=SourceAdminResponse)
    def source_admin_status(
        user_id: Annotated[str, Depends(get_current_user)],
    ) -> SourceAdminResponse:
        return SourceAdminResponse(is_admin=user_id in get_settings().source_admin_ids)

    @router.post("/v1/sources", response_model=SourceDetailResponse, status_code=201)
    def create_source(
        request: SourceCreateRequest,
        _admin: Annotated[str, Depends(get_source_admin)],
        session: Annotated[Session, Depends(get_session)],
    ) -> SourceDetailResponse:
        board_name = request.board_name.strip()
        source_name = f"{request.platform}:{board_name.casefold()}"
        if session.scalar(select(Source.id).where(Source.name == source_name)):
            raise HTTPException(status_code=409, detail="source already exists")
        try:
            config = validate_filter(request.filter_config or DEFAULT_FILTER)
            with httpx.Client(timeout=20) as client:
                fetch_board(client, request.platform, board_name)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail="board could not be verified") from error
        source = Source(
            name=source_name,
            url=board_url(request.platform, board_name),
            platform=request.platform,
            board_name=board_name,
            company_name=request.company_name.strip(),
            filter_config=config,
            priority=100,
        )
        session.add(source)
        session.flush()
        detail = _source_detail(source)
        session.commit()
        return detail

    @router.patch("/v1/sources/{source_id}", response_model=SourceDetailResponse)
    def update_source(
        source_id: UUID,
        request: SourceUpdateRequest,
        _admin: Annotated[str, Depends(get_source_admin)],
        session: Annotated[Session, Depends(get_session)],
    ) -> SourceDetailResponse:
        source = session.get(Source, source_id)
        if source is None or source.platform == "github":
            raise HTTPException(status_code=404, detail="board source not found")
        try:
            config = (
                validate_filter(request.filter_config)
                if request.filter_config is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if request.enabled and not source.enabled:
            if not source.board_name:
                raise HTTPException(status_code=422, detail="board source has no board name")
            try:
                with httpx.Client(timeout=20) as client:
                    fetch_board(client, cast(Platform, source.platform), source.board_name)
            except (ValueError, httpx.HTTPError) as error:
                raise HTTPException(
                    status_code=502, detail="board could not be verified"
                ) from error
        if request.enabled is not None:
            source.enabled = request.enabled
        if config is not None:
            source.filter_config = config
        session.flush()
        detail = _source_detail(source)
        session.commit()
        return detail

    @router.get("/v1/jobs", response_model=JobPageResponse)
    def list_jobs(
        *,
        q: str | None = None,
        location: str | None = None,
        remote: bool | None = None,
        company: str | None = None,
        posted_within_hours: Annotated[int | None, Query(ge=1)] = None,
        listed_within_hours: Annotated[int | None, Query(ge=1)] = None,
        sources: Annotated[list[str] | None, Query()] = None,
        sort_by: Literal["company_name", "listed_at"] = "listed_at",
        sort_direction: Literal["asc", "desc"] = "desc",
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        session: Annotated[Session, Depends(get_session)],
    ) -> JobPageResponse:
        source_link = (
            select(JobPostingSource.job_posting_id)
            .join(Source, JobPostingSource.source_id == Source.id)
            .where(
                JobPostingSource.job_posting_id == JobPosting.id,
                JobPostingSource.active,
                Source.enabled,
            )
        )
        if sources:
            source_link = source_link.where(Source.name.in_(sources))
        source_priority = Source.priority
        source_position = (
            select(JobPostingSource.source_position)
            .join(Source, JobPostingSource.source_id == Source.id)
            .where(
                JobPostingSource.job_posting_id == JobPosting.id,
                JobPostingSource.active,
                Source.enabled,
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
                JobPostingSource.active,
                Source.enabled,
            )
            .order_by(source_priority, JobPostingSource.source_position.asc().nulls_last())
            .limit(1)
            .scalar_subquery()
        )
        if sources:
            source_position = source_position.where(Source.name.in_(sources))
            source_order = source_order.where(Source.name.in_(sources))
        statement = select(JobPosting).where(exists(source_link))
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
            ordering = [
                date_order,
                JobPosting.first_seen_at.desc(),
                source_order,
                position_order,
                JobPosting.id.desc(),
            ]
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
            logger.error("api.telegram.link.failed reason=bot_username_not_configured")
            raise HTTPException(status_code=503, detail="Telegram connection is unavailable")
        now = datetime.now(UTC)
        with session.begin():
            token, expires_at = create_link_intent(session, UUID(user_id), now)
        logger.info("api.telegram.link.created expires_at=%s", expires_at.isoformat())
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
            disconnected = disable_connection(session, UUID(user_id), datetime.now(UTC))
        logger.info("api.telegram.disconnected existed=%s", disconnected)

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
            logger.warning("api.telegram.webhook.rejected reason=invalid_secret")
            raise HTTPException(status_code=403, detail="invalid webhook secret")
        message = update.get("message")
        if not isinstance(message, dict):
            logger.info("api.telegram.webhook.ignored reason=no_message")
            return {"ok": True}
        chat, sender, text = message.get("chat"), message.get("from"), message.get("text")
        if not isinstance(chat, dict) or not isinstance(sender, dict) or not isinstance(text, str):
            logger.info("api.telegram.webhook.ignored reason=invalid_message")
            return {"ok": True}
        if (
            chat.get("type") != "private"
            or type(chat.get("id")) is not int
            or type(sender.get("id")) is not int
        ):
            logger.info("api.telegram.webhook.ignored reason=non_private_message")
            return {"ok": True}
        reply: str | None = None
        now = datetime.now(UTC)
        with session.begin():
            if text.startswith("/start "):
                result = consume_start(
                    session, text.split(maxsplit=1)[1], sender["id"], chat["id"], now
                )
                reply = _telegram_start_reply(result)
                logger.info("api.telegram.webhook.start result=%s", result)
            elif text.startswith("/start"):
                reply = "Open GradRadar notification settings and use Connect Telegram first."
            elif text.startswith("/stop"):
                connection = session.scalar(
                    select(TelegramConnection).where(
                        TelegramConnection.telegram_chat_id == chat["id"]
                    )
                )
                if connection:
                    disable_connection(session, connection.user_id, now)
                reply = "Telegram alerts stopped. You can reconnect from GradRadar settings."
                logger.info("api.telegram.webhook.stop connection_found=%s", connection is not None)
            elif text.startswith("/help") or text.startswith("/settings"):
                reply = "Manage Telegram alerts at GradRadar notification settings."
        if reply and settings.telegram_bot_token:
            with TelegramClient(settings.telegram_bot_token) as telegram:
                outcome = telegram.send_message(reply, chat_id=str(chat["id"]))
            if outcome.success:
                logger.info(
                    "api.telegram.webhook.reply_succeeded message_id=%s", outcome.message_id
                )
            else:
                logger.error(
                    "api.telegram.webhook.reply_failed error=%s status_code=%s",
                    outcome.error,
                    outcome.status_code,
                )
        elif reply:
            logger.error("api.telegram.webhook.reply_failed reason=bot_token_not_configured")
        return {"ok": True}

    return router


def _telegram_start_reply(result: str) -> str:
    if result == "connected":
        return "Telegram alerts connected."
    if result == "already_connected":
        return "Telegram alerts are already connected."
    if result == "chat_conflict":
        return "This Telegram chat is already linked to another GradRadar account."
    if result == "telegram_user_conflict":
        return "This Telegram account is already linked to another GradRadar account."
    if result == "user_conflict":
        return "This GradRadar account is linked to a different Telegram account."
    if result == "invalid":
        return "That connection link is invalid. Create a new link on GradRadar."
    return "That connection link has expired or was already used. Create a new link on GradRadar."


def _sources_by_job(session: Session, job_ids: list[UUID]) -> dict[UUID, list[SourceResponse]]:
    sources_by_job: dict[UUID, list[SourceResponse]] = defaultdict(list)
    if not job_ids:
        return sources_by_job
    rows = session.execute(
        select(JobPostingSource.job_posting_id, Source.name, Source.url, JobPostingSource.apply_url)
        .join(JobPostingSource, JobPostingSource.source_id == Source.id)
        .where(JobPostingSource.job_posting_id.in_(job_ids))
        .where(JobPostingSource.active, Source.enabled)
        .order_by(JobPostingSource.job_posting_id, Source.name)
    ).all()
    for job_id, name, url, apply_url in rows:
        sources_by_job[job_id].append(SourceResponse(name=name, url=url, apply_url=apply_url))
    return sources_by_job


def _source_freshness(session: Session) -> list[SourceFreshnessResponse]:
    return [
        SourceFreshnessResponse(
            name=source.name,
            url=source.url,
            last_successful_sync_at=source.last_successful_sync_at,
        )
        for source in session.scalars(select(Source).where(Source.enabled).order_by(Source.name))
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


def _source_detail(source: Source) -> SourceDetailResponse:
    return SourceDetailResponse(
        id=source.id,
        name=source.name,
        url=source.url,
        platform=source.platform,
        board_name=source.board_name,
        company_name=source.company_name,
        enabled=source.enabled,
        filter_config=source.filter_config,
        last_successful_sync_at=source.last_successful_sync_at,
        last_sync_status=source.last_sync_status,
    )
