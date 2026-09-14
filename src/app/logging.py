import logging
import time


class UtcFormatter(logging.Formatter):
    converter = time.gmtime


def configure_logging(log_level: str) -> None:
    """Configure concise, timestamped logs for command-line processes."""
    level = getattr(logging, log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"unsupported log level: {log_level}")
    formatter = UtcFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
    )
    logging.basicConfig(
        level=level,
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
