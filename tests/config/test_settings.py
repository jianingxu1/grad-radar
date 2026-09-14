import pytest
from pydantic import ValidationError

from gradradar.config.settings import Settings


def test_settings_requires_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({})


def test_settings_reads_database_url() -> None:
    settings = Settings.model_validate(
        {"database_url": "postgresql://postgres:postgres@localhost:54322/postgres"}
    )

    assert str(settings.database_url).startswith("postgresql://postgres:postgres@localhost")
