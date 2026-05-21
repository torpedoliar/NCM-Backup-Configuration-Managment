from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_FILE_NAME = "ncm-v4.log"
_DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_file_logger(logs_dir: Path, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> Path:
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / LOG_FILE_NAME

    root = logging.getLogger()
    for handler in root.handlers:
        base = getattr(handler, "baseFilename", "")
        if base and base.endswith(LOG_FILE_NAME):
            return log_file

    formatter = logging.Formatter(_DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return log_file
