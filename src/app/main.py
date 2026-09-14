from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import create_router


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    app = FastAPI(title="GradRadar", version="0.1.0")
    app.include_router(create_router(session_factory))
    return app


app = create_app()
