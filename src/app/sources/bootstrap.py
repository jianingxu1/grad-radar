from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Source
from app.sources.definitions import SOURCES


def bootstrap_sources(session: Session) -> int:
    configured_names = {definition.name for definition in SOURCES}
    existing = {
        source.name: source
        for source in session.scalars(select(Source).where(Source.name.in_(configured_names)))
    }
    for definition in SOURCES:
        if definition.name in existing:
            existing[definition.name].url = definition.url
        else:
            session.add(
                Source(name=definition.name, url=definition.url, priority=definition.priority)
            )
    return len(configured_names - existing.keys())
