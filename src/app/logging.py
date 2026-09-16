import logging
import sys


def configure_logging(log_level: str) -> None:
    logging.basicConfig(level=log_level.upper(), stream=sys.stdout)
