from app.config.settings import Settings
from app.database.models import JobPosting, JobPostingSource, Source
from app.database.session import create_session_factory


def test_session_factory_uses_installed_psycopg_driver() -> None:
    settings = Settings.model_validate(
        {"database_url": "postgresql://postgres:postgres@localhost:54322/postgres"}
    )

    session_factory = create_session_factory(settings)

    assert session_factory.kw["bind"].url.drivername == "postgresql+psycopg"


def test_models_target_the_migration_schema() -> None:
    assert {
        JobPosting.__table__.schema,
        Source.__table__.schema,
        JobPostingSource.__table__.schema,
    } == {"public"}
