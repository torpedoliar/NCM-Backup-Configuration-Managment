from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<logger>[^:]+):\s+(?P<message>.*)$"
)


@dataclass(frozen=True)
class LogLine:
    ts: str
    level: str
    logger: str
    message: str


def _read_reverse_lines(path: Path, byte_chunk: int = 64 * 1024):
    with path.open("rb") as fp:
        fp.seek(0, os.SEEK_END)
        position = fp.tell()
        buffer = b""
        while position > 0:
            read_size = min(byte_chunk, position)
            position -= read_size
            fp.seek(position)
            chunk = fp.read(read_size)
            buffer = chunk + buffer
            split = buffer.split(b"\n")
            buffer = split[0]
            for piece in reversed(split[1:]):
                if piece:
                    yield piece.rstrip(b"\r").decode("utf-8", errors="replace")
        if buffer:
            yield buffer.rstrip(b"\r").decode("utf-8", errors="replace")


def tail_log(
    path: Path,
    lines: int = 200,
    level: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
) -> list[LogLine]:
    if not path.exists():
        return []
    collected: list[LogLine] = []
    for raw in _read_reverse_lines(path):
        match = _LINE_RE.match(raw)
        if not match:
            continue
        line = LogLine(
            ts=match.group("ts"),
            level=match.group("level"),
            logger=match.group("logger"),
            message=match.group("message"),
        )
        if level and line.level != level:
            continue
        if q and q.lower() not in line.message.lower() and q.lower() not in line.logger.lower():
            continue
        if since:
            try:
                line_dt = datetime.strptime(line.ts, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if line_dt < since:
                break
        collected.append(line)
        if len(collected) >= lines:
            break
    collected.reverse()
    return collected
