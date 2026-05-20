# Phase 8 — Settings: Service / Retention / About

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder Settings page with three working sections: read-only Service info, editable Retention windows, read-only About/status. Introduce vertical-tab layout used by Phase 9 and 10 too.

**Architecture:**
- Backend: `data/runtime_settings.json` (new) holds editable runtime config; `core/runtime_settings.py` provides typed accessor + atomic save. `RetentionService` consumes this file and reschedules when `retention_hour/minute` change. New endpoints `GET/PATCH /system/retention`. `/system/status` extended with `data_dir`, `backups_dir`, `logs_dir`.
- Frontend: SettingsPage gets vertical tabs, three components (`SettingsServiceSection`, `SettingsRetentionSection`, `SettingsAboutSection`).

**Tech Stack:** Pydantic v2, FastAPI, APScheduler `reschedule_job`, React Query, Wouter sub-routes, vitest, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 8.

---

## Task 1: `core/runtime_settings.py` storage helper

**Files:**
- Create: `app_v4/core/runtime_settings.py`
- Create: `app_v4/tests/test_runtime_settings.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from pathlib import Path

from app_v4.core.runtime_settings import (
    RetentionSettings,
    RuntimeSettings,
    load_runtime_settings,
    save_runtime_settings,
)


def test_load_returns_defaults_when_file_missing(tmp_path: Path):
    rs = load_runtime_settings(tmp_path / "missing.json")
    assert rs.retention.backup_min_keep == 1
    assert rs.retention.backup_retention_days == 365
    assert rs.retention.audit_retention_days == 90
    assert rs.retention.retention_hour == 3
    assert rs.retention.retention_minute == 0


def test_save_and_load_round_trip(tmp_path: Path):
    target = tmp_path / "data" / "runtime_settings.json"
    rs = RuntimeSettings(
        retention=RetentionSettings(
            backup_min_keep=2, backup_retention_days=30,
            audit_retention_days=60, retention_hour=4, retention_minute=15,
        ),
    )
    save_runtime_settings(target, rs)
    loaded = load_runtime_settings(target)
    assert loaded == rs


def test_load_returns_defaults_when_file_corrupt(tmp_path: Path):
    target = tmp_path / "rs.json"
    target.write_text("not json")
    rs = load_runtime_settings(target)
    assert rs.retention.backup_min_keep == 1


def test_save_creates_parent_directories(tmp_path: Path):
    target = tmp_path / "deep" / "data" / "runtime_settings.json"
    save_runtime_settings(target, RuntimeSettings())
    assert target.exists()
```

- [ ] **Step 2: Run, FAIL.**

Run: `python -m pytest app_v4/tests/test_runtime_settings.py -v`

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RetentionSettings:
    backup_min_keep: int = 1
    backup_retention_days: int = 365
    audit_retention_days: int = 90
    retention_hour: int = 3
    retention_minute: int = 0


@dataclass(frozen=True)
class RuntimeSettings:
    retention: RetentionSettings = field(default_factory=RetentionSettings)


def load_runtime_settings(path: Path) -> RuntimeSettings:
    if not path.exists():
        return RuntimeSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        retention_data = data.get("retention", {})
        return RuntimeSettings(retention=RetentionSettings(**{
            k: v for k, v in retention_data.items()
            if k in RetentionSettings.__dataclass_fields__
        }))
    except (json.JSONDecodeError, TypeError, ValueError):
        return RuntimeSettings()


