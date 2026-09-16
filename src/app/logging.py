import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event)


def configure_logging(log_level: str) -> None:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    logging.basicConfig(
        level=log_level.upper(),
        handlers=[stdout_handler],
    )
