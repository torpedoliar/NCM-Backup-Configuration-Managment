# Phase 10 — Settings: Logs (file logger + viewer)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** All log output writes to `logs/ncm-v4.log` (rotating). Admins can view tail through Settings → Logs with level filter, search, level color, auto-refresh toggle.

**Architecture:**
- Backend: `core/logging.py` configures a rotating file handler attached to the root logger. `SAFE_LOG_CONFIG` in `desktop/launcher.py` is reshaped to route uvicorn handlers to the same file. New endpoint `GET /system/logs` reads efficient tail. Admin-only.
- Frontend: SettingsLogsSection with level select, search input, refresh button, optional auto-refresh, color-by-level pre block, "Load more" up to 5000 lines.

**Tech Stack:** Python `logging.handlers`, FastAPI, React Query, vitest, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 10.

---

## Task 1: `core/logging.py` and rotating file handler

**Files:**
- Create: `app_v4/core/logging.py`
- Create: `app_v4/tests/test_logging_setup.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: Run, FAIL.**

Run: `python -m pytest app_v4/tests/test_logging_setup.py -v`

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/core/logging.py app_v4/tests/test_logging_setup.py
git commit -m "feat(core): rotating file logger configuration"
```

---

## Task 2: Wire file logger from desktop and service entrypoints

**Files:**
- Modify: `app_v4/desktop/main.py`
- Modify: `app_v4/service/main.py`
- Modify: `app_v4/desktop/launcher.py`

- [ ] **Step 1: Add invocation in `desktop/main.py:main()`**

Right after `base_dir = _resource_base_dir()` and before any backend code:

```python
from app_v4.core.logging import configure_file_logger
configure_file_logger(base_dir / "logs")
```

- [ ] **Step 2: Add invocation in `service/main.py:main()`**

```python
from app_v4.core.logging import configure_file_logger
from app_v4.core.paths import resolve_paths
settings = Settings()
configure_file_logger(resolve_paths(settings).logs_dir)
```

- [ ] **Step 3: Update `SAFE_LOG_CONFIG` in `desktop/launcher.py`**

Replace `NullHandler` handlers with rotating file handlers pointing at the same file:

```python
import os
from pathlib import Path

def _safe_log_file_path() -> str:
    base = os.environ.get("NCM_V4_BASE_DIR")
    logs_dir = (Path(base) / "logs") if base else (Path.cwd() / "logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return str(logs_dir / "ncm-v4.log")


SAFE_LOG_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
        "access":  {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "default": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _safe_log_file_path(),
            "maxBytes": 10485760,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "default",
        },
        "access": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _safe_log_file_path(),
            "maxBytes": 10485760,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "access",
        },
    },
    "loggers": {
        "uvicorn":         {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error":   {"level": "INFO"},
        "uvicorn.access":  {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}
```

- [ ] **Step 4: Run desktop tests + sanity**

