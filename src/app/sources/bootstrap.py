from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Source
from app.sources.definitions import SOURCES


def bootstrap_sources(session: Session) -> int:
    existing = set(session.scalars(select(Source.name)).all())
    for definition in SOURCES:
        if definition.name not in existing:
            session.add(Source(name=definition.name, url=definition.url))
    return len(set(definition.name for definition in SOURCES) - existing)
