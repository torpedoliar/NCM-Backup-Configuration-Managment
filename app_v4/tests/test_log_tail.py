import re
from pathlib import Path

import pytest

from app_v4.service.log_tail import LogLine, tail_log


def write_log(path: Path, lines: int) -> None:
    levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
    text = "\n".join(
        f"2026-05-20 {(i // 60) + 10:02d}:{i % 60:02d}:00 {levels[i % 4]:<8} app_v4: line {i}"
        for i in range(lines)
    ) + "\n"
    path.write_text(text, encoding="utf-8")


def test_tail_returns_last_n_lines(tmp_path: Path):
    p = tmp_path / "x.log"
    write_log(p, 200)
    result = tail_log(p, lines=20)
    assert len(result) == 20
    assert result[-1].message == "line 199"


def test_tail_filters_level(tmp_path: Path):
    p = tmp_path / "x.log"
    write_log(p, 80)
    result = tail_log(p, lines=80, level="ERROR")
    assert result and all(line.level == "ERROR" for line in result)


def test_tail_filters_query(tmp_path: Path):
    p = tmp_path / "x.log"
    write_log(p, 50)
    result = tail_log(p, lines=50, q="line 4")
    assert result and all("line 4" in line.message for line in result)


def test_tail_returns_empty_when_file_missing(tmp_path: Path):
    assert tail_log(tmp_path / "missing.log", lines=10) == []