Run: `python -m pytest app_v4/tests/test_desktop_launcher.py -v`
Expected: existing `test_safe_log_config_loads_without_isatty` still passes (RotatingFileHandler doesn't call `isatty`).

- [ ] **Step 5: Commit**

```bash
git add app_v4/desktop/main.py app_v4/service/main.py app_v4/desktop/launcher.py
git commit -m "feat(logging): route desktop and service logs to rotating file"
```

---

## Task 3: Tail parser + `GET /system/logs`

**Files:**
- Create: `app_v4/service/log_tail.py`
- Create: `app_v4/tests/test_log_tail.py`
- Modify: `app_v4/service/api/system.py`
- Modify: `app_v4/tests/test_system_api.py`

- [ ] **Step 1: Failing tests for tail parser**

```python
import re
from pathlib import Path

import pytest

from app_v4.service.log_tail import LogLine, tail_log


def write_log(path: Path, lines: int) -> None:
    levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
    text = "\n".join(
        f"2026-05-20 10:{i:02d}:00 {levels[i % 4]:<8} app_v4: line {i}"
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
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement `log_tail.py`**

```python
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
                    yield piece.decode("utf-8", errors="replace")
        if buffer:
            yield buffer.decode("utf-8", errors="replace")


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
```

- [ ] **Step 4: Run tail tests, PASS.**

- [ ] **Step 5: Failing tests for the API**

```python
@pytest.mark.asyncio
async def test_logs_endpoint_admin_only(client, viewer_token):
    r = await client.get("/api/v1/system/logs", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_logs_endpoint_returns_recent_lines(client, admin_token, tmp_path, runtime, monkeypatch):
    log_file = tmp_path / "ncm-v4.log"
    log_file.write_text(
        "2026-05-20 10:00:00 INFO     uvicorn.error: started\n"
        "2026-05-20 10:00:01 WARNING  uvicorn.error: slow disk\n"
        "2026-05-20 10:00:02 ERROR    uvicorn.error: failed conn\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app_v4.service.api.system._resolve_log_file", lambda runtime: log_file)

    r = await client.get(
        "/api/v1/system/logs?level=ERROR",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert all(line["level"] == "ERROR" for line in body["lines"])
    assert body["log_file"].endswith("ncm-v4.log")
    assert body["log_file_size_bytes"] > 0
```

- [ ] **Step 6: Run, FAIL.**

- [ ] **Step 7: Implement endpoint**

```python
from app_v4.core.logging import LOG_FILE_NAME
from app_v4.service.log_tail import LogLine, tail_log


def _resolve_log_file(runtime: ServiceRuntime) -> Path:
    return resolve_paths(runtime.settings).logs_dir / LOG_FILE_NAME


class LogsResponse(BaseModel):
    lines: list[dict[str, str]]
    total_returned: int
    log_file: str
    log_file_size_bytes: int


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    request: Request,
    lines: int = Query(default=200, ge=1, le=5000),
    level: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> LogsResponse:
    log_path = _resolve_log_file(runtime)
    parsed = tail_log(log_path, lines=lines, level=level, q=q, since=since)
    await runtime.audit_writer.record(
        action="system.logs_viewed",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"lines": lines, "level": level, "q": q},
    )
    return LogsResponse(
        lines=[{"ts": l.ts, "level": l.level, "logger": l.logger, "message": l.message} for l in parsed],
        total_returned=len(parsed),
        log_file=str(log_path),
        log_file_size_bytes=log_path.stat().st_size if log_path.exists() else 0,
    )
```

- [ ] **Step 8: Run, PASS.**

- [ ] **Step 9: Commit**

```bash
git add app_v4/service/log_tail.py app_v4/tests/test_log_tail.py \
        app_v4/service/api/system.py app_v4/tests/test_system_api.py
git commit -m "feat(api): /system/logs tail endpoint"
```

---

## Task 4: SettingsLogsSection UI

**Files:**
- Create: `app_v4/web/src/pages/settings/SettingsLogsSection.tsx`
- Create: `app_v4/web/src/pages/settings/SettingsLogsSection.test.tsx`
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`
- Modify: `app_v4/web/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add types**

```ts
export interface LogLine {
  ts: string;
  level: string;
  logger: string;
  message: string;
}

export interface LogsResponse {
  lines: LogLine[];
  total_returned: number;
  log_file: string;
  log_file_size_bytes: number;
}

export interface LogsFilters {
  lines?: number;
  level?: string;
  q?: string;
}
```

- [ ] **Step 2: Add hook**

```ts
export function useLogs(filters: LogsFilters, autoRefresh: boolean) {
  return useQuery({
    queryKey: ['system', 'logs', filters],
    queryFn: async () => (await api.get<LogsResponse>('/system/logs', { params: filters })).data,
    refetchInterval: autoRefresh ? 5 * SECOND : false,
  });
}
```

- [ ] **Step 3: Failing test**

Create `app_v4/web/src/pages/settings/SettingsLogsSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsLogsSection } from './SettingsLogsSection';

const useLogsMock = vi.fn();
const refetch = vi.fn();

vi.mock('../../api/hooks', () => ({
  useLogs: (filters: unknown, autoRefresh: boolean) => {
    useLogsMock(filters, autoRefresh);
    return {
      data: {
        lines: [
          { ts: '2026-05-20 09:00:00', level: 'INFO',    logger: 'uvicorn', message: 'started' },
          { ts: '2026-05-20 09:00:01', level: 'WARNING', logger: 'uvicorn', message: 'slow disk' },
          { ts: '2026-05-20 09:00:02', level: 'ERROR',   logger: 'uvicorn', message: 'failed conn' },
        ],
        total_returned: 3,
        log_file: '/tmp/ncm-v4.log',
        log_file_size_bytes: 12345,
      },
      refetch,
    };
  },
}));

describe('SettingsLogsSection', () => {
  it('renders lines with level color classes', () => {
    render(<SettingsLogsSection />);
    expect(document.querySelector('.level-INFO')).not.toBeNull();
    expect(document.querySelector('.level-WARNING')).not.toBeNull();
    expect(document.querySelector('.level-ERROR')).not.toBeNull();
  });

  it('changing level dropdown refetches with level param', async () => {
    const user = userEvent.setup();
    useLogsMock.mockClear();
    render(<SettingsLogsSection />);
    await user.selectOptions(screen.getByLabelText(/level/i), 'ERROR');
    await waitFor(() => {
      const lastFilters = useLogsMock.mock.calls.at(-1)![0] as { level?: string };
      expect(lastFilters.level).toBe('ERROR');
    });
  });

  it('Refresh button calls refetch', async () => {
    const user = userEvent.setup();
    refetch.mockClear();
    render(<SettingsLogsSection />);
    await user.click(screen.getByRole('button', { name: /refresh/i }));
    expect(refetch).toHaveBeenCalled();
  });
});
```

- [ ] **Step 4: Implement component**

```tsx
import { useState } from 'react';
import { useLogs } from '../../api/hooks';

const LEVELS = ['', 'INFO', 'WARNING', 'ERROR', 'DEBUG'];

export function SettingsLogsSection() {
  const [level, setLevel] = useState('');
  const [q, setQ] = useState('');
  const [lines, setLines] = useState(200);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const { data, refetch } = useLogs({ level: level || undefined, q: q || undefined, lines }, autoRefresh);

  return (
    <section>
      <h2>Logs</h2>
      <div className="filter-bar">
        <label>
          Level
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((l) => <option key={l} value={l}>{l || 'All'}</option>)}
          </select>
        </label>
        <label>
          Search
          <input value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <button onClick={() => refetch()}>Refresh</button>
        <label>
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
          Auto-refresh (5s)
        </label>
      </div>
      <pre className="log-tail">
        {data?.lines.map((line, idx) => (
          <div key={idx} className={`level-${line.level}`}>
            <span className="ts">{line.ts}</span>{' '}
            <span className="level">{line.level}</span>{' '}
            <span className="logger">{line.logger}</span>: {line.message}
          </div>
        ))}
      </pre>
      <footer>
        Showing {data?.total_returned ?? 0} lines · {data?.log_file ?? '—'}
        {' '}
        {data && data.total_returned >= lines && (
          <button onClick={() => setLines(Math.min(5000, lines + 200))}>Load 200 more</button>
        )}
      </footer>
    </section>
  );
}
```

- [ ] **Step 5: Add to SettingsPage tabs**

```tsx
const TABS = [
  { id: 'service', label: 'Service', section: <SettingsServiceSection /> },
  { id: 'retention', label: 'Retention', section: <SettingsRetentionSection /> },
  { id: 'auth', label: 'Authentication', section: <SettingsAuthSection /> },
  { id: 'logs', label: 'Logs', section: <SettingsLogsSection /> },
  { id: 'about', label: 'About', section: <SettingsAboutSection /> },
];
```

- [ ] **Step 6: Run, PASS + commit**

```bash
git add app_v4/web/src/pages/settings/SettingsLogsSection.tsx \
        app_v4/web/src/pages/settings/SettingsLogsSection.test.tsx \
        app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts \
        app_v4/web/src/pages/SettingsPage.tsx
git commit -m "feat(settings): logs viewer section"
```

---

## Task 5: Verify + bundle

- [ ] Run full backend pytest, frontend vitest, vite build, and PyInstaller rebuild. All green.

- [ ] Manual sanity check (after the user launches the exe): `logs/ncm-v4.log` is created and gets uvicorn startup lines.
