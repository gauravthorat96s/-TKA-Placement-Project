"""Application logging. Call setup_logging() once at start-up; get_logger() returns child loggers."""
import logging
from app.config import LOG_FILE


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("rpms")
    if any(isinstance(h, logging.FileHandler) for h in root.handlers):
        return
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str = "rpms") -> logging.Logger:
    return logging.getLogger(name if name.startswith("rpms") else f"rpms.{name}")