def save_runtime_settings(path: Path, settings: RuntimeSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/core/runtime_settings.py app_v4/tests/test_runtime_settings.py
git commit -m "feat(core): runtime_settings.json storage with retention defaults"
```

---

## Task 2: `RetentionService` reads from runtime settings

**Files:**
- Modify: `app_v4/service/retention_service.py`
- Modify: `app_v4/service/runtime.py`
- Modify: `app_v4/tests/test_retention_service.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_retention_service_uses_runtime_settings_for_audit_days(tmp_path, session_factory):
    from app_v4.core.runtime_settings import RetentionSettings, RuntimeSettings, save_runtime_settings
    from app_v4.service.retention_service import RetentionService
    from app_v4.core.config import Settings

    rs_file = tmp_path / "data" / "runtime_settings.json"
    save_runtime_settings(rs_file, RuntimeSettings(retention=RetentionSettings(audit_retention_days=7)))
    settings = Settings(base_dir=tmp_path)
    service = RetentionService(settings, session_factory, runtime_settings_path=rs_file)
    assert service._effective_audit_retention_days() == 7
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Modify `RetentionService`**

Add an optional `runtime_settings_path` parameter; if provided, read it on each `run_once` invocation; fall back to `settings.audit_retention_days`. Method `_effective_audit_retention_days()` returns the value used.

- [ ] **Step 4: Wire from `service/runtime.py`**

In `build_runtime`, pass `runtime_settings_path=paths.data_dir / "runtime_settings.json"` to `RetentionService`. Same for any other places it's instantiated.

- [ ] **Step 5: Run, PASS.**

- [ ] **Step 6: Commit**

```bash
git add app_v4/service/retention_service.py app_v4/service/runtime.py app_v4/tests/test_retention_service.py
git commit -m "feat(retention): pull retention windows from runtime_settings.json"
```

---

## Task 3: `/system/retention` endpoints + scheduler reschedule

**Files:**
- Modify: `app_v4/service/api/system.py`
- Modify: `app_v4/service/scheduler.py`
- Modify: `app_v4/tests/test_system_api.py`

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_get_retention_returns_defaults(client, viewer_token):
    r = await client.get("/api/v1/system/retention", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["backup_retention_days"] == 365
    assert data["retention_hour"] == 3


@pytest.mark.asyncio
async def test_patch_retention_admin_only(client, operator_token):
    r = await client.patch(
        "/api/v1/system/retention",
        json={"backup_retention_days": 30},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_patch_retention_validates_ranges(client, admin_token):
    r = await client.patch(
        "/api/v1/system/retention",
        json={"backup_retention_days": 1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_retention_persists_and_reschedules(client, admin_token, runtime, tmp_path):
    r = await client.patch(
        "/api/v1/system/retention",
        json={"retention_hour": 5, "retention_minute": 30},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    job = runtime.scheduler_service.scheduler.get_job("retention-nightly")
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "5"
    assert fields["minute"] == "30"
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement endpoints**

```python
class RetentionResponse(BaseModel):
    backup_min_keep: int
    backup_retention_days: int
    audit_retention_days: int
    retention_hour: int
    retention_minute: int


class RetentionPatch(BaseModel):
    backup_min_keep: int | None = Field(default=None, ge=1)
    backup_retention_days: int | None = Field(default=None, ge=7)
    audit_retention_days: int | None = Field(default=None, ge=7)
    retention_hour: int | None = Field(default=None, ge=0, le=23)
    retention_minute: int | None = Field(default=None, ge=0, le=59)


@router.get("/retention", response_model=RetentionResponse)
async def get_retention(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> RetentionResponse:
    paths = resolve_paths(runtime.settings)
    rs = load_runtime_settings(paths.data_dir / "runtime_settings.json")
    return RetentionResponse(**asdict(rs.retention))


@router.patch("/retention", response_model=RetentionResponse)
async def patch_retention(
    payload: RetentionPatch,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> RetentionResponse:
    paths = resolve_paths(runtime.settings)
    target = paths.data_dir / "runtime_settings.json"
    current = load_runtime_settings(target)
    updates = payload.model_dump(exclude_none=True)
    new_retention = replace(current.retention, **updates)
    new_settings = replace(current, retention=new_retention)
    save_runtime_settings(target, new_settings)

    if runtime.scheduler_service is not None and (
        "retention_hour" in updates or "retention_minute" in updates
    ):
        runtime.scheduler_service.reschedule_retention(
            new_retention.retention_hour, new_retention.retention_minute
        )

    await runtime.audit_writer.record(
        action="system.retention_updated",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"changes": updates},
    )
    return RetentionResponse(**asdict(new_retention))
```

Add helper to `SchedulerService`:

```python
def reschedule_retention(self, hour: int, minute: int) -> None:
    if self.scheduler.get_job("retention-nightly"):
        from apscheduler.triggers.cron import CronTrigger
        self.scheduler.reschedule_job(
            "retention-nightly", trigger=CronTrigger(hour=hour, minute=minute),
        )
```

Imports: `from dataclasses import asdict, replace`.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/system.py app_v4/service/scheduler.py app_v4/tests/test_system_api.py
git commit -m "feat(api): GET/PATCH /system/retention with reschedule"
```

---

## Task 4: `/system/status` exposes paths

**Files:**
- Modify: `app_v4/service/api/system.py`
- Modify: `app_v4/tests/test_system_api.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_status_returns_paths(client, viewer_token):
    r = await client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 200
    payload = r.json()
    assert "data_dir" in payload and "backups_dir" in payload and "logs_dir" in payload
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Extend `StatusResponse` and the status route**

```python
class StatusResponse(BaseModel):
    service: str
    version: str
    started_at: datetime
    host: str
    port: int
    uptime_seconds: int
    scheduler_running: bool
    db_size_bytes: int
    data_dir: str
    backups_dir: str
    logs_dir: str
```

In the route, populate `data_dir=str(paths.data_dir)`, `backups_dir=str(paths.backups_dir)`, `logs_dir=str(paths.logs_dir)`.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/system.py app_v4/tests/test_system_api.py
git commit -m "feat(api): /system/status exposes data/backups/logs paths"
```

---

## Task 5: SettingsPage vertical tabs + Service section

**Files:**
- Modify: `app_v4/web/src/pages/SettingsPage.tsx`
- Create: `app_v4/web/src/pages/settings/SettingsServiceSection.tsx`
- Create: `app_v4/web/src/pages/settings/SettingsServiceSection.test.tsx`
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`
- Modify: `app_v4/web/src/App.tsx`

- [ ] **Step 1: Add `SystemStatus` type + hook**

`types.ts`:
```ts
export interface SystemStatus {
  service: string;
  version: string;
  started_at: string;
  host: string;
  port: number;
  uptime_seconds: number;
  scheduler_running: boolean;
  db_size_bytes: number;
  data_dir: string;
  backups_dir: string;
  logs_dir: string;
}
```

`hooks.ts`:
```ts
export function useSystemStatus() {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: async () => (await api.get<SystemStatus>('/system/status')).data,
    staleTime: 30 * SECOND,
  });
}
```

- [ ] **Step 2: Failing test for Service section**

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SettingsServiceSection } from './SettingsServiceSection';

vi.mock('../../api/hooks', () => ({
  useSystemStatus: () => ({
    data: { service: 'running', version: '4.0.0', started_at: '2026-05-19T08:00:00Z', host: '127.0.0.1',
            port: 8443, uptime_seconds: 7321, scheduler_running: true, db_size_bytes: 12345,
            data_dir: '/data', backups_dir: '/backups', logs_dir: '/logs' },
    isLoading: false,
  }),
}));

describe('SettingsServiceSection', () => {
  it('renders host, port and status from /system/status', () => {
    render(<SettingsServiceSection />);
    expect(screen.getByText(/127\.0\.0\.1/)).toBeInTheDocument();
    expect(screen.getByText(/8443/)).toBeInTheDocument();
    expect(screen.getByText(/running/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /restart/i })).toBeDisabled();
  });
});
```

- [ ] **Step 3: Run, FAIL.**

- [ ] **Step 4: Implement SettingsServiceSection**

```tsx
import { useSystemStatus } from '../../api/hooks';

function fmtUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

export function SettingsServiceSection() {
  const { data: status } = useSystemStatus();
  return (
    <section>
      <h2>Service</h2>
      <dl className="settings-list">
        <div><dt>Status</dt><dd>{status?.service ?? '—'}</dd></div>
        <div><dt>Bind</dt><dd>{status ? `${status.host}:${status.port}` : '—'}</dd></div>
        <div><dt>Version</dt><dd>{status?.version ?? '—'}</dd></div>
        <div><dt>Started at</dt><dd>{status ? new Date(status.started_at).toLocaleString() : '—'}</dd></div>
        <div><dt>Uptime</dt><dd>{status ? fmtUptime(status.uptime_seconds) : '—'}</dd></div>
      </dl>
      <button title="Restart not yet implemented; close and reopen the app instead." disabled>
        Restart service
      </button>
    </section>
  );
}
```

- [ ] **Step 5: Vertical-tab SettingsPage**

```tsx
import { useLocation, useRoute } from 'wouter';
import { SettingsServiceSection } from './settings/SettingsServiceSection';
import { SettingsRetentionSection } from './settings/SettingsRetentionSection';
import { SettingsAboutSection } from './settings/SettingsAboutSection';

const TABS = [
  { id: 'service', label: 'Service', section: <SettingsServiceSection /> },
  { id: 'retention', label: 'Retention', section: <SettingsRetentionSection /> },
  { id: 'about', label: 'About', section: <SettingsAboutSection /> },
];

export function SettingsPage() {
  const [, setLocation] = useLocation();
  const [, params] = useRoute('/settings/:tab');
  const active = params?.tab ?? 'service';
  const tab = TABS.find((t) => t.id === active) ?? TABS[0];
  return (
    <main className="settings-page">
      <p className="marker">/08 · SETTINGS</p>
      <div className="settings-layout">
        <nav className="settings-tabs">
          {TABS.map((t) => (
            <button key={t.id} data-active={t.id === active} onClick={() => setLocation(`/settings/${t.id}`)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="settings-content">{tab.section}</div>
      </div>
    </main>
  );
}
```

Wire route in `App.tsx`:
```tsx
<Route path="/settings"><SettingsPage /></Route>
<Route path="/settings/:tab"><SettingsPage /></Route>
```

- [ ] **Step 6: Run + commit**

```bash
npm --prefix app_v4/web test -- --run
git add app_v4/web/src/pages/SettingsPage.tsx \
        app_v4/web/src/pages/settings/SettingsServiceSection.tsx \
        app_v4/web/src/pages/settings/SettingsServiceSection.test.tsx \
        app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts \
        app_v4/web/src/App.tsx
git commit -m "feat(settings): vertical tabs + Service section"
```

---

## Task 6: SettingsRetentionSection

**Files:**
- Create: `app_v4/web/src/pages/settings/SettingsRetentionSection.tsx`
- Create: `app_v4/web/src/pages/settings/SettingsRetentionSection.test.tsx`
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`

- [ ] **Step 1: Add types + hooks**

```ts
export interface RetentionSettings {
  backup_min_keep: number;
  backup_retention_days: number;
  audit_retention_days: number;
  retention_hour: number;
  retention_minute: number;
}

export function useRetention() {
  return useQuery({
    queryKey: ['system', 'retention'],
    queryFn: async () => (await api.get<RetentionSettings>('/system/retention')).data,
    staleTime: 60 * SECOND,
  });
}

export function usePatchRetention() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: Partial<RetentionSettings>) =>
      (await api.patch<RetentionSettings>('/system/retention', input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['system', 'retention'] }),
  });
}
```

- [ ] **Step 2: Failing test**

Create `app_v4/web/src/pages/settings/SettingsRetentionSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsRetentionSection } from './SettingsRetentionSection';

const mutate = vi.fn();

vi.mock('../../api/hooks', () => ({
  useRetention: () => ({
    data: {
      backup_min_keep: 1,
      backup_retention_days: 365,
      audit_retention_days: 90,
      retention_hour: 3,
      retention_minute: 0,
    },
    isLoading: false,
  }),
  usePatchRetention: () => ({ mutate, isPending: false }),
}));

describe('SettingsRetentionSection', () => {
  it('disables Save until a field changes, then submits only the dirty field', async () => {
    const user = userEvent.setup();
    render(<SettingsRetentionSection />);
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();

    const days = screen.getByLabelText(/Backup retention/i);
    await user.clear(days);
    await user.type(days, '180');

    const save = screen.getByRole('button', { name: /save/i });
    expect(save).not.toBeDisabled();
    await user.click(save);

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({ backup_retention_days: 180 });
  });
});
```

- [ ] **Step 3: Run, FAIL.**

- [ ] **Step 4: Implement section**

Create `app_v4/web/src/pages/settings/SettingsRetentionSection.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { usePatchRetention, useRetention } from '../../api/hooks';
import type { RetentionSettings } from '../../api/types';

const FIELDS: { key: keyof RetentionSettings; label: string; min: number; max?: number }[] = [
  { key: 'backup_min_keep', label: 'Backup minimum keep', min: 1 },
  { key: 'backup_retention_days', label: 'Backup retention (days)', min: 7 },
  { key: 'audit_retention_days', label: 'Audit retention (days)', min: 7 },
  { key: 'retention_hour', label: 'Sweep hour', min: 0, max: 23 },
  { key: 'retention_minute', label: 'Sweep minute', min: 0, max: 59 },
];

export function SettingsRetentionSection() {
  const { data } = useRetention();
  const patch = usePatchRetention();
  const [draft, setDraft] = useState<RetentionSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) setDraft({ ...data });
  }, [data]);

  if (!draft || !data) return <p>Loading…</p>;

  const dirtyKeys = (Object.keys(draft) as (keyof RetentionSettings)[]).filter(
    (key) => draft[key] !== data[key],
  );

  function save() {
    setError(null);
    if (!data) return;
    const updates: Partial<RetentionSettings> = {};
    for (const key of dirtyKeys) {
      (updates as Record<string, number>)[key] = draft![key];
    }
    patch.mutate(updates, {
      onError: (err: unknown) => setError(err instanceof Error ? err.message : 'Save failed'),
    });
  }

  return (
    <section>
      <h2>Retention</h2>
      <form
        className="settings-form"
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
      >
        {FIELDS.map((field) => (
          <label key={field.key} className="settings-field">
            <span>{field.label}</span>
            <input
              type="number"
              min={field.min}
              max={field.max}
              value={draft[field.key]}
              onChange={(event) => setDraft({ ...draft, [field.key]: Number(event.target.value) })}
            />
          </label>
        ))}
        {error && <div role="alert" className="settings-error">{error}</div>}
        <button type="submit" disabled={dirtyKeys.length === 0 || patch.isPending}>
          {patch.isPending ? 'Saving…' : 'Save'}
        </button>
      </form>
    </section>
  );
}
```

- [ ] **Step 5: Run, PASS.**

- [ ] **Step 6: Commit**

```bash
git add app_v4/web/src/pages/settings/SettingsRetentionSection.tsx \
        app_v4/web/src/pages/settings/SettingsRetentionSection.test.tsx \
        app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts
git commit -m "feat(settings): retention windows editor"
```

---

## Task 7: SettingsAboutSection

**Files:**
- Create: `app_v4/web/src/pages/settings/SettingsAboutSection.tsx`
- Create: `app_v4/web/src/pages/settings/SettingsAboutSection.test.tsx`

- [ ] **Step 1: Failing test**

Render with mocked `useSystemStatus` and `useSystemMetrics`. Assert: version, db_size, data_dir, backups_dir, logs_dir, switches/backups/jobs/failures all visible.

- [ ] **Step 2: Implement**

```tsx
import { useSystemMetrics, useSystemStatus } from '../../api/hooks';

function fmtBytes(n: number): string {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  if (n > 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

export function SettingsAboutSection() {
  const { data: status } = useSystemStatus();
  const { data: metrics } = useSystemMetrics();
  return (
    <section>
      <h2>About</h2>
      <dl className="settings-list">
        <div><dt>Application</dt><dd>NCM v4 Ops Terminal</dd></div>
        <div><dt>Version</dt><dd>{status?.version ?? '—'}</dd></div>
        <div><dt>Switches under management</dt><dd>{metrics?.switches ?? '—'}</dd></div>
        <div><dt>Total backups</dt><dd>{metrics?.backups ?? '—'}</dd></div>
        <div><dt>Scheduled jobs</dt><dd>{metrics?.jobs ?? '—'}</dd></div>
        <div><dt>Failures (24h)</dt><dd>{metrics?.failures_24h ?? '—'}</dd></div>
        <div><dt>Database size</dt><dd>{status ? fmtBytes(status.db_size_bytes) : '—'}</dd></div>
        <div><dt>Data path</dt><dd>{status?.data_dir ?? '—'}</dd></div>
        <div><dt>Backups path</dt><dd>{status?.backups_dir ?? '—'}</dd></div>
        <div><dt>Logs path</dt><dd>{status?.logs_dir ?? '—'}</dd></div>
      </dl>
    </section>
  );
}
```

- [ ] **Step 3: Run, PASS.**

- [ ] **Step 4: Commit**

```bash
git add app_v4/web/src/pages/settings/SettingsAboutSection.tsx \
        app_v4/web/src/pages/settings/SettingsAboutSection.test.tsx
git commit -m "feat(settings): about section with paths and metrics"
```

---

## Task 8: Verify + bundle

- [ ] Run full backend pytest, full frontend vitest, `npm run build`, `installer/v4/build_app.ps1 -SkipWebBuild`. All green.
