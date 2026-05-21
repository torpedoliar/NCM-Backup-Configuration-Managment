import logging
from pathlib import Path

import pytest

from app_v4.core.logging import LOG_FILE_NAME, configure_file_logger


def test_configure_attaches_rotating_handler(tmp_path: Path):
    configure_file_logger(tmp_path / "logs")
    handlers = [h for h in logging.getLogger().handlers if getattr(h, "baseFilename", "").endswith(LOG_FILE_NAME)]
    assert handlers, "rotating file handler not attached"
    for h in handlers:
        logging.getLogger().removeHandler(h)


def test_configure_creates_log_file_and_writes(tmp_path: Path, caplog):
    logs_dir = tmp_path / "logs"
    configure_file_logger(logs_dir)
    logging.getLogger("test").info("hello world")
    log_file = logs_dir / LOG_FILE_NAME
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello world" in content
    for h in list(logging.getLogger().handlers):
        if getattr(h, "baseFilename", "").endswith(LOG_FILE_NAME):
            logging.getLogger().removeHandler(h)


def test_configure_is_idempotent(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    configure_file_logger(logs_dir)
    configure_file_logger(logs_dir)
    matching = [h for h in logging.getLogger().handlers if getattr(h, "baseFilename", "").endswith(LOG_FILE_NAME)]
    assert len(matching) == 1
    for h in matching:
        logging.getLogger().removeHandler(h)
