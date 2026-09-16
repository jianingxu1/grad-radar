import sys
from unittest.mock import patch

from app.logging import configure_logging


def test_configure_logging_writes_records_to_stdout() -> None:
    with patch("app.logging.logging.basicConfig") as basic_config:
        configure_logging("INFO")

    basic_config.assert_called_once_with(level="INFO", stream=sys.stdout)
