from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import create_router
from app.config.settings import get_settings


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    app = FastAPI(title="GradRadar", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=[],
    )

    @app.get("/", tags=["service"])
    def root() -> dict[str, str]:
        return {
            "name": "GradRadar API",
            "docs_url": "/docs",
            "health_url": "/health",
            "jobs_url": "/v1/jobs",
        }

    app.include_router(create_router(session_factory))
    return app


app = create_app()
