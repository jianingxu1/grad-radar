import json
import logging
import sys
from unittest.mock import patch

from app.logging import JsonFormatter, configure_logging


def test_json_formatter_includes_railway_severity() -> None:
    record = logging.LogRecord(
        "app.services.notifications", logging.ERROR, "", 0, "failed", (), None
    )

    assert json.loads(JsonFormatter().format(record)) == {
        "level": "ERROR",
        "logger": "app.services.notifications",
        "message": "failed",
    }


def test_configure_logging_uses_json_stdout_handler() -> None:
    with patch("app.logging.logging.basicConfig") as basic_config:
        configure_logging("INFO")

    basic_config.assert_called_once()
    _, kwargs = basic_config.call_args
    (stdout_handler,) = kwargs["handlers"]

    assert kwargs["level"] == "INFO"
    assert stdout_handler.stream is sys.stdout
    assert isinstance(stdout_handler.formatter, JsonFormatter)
