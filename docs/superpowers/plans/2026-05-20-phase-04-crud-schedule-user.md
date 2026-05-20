# Phase 4 — CRUD Schedule + User (inline)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inline Add/Edit/Toggle/Delete for backup schedules and users; Run-now action; admin reset password; weekly/monthly schedule columns.

**Architecture:**
- Backend: schema migration adds `Job.day_of_week`, `Job.day_of_month`. New endpoints `POST /jobs/{id}/run` and `POST /users/{id}/password`. Scheduler trigger builder reads new columns instead of hardcoded values.
- Frontend: SchedulesPage and UsersPage gain inline rows + action menu + reset-password modal.

**Tech Stack:** SQLAlchemy 2 async, FastAPI, APScheduler, React Query, vitest, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 4.

---

## Task 1: Schema migration for `day_of_week`, `day_of_month`

**Files:**
- Modify: `app_v4/data/models.py`
- Modify: `app_v4/data/db.py`
- Modify: `app_v4/tests/test_db_init.py`

- [ ] **Step 1: Write failing test**

Append to `app_v4/tests/test_db_init.py`:

```python
@pytest.mark.asyncio
async def test_jobs_table_has_day_of_week_and_day_of_month(tmp_path):
    db_url = f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}"
    engine = create_async_engine(db_url)
    await init_db(engine)
    async with engine.begin() as conn:
        cols = await conn.run_sync(lambda sync_conn: {c['name'] for c in inspect(sync_conn).get_columns('jobs')})
    assert 'day_of_week' in cols
    assert 'day_of_month' in cols
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Add columns**

`app_v4/data/models.py` — class `Job`, after `schedule_minute`:

```python
    day_of_week: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    day_of_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

`app_v4/data/db.py` — append in `_run_sqlite_migrations`:

```python
    await _add_column_if_missing(conn, "jobs", "day_of_week", "VARCHAR(3)")
    await _add_column_if_missing(conn, "jobs", "day_of_month", "INTEGER")
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/data/models.py app_v4/data/db.py app_v4/tests/test_db_init.py
git commit -m "feat(db): add day_of_week and day_of_month to jobs"
```

---

## Task 2: Scheduler reads new columns

**Files:**
- Modify: `app_v4/service/scheduler.py`
- Modify: `app_v4/tests/test_scheduler.py`

- [ ] **Step 1: Write failing test**

Append to `app_v4/tests/test_scheduler.py`:

```python
def test_build_trigger_weekly_uses_day_of_week(scheduler_service):
    trigger = scheduler_service._build_trigger_v2(
        interval_minutes=10080,
        schedule_hour=8,
        schedule_minute=30,
        day_of_week="fri",
        day_of_month=None,
    )
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["day_of_week"] == "fri"
    assert fields["hour"] == "8"
    assert fields["minute"] == "30"


def test_build_trigger_monthly_uses_day_of_month(scheduler_service):
    trigger = scheduler_service._build_trigger_v2(
        interval_minutes=43200,
        schedule_hour=2,
        schedule_minute=0,
        day_of_week=None,
        day_of_month=15,
    )
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["day"] == "15"
    assert fields["hour"] == "2"
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Replace `_build_trigger`**

Edit `scheduler.py`. Replace the existing private with a new method that accepts the new params; delegate from old. Keep backward compatibility by reading the columns when the job object is provided.

```python
def _build_trigger_v2(
    self,
    interval_minutes: int,
    schedule_hour: int,
    schedule_minute: int,
    day_of_week: str | None,
    day_of_month: int | None,
):
    if interval_minutes == 1440:
        return CronTrigger(hour=schedule_hour, minute=schedule_minute)
    if interval_minutes == 10080:
        return CronTrigger(day_of_week=day_of_week or "mon", hour=schedule_hour, minute=schedule_minute)
    if interval_minutes == 43200:
        return CronTrigger(day=day_of_month or 1, hour=schedule_hour, minute=schedule_minute)
    return IntervalTrigger(minutes=interval_minutes)
```

Then update `add_job` signature:

```python
def add_job(
    self,
    job_id: int,
    switch_id: int,
    interval_minutes: int,
    schedule_hour: int,
    schedule_minute: int,
    day_of_week: str | None = None,
    day_of_month: int | None = None,
) -> None:
    aps_id = f"backup_job_{job_id}"
    self.scheduler.add_job(
        self.execute_scheduled_backup,
        trigger=self._build_trigger_v2(interval_minutes, schedule_hour, schedule_minute, day_of_week, day_of_month),
        id=aps_id,
        args=[job_id, switch_id],
        replace_existing=True,
        name=f"Backup Job {job_id}",
    )
    self.job_map[job_id] = aps_id
    self.job_interval_map[job_id] = interval_minutes
    self.job_time_map[job_id] = (schedule_hour, schedule_minute)
```

In `sync_once`, call `add_job(job.id, job.switch_id, job.interval_minutes, job.schedule_hour, job.schedule_minute, job.day_of_week, job.day_of_month)`.

- [ ] **Step 4: Run, PASS.**

Run: `python -m pytest app_v4/tests/test_scheduler.py -v`

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/scheduler.py app_v4/tests/test_scheduler.py
git commit -m "feat(scheduler): respect job day_of_week and day_of_month"
```

---

## Task 3: `POST /jobs/{id}/run` endpoint

**Files:**
- Modify: `app_v4/service/api/jobs.py`
- Modify: `app_v4/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_run_job_now_triggers_backup(client, admin_token, seeded_job_id, monkeypatch, runtime):
    called = {}
    async def fake_execute(switch_id, backup_type, job_id, triggered_by_user_id):
        called.update({"switch_id": switch_id, "backup_type": backup_type, "job_id": job_id})
        return {"success": True, "backup_id": 1, "message": "", "file_path": "", "size_kb": 0}
    monkeypatch.setattr(runtime.backup_service, "execute_backup", fake_execute)

    r = await client.post(
        f"/api/v1/jobs/{seeded_job_id}/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 202
    assert called["job_id"] == seeded_job_id
    assert called["backup_type"] == "manual_schedule"
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement endpoint**

Edit `app_v4/service/api/jobs.py`:

```python
@router.post("/jobs/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_job_now(
    job_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> dict:
    repo = Repository(session)
    job = await repo.get_job(job_id)
    if job is None:
        raise problem(404, "Not Found", "Job not found")
    if runtime.backup_service is None:
        raise problem(503, "Service Unavailable", "Backup service is not initialized")
    await runtime.audit_writer.record(
        action="schedule.run_now",
        user_id=user.user_id,
        target_type="job",
        target_id=str(job_id),
        ip=request.client.host if request.client else None,
    )
    result = await runtime.backup_service.execute_backup(
        switch_id=job.switch_id,
        backup_type="manual_schedule",
        job_id=job_id,
        triggered_by_user_id=user.user_id,
    )
    return {"backup_id": result.get("backup_id"), "success": result.get("success")}
```

Make sure `repo.get_job` exists; if not, add to `Repository`.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/jobs.py app_v4/data/repository.py app_v4/tests/test_jobs_api.py
git commit -m "feat(jobs): POST /jobs/{id}/run for manual schedule trigger"
```

---

## Task 4: `POST /users/{id}/password` endpoint

**Files:**
- Modify: `app_v4/service/api/users.py`
- Modify: `app_v4/tests/test_users_api.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_admin_reset_password_changes_login(client, admin_token, seeded_operator):
    r = await client.post(
        f"/api/v1/users/{seeded_operator['id']}/password",
        json={"password": "NewPassw0rd!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    r = await client.post(
        "/api/v1/auth/login",
        json={"username": seeded_operator['username'], "password": "NewPassw0rd!"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_admin_only(client, operator_token, seeded_operator):
    r = await client.post(
        f"/api/v1/users/{seeded_operator['id']}/password",
        json={"password": "NewPassw0rd!"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement endpoint**

Edit `app_v4/service/api/users.py`:

```python
class PasswordResetRequest(BaseModel):
    password: str


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    if not payload.password or len(payload.password) < 8:
        raise problem(422, "Unprocessable Entity", "Password must be at least 8 characters")
    repo = Repository(session)
    user = await repo.get_user_by_id(user_id)
    if user is None:
        raise problem(404, "Not Found", "User not found")
    user.password_hash = runtime.auth_service.hash_password(payload.password)
    await session.commit()
    await runtime.audit_writer.record(
        action="user.password_reset_by_admin",
        user_id=actor.user_id,
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/users.py app_v4/tests/test_users_api.py
git commit -m "feat(users): admin password reset endpoint"
```

---

## Task 5: Frontend mutation hooks for schedules + users

**Files:**
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`

- [ ] **Step 1: Add types**

```ts
export interface JobCreateInput {
  switch_id: number;
  name: string;
  interval_minutes: number;
  schedule_hour: number;
  schedule_minute: number;
  day_of_week?: string | null;
  day_of_month?: number | null;
  enabled: boolean;
}

export type JobUpdateInput = Partial<JobCreateInput>;

export interface UserCreateInput {
  username: string;
  password: string;
  role: Role;
  is_active?: boolean;
}

export type UserUpdateInput = Partial<Omit<UserCreateInput, 'password'>>;
```

Also extend `JobRecord` with the new optional fields:

```ts
export interface JobRecord { id: number; switch_id: number; name: string; interval_minutes: number; schedule_hour: number; schedule_minute: number; day_of_week?: string | null; day_of_month?: number | null; enabled: boolean; last_run_at?: string | null; }
```

- [ ] **Step 2: Add hooks**

```ts
export function useCreateJob() { /* POST /jobs ; invalidate ['jobs'] */ }
export function useUpdateJob() { /* PATCH /jobs/{id} ; invalidate ['jobs'] */ }
export function useDeleteJob() { /* DELETE /jobs/{id} ; invalidate ['jobs'] */ }
export function useRunJobNow() { /* POST /jobs/{id}/run ; invalidate ['backups'] */ }

export function useCreateUser() { /* POST /users */ }
export function useUpdateUser() { /* PATCH /users/{id} */ }
export function useDeleteUser() { /* DELETE /users/{id} */ }
export function useResetUserPassword() { /* POST /users/{id}/password */ }
```

Each follows the pattern from Phase 3 hooks (use `useMutation`, invalidate relevant queryKey).

- [ ] **Step 3: Build to type-check**

Run: `npm --prefix app_v4/web run build`

- [ ] **Step 4: Commit**

```bash
git add app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts
git commit -m "feat(api): mutation hooks for schedules and users"
```

---

## Task 6: SchedulesPage inline CRUD

**Files:**
- Modify: `app_v4/web/src/pages/SchedulesPage.tsx`
- Modify: `app_v4/web/src/pages/SchedulesPage.test.tsx`

- [ ] **Step 1: Write failing tests**

Replace `app_v4/web/src/pages/SchedulesPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SchedulesPage } from './SchedulesPage';

const createMutate = vi.fn();
const updateMutate = vi.fn();
const runNowMutate = vi.fn();

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [
    { id: 1, name: 'SW-A', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
    { id: 2, name: 'SW-INACTIVE', ip: '10.0.0.2', host: '10.0.0.2', protocol: 'ssh', port: 22, credential_id: 1, is_active: false },
  ], isLoading: false }),
  useJobs: () => ({ data: [
    { id: 10, switch_id: 1, name: 'Backup SW-A', interval_minutes: 1440, schedule_hour: 8, schedule_minute: 30, day_of_week: null, day_of_month: null, enabled: true },
  ], isLoading: false }),
  useCreateJob: () => ({ mutate: createMutate, isPending: false }),
  useUpdateJob: () => ({ mutate: updateMutate, isPending: false }),
  useDeleteJob: () => ({ mutate: vi.fn(), isPending: false }),
  useRunJobNow: () => ({ mutate: runNowMutate, isPending: false }),
}));

describe('SchedulesPage', () => {
  it('opens a draft row on + Add schedule and lists only active switches', async () => {
    const user = userEvent.setup();
    render(<SchedulesPage />);
    await user.click(screen.getByRole('button', { name: /add schedule/i }));
    const switchSelect = screen.getByLabelText(/switch/i);
    expect(switchSelect.textContent).toContain('SW-A');
    expect(switchSelect.textContent).not.toContain('SW-INACTIVE');
  });

  it('Run now triggers useRunJobNow.mutate', async () => {
    const user = userEvent.setup();
    render(<SchedulesPage />);
    await user.click(screen.getByRole('button', { name: /run now/i }));
    expect(runNowMutate).toHaveBeenCalledWith(10);
  });

  it('toggling enabled checkbox calls useUpdateJob with {enabled}', async () => {
    const user = userEvent.setup();
    render(<SchedulesPage />);
    await user.click(screen.getByRole('checkbox', { name: /enabled/i }));
    expect(updateMutate).toHaveBeenCalledWith({ id: 10, input: { enabled: false } });
  });
});
```

- [ ] **Step 2: Run, FAIL.**

Run: `npm --prefix app_v4/web test -- --run src/pages/SchedulesPage.test.tsx`

- [ ] **Step 3: Implement page**

Overwrite `app_v4/web/src/pages/SchedulesPage.tsx`:

```tsx
import { useState } from 'react';
import {
  useCreateJob,
  useDeleteJob,
  useJobs,
  useRunJobNow,
  useSwitches,
  useUpdateJob,
} from '../api/hooks';
import type { JobRecord } from '../api/types';

type ScheduleType = 'interval' | 'daily' | 'weekly' | 'monthly';

const TYPE_INTERVAL: Record<ScheduleType, number> = {
  interval: 60,
  daily: 1440,
  weekly: 10080,
  monthly: 43200,
};

const DAYS_OF_WEEK = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

interface DraftJob {
  id: number | null;
  switch_id: number | null;
  name: string;
  type: ScheduleType;
  interval_minutes: number;
  schedule_hour: number;
  schedule_minute: number;
  day_of_week: string | null;
  day_of_month: number | null;
  enabled: boolean;
}

const EMPTY_DRAFT: DraftJob = {
  id: null,
  switch_id: null,
  name: '',
  type: 'interval',
  interval_minutes: 60,
  schedule_hour: 8,
  schedule_minute: 0,
  day_of_week: null,
  day_of_month: null,
  enabled: true,
};

function inferType(job: JobRecord): ScheduleType {
  if (job.interval_minutes === 1440) return 'daily';
  if (job.interval_minutes === 10080) return 'weekly';
  if (job.interval_minutes === 43200) return 'monthly';
  return 'interval';
}

function describeSchedule(job: JobRecord): string {
  const t = inferType(job);
  const hh = String(job.schedule_hour).padStart(2, '0');
  const mm = String(job.schedule_minute).padStart(2, '0');
  switch (t) {
    case 'interval':
      return `Every ${job.interval_minutes}m`;
    case 'daily':
      return `Daily ${hh}:${mm}`;
    case 'weekly':
      return `Weekly ${(job.day_of_week ?? 'mon').toUpperCase()} ${hh}:${mm}`;
    case 'monthly':
      return `Monthly day ${job.day_of_month ?? 1} ${hh}:${mm}`;
  }
}

export function SchedulesPage() {
  const [draft, setDraft] = useState<DraftJob | null>(null);
  const { data: switches = [] } = useSwitches();
  const { data: jobs = [] } = useJobs();
  const create = useCreateJob();
  const update = useUpdateJob();
  const remove = useDeleteJob();
  const runNow = useRunJobNow();

  const activeSwitches = switches.filter((s) => s.is_active);

  function startAdd() {
    setDraft({ ...EMPTY_DRAFT, switch_id: activeSwitches[0]?.id ?? null });
  }

  function startEdit(job: JobRecord) {
    setDraft({
      id: job.id,
      switch_id: job.switch_id,
      name: job.name,
      type: inferType(job),
      interval_minutes: job.interval_minutes,
      schedule_hour: job.schedule_hour,
      schedule_minute: job.schedule_minute,
      day_of_week: job.day_of_week ?? null,
      day_of_month: job.day_of_month ?? null,
      enabled: job.enabled,
    });
  }

  function cancel() {
    setDraft(null);
  }

  function save() {
    if (!draft || draft.switch_id === null) return;
    const payload = {
      switch_id: draft.switch_id,
      name: draft.name || `Backup ${switches.find((s) => s.id === draft.switch_id)?.name ?? ''}`,
      interval_minutes: TYPE_INTERVAL[draft.type],
      schedule_hour: draft.schedule_hour,
      schedule_minute: draft.schedule_minute,
      day_of_week: draft.type === 'weekly' ? draft.day_of_week ?? 'mon' : null,
      day_of_month: draft.type === 'monthly' ? draft.day_of_month ?? 1 : null,
      enabled: draft.enabled,
    };
    if (draft.id === null) {
      create.mutate(payload, { onSuccess: cancel });
    } else {
      update.mutate({ id: draft.id, input: payload }, { onSuccess: cancel });
    }
  }

  function setType(type: ScheduleType) {
    if (!draft) return;
    setDraft({ ...draft, type, interval_minutes: TYPE_INTERVAL[type] });
  }

  return (
    <main>
      <header className="page-header">
        <p className="marker">/04 · SCH</p>
        <h1 className="headline">Schedules run without watchers.</h1>
        <div className="page-actions">
          <button onClick={startAdd} disabled={draft !== null || activeSwitches.length === 0}>
            + Add schedule
          </button>
        </div>
      </header>

      <table className="data-table">
        <thead>
          <tr>
            <th>Switch</th>
            <th>Schedule</th>
            <th>Last run</th>
            <th>Enabled</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {draft && draft.id === null && (
            <DraftScheduleRow
              draft={draft}
              setDraft={setDraft}
              activeSwitches={activeSwitches}
              setType={setType}
              onSave={save}
              onCancel={cancel}
            />
          )}
          {jobs.map((job) =>
            draft && draft.id === job.id ? (
              <DraftScheduleRow
                key={job.id}
                draft={draft}
                setDraft={setDraft}
                activeSwitches={activeSwitches}
                setType={setType}
                onSave={save}
                onCancel={cancel}
              />
            ) : (
              <tr key={job.id}>
                <td>{switches.find((s) => s.id === job.switch_id)?.name ?? `#${job.switch_id}`}</td>
                <td>{describeSchedule(job)}</td>
                <td>{job.last_run_at ? new Date(job.last_run_at).toLocaleString() : '—'}</td>
                <td>
                  <label>
                    <input
                      type="checkbox"
                      aria-label="Enabled"
                      checked={job.enabled}
                      onChange={() =>
                        update.mutate({ id: job.id, input: { enabled: !job.enabled } })
                      }
                    />
                  </label>
                </td>
                <td className="row-actions">
                  <button onClick={() => startEdit(job)}>Edit</button>
                  <button onClick={() => runNow.mutate(job.id)}>Run now</button>
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete schedule for ${switches.find((s) => s.id === job.switch_id)?.name ?? job.switch_id}?`)) {
                        remove.mutate(job.id);
                      }
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </main>
  );
}

function DraftScheduleRow(props: {
  draft: DraftJob;
  setDraft: (d: DraftJob) => void;
  activeSwitches: { id: number; name: string }[];
  setType: (t: ScheduleType) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const { draft, setDraft, activeSwitches, setType, onSave, onCancel } = props;
  return (
    <tr className="draft-row">
      <td>
        <label>
          Switch
          <select
            value={draft.switch_id ?? ''}
            onChange={(e) => setDraft({ ...draft, switch_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="" disabled>Select…</option>
            {activeSwitches.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>
      </td>
      <td>
        <select value={draft.type} onChange={(e) => setType(e.target.value as ScheduleType)}>
          <option value="interval">Interval</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
        {draft.type === 'interval' && (
          <input
            type="number"
            min={1}
            max={1440}
            value={draft.interval_minutes}
            onChange={(e) => setDraft({ ...draft, interval_minutes: Number(e.target.value) })}
          />
        )}
        {draft.type !== 'interval' && (
          <>
            <input
              type="time"
              value={`${String(draft.schedule_hour).padStart(2, '0')}:${String(draft.schedule_minute).padStart(2, '0')}`}
              onChange={(e) => {
                const [h, m] = e.target.value.split(':').map(Number);
                setDraft({ ...draft, schedule_hour: h, schedule_minute: m });
              }}
            />
            {draft.type === 'weekly' && (
              <select
                value={draft.day_of_week ?? 'mon'}
                onChange={(e) => setDraft({ ...draft, day_of_week: e.target.value })}
              >
                {DAYS_OF_WEEK.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}
            {draft.type === 'monthly' && (
              <input
                type="number"
                min={1}
                max={31}
                value={draft.day_of_month ?? 1}
                onChange={(e) => setDraft({ ...draft, day_of_month: Number(e.target.value) })}
              />
            )}
          </>
        )}
      </td>
      <td>—</td>
      <td>
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
      </td>
      <td className="row-actions">
        <button onClick={onSave} disabled={draft.switch_id === null}>Save</button>
        <button onClick={onCancel}>Cancel</button>
      </td>
    </tr>
  );
}
```

- [ ] **Step 4: Run, PASS.**

Run: `npm --prefix app_v4/web test -- --run src/pages/SchedulesPage.test.tsx`

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/pages/SchedulesPage.tsx app_v4/web/src/pages/SchedulesPage.test.tsx
git commit -m "feat(schedules): inline CRUD with run-now and toggle"
```

---

## Task 7: UsersPage inline CRUD + reset password modal

**Files:**
- Modify: `app_v4/web/src/pages/UsersPage.tsx`
- Modify: `app_v4/web/src/pages/UsersPage.test.tsx`

- [ ] **Step 1: Write failing tests**

Replace `app_v4/web/src/pages/UsersPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UsersPage } from './UsersPage';

const createMutate = vi.fn();
const updateMutate = vi.fn();
const deleteMutate = vi.fn();
const resetMutateAsync = vi.fn().mockResolvedValue(undefined);

vi.mock('../api/hooks', () => ({
  useUsers: () => ({ data: [
    { id: 1, username: 'admin', role: 'admin', is_active: true, created_at: '2026-05-01T00:00:00Z' },
    { id: 2, username: 'op1',   role: 'operator', is_active: true, created_at: '2026-05-01T00:00:00Z' },
  ], isLoading: false }),
  useCreateUser: () => ({ mutate: createMutate, isPending: false }),
  useUpdateUser: () => ({ mutate: updateMutate, isPending: false }),
  useDeleteUser: () => ({ mutate: deleteMutate, isPending: false }),
  useResetUserPassword: () => ({ mutateAsync: resetMutateAsync, isPending: false }),
}));

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({ user: { id: 1, username: 'admin', role: 'admin', is_active: true } }),
}));

describe('UsersPage', () => {
  it('opens an inline draft row on + Add user', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    await user.click(screen.getByRole('button', { name: /add user/i }));
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  it('disables Delete on the current user row', () => {
    render(<UsersPage />);
    const row = screen.getByText('admin').closest('tr')!;
    const deleteBtn = row.querySelector('button[data-action="delete"]') as HTMLButtonElement;
    expect(deleteBtn).toBeDisabled();
  });

  it('toggling Active calls useUpdateUser with {is_active: false}', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    const row = screen.getByText('op1').closest('tr')!;
    await user.click(row.querySelector('input[type=checkbox]') as HTMLElement);
    expect(updateMutate).toHaveBeenCalledWith({ id: 2, input: { is_active: false } });
  });

  it('Reset password expansion submits new password', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    const row = screen.getByText('op1').closest('tr')!;
    await user.click(row.querySelector('button[data-action="reset"]') as HTMLElement);
    await user.type(screen.getByPlaceholderText(/new password/i), 'NewPass123');
    await user.click(screen.getByRole('button', { name: /save new password/i }));
    expect(resetMutateAsync).toHaveBeenCalledWith({ id: 2, password: 'NewPass123' });
  });
});
```

- [ ] **Step 2: Run, FAIL.**

Run: `npm --prefix app_v4/web test -- --run src/pages/UsersPage.test.tsx`

- [ ] **Step 3: Implement page**

Overwrite `app_v4/web/src/pages/UsersPage.tsx`:

```tsx
import { useState } from 'react';
import {
  useCreateUser,
  useDeleteUser,
  useResetUserPassword,
  useUpdateUser,
  useUsers,
} from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import type { Role } from '../api/types';

const ROLES: Role[] = ['admin', 'operator', 'viewer'];

interface DraftUser {
  id: number | null;
  username: string;
  role: Role;
  password: string;
  is_active: boolean;
}

const EMPTY_DRAFT: DraftUser = {
  id: null,
  username: '',
  role: 'viewer',
  password: '',
  is_active: true,
};

export function UsersPage() {
  const auth = useAuth();
  const myId = auth.user?.id ?? null;
  const [draft, setDraft] = useState<DraftUser | null>(null);
  const [resetingUserId, setResetingUserId] = useState<number | null>(null);
  const [newPwd, setNewPwd] = useState('');

  const { data: users = [] } = useUsers();
  const create = useCreateUser();
  const update = useUpdateUser();
  const remove = useDeleteUser();
  const resetPwd = useResetUserPassword();

  function startAdd() {
    setDraft({ ...EMPTY_DRAFT });
  }

  function startEdit(user: { id: number; username: string; role: Role; is_active: boolean }) {
    setDraft({
      id: user.id,
      username: user.username,
      role: user.role,
      password: '',
      is_active: user.is_active,
    });
  }

  function cancel() {
    setDraft(null);
  }

  function save() {
    if (!draft) return;
    if (draft.id === null) {
      create.mutate(
        { username: draft.username, role: draft.role, password: draft.password, is_active: draft.is_active },
        { onSuccess: cancel },
      );
    } else {
      update.mutate(
        { id: draft.id, input: { username: draft.username, role: draft.role, is_active: draft.is_active } },
        { onSuccess: cancel },
      );
    }
  }

  async function submitReset(userId: number) {
    await resetPwd.mutateAsync({ id: userId, password: newPwd });
    setResetingUserId(null);
    setNewPwd('');
  }

  return (
    <main>
      <header className="page-header">
        <p className="marker">/07 · USERS</p>
        <h1 className="headline">Access is operational control.</h1>
        <div className="page-actions">
          <button onClick={startAdd} disabled={draft !== null}>+ Add user</button>
        </div>
      </header>

      <table className="data-table">
        <thead>
          <tr>
            <th>Username</th><th>Role</th><th>Active</th><th>Created</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {draft && draft.id === null && (
            <DraftUserRow draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} isNew />
          )}
          {users.map((u) =>
            draft && draft.id === u.id ? (
              <DraftUserRow key={u.id} draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} />
            ) : (
              <>
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.role}</td>
                  <td>
                    <input
                      type="checkbox"
                      aria-label="Active"
                      checked={u.is_active}
                      disabled={u.id === myId}
                      onChange={() => update.mutate({ id: u.id, input: { is_active: !u.is_active } })}
                    />
                  </td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="row-actions">
                    <button onClick={() => startEdit(u)}>Edit</button>
                    <button data-action="reset" onClick={() => setResetingUserId(u.id)}>
                      Reset password
                    </button>
                    <button
                      data-action="delete"
                      disabled={u.id === myId}
                      onClick={() => {
                        if (window.confirm(`Delete user ${u.username}?`)) remove.mutate(u.id);
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                {resetingUserId === u.id && (
                  <tr key={`${u.id}-reset`} className="draft-subrow">
                    <td colSpan={5}>
                      <input
                        type="password"
                        placeholder="New password"
                        value={newPwd}
                        onChange={(e) => setNewPwd(e.target.value)}
                      />
                      <button onClick={() => submitReset(u.id)}>Save new password</button>
                      <button onClick={() => { setResetingUserId(null); setNewPwd(''); }}>Cancel</button>
                    </td>
                  </tr>
                )}
              </>
            ),
          )}
        </tbody>
      </table>
    </main>
  );
}

function DraftUserRow(props: {
  draft: DraftUser;
  setDraft: (d: DraftUser) => void;
  onSave: () => void;
  onCancel: () => void;
  isNew?: boolean;
}) {
  const { draft, setDraft, onSave, onCancel, isNew } = props;
  return (
    <tr className="draft-row">
      <td>
        <input
          placeholder="Username"
          value={draft.username}
          onChange={(e) => setDraft({ ...draft, username: e.target.value })}
        />
      </td>
      <td>
        <select value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value as Role })}>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </td>
      <td>
        <input
          type="checkbox"
          checked={draft.is_active}
          onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
        />
      </td>
      <td>
        {isNew && (
          <input
            type="password"
            placeholder="Password"
            value={draft.password}
            onChange={(e) => setDraft({ ...draft, password: e.target.value })}
          />
        )}
      </td>
      <td className="row-actions">
        <button onClick={onSave}>Save</button>
        <button onClick={onCancel}>Cancel</button>
      </td>
    </tr>
  );
}
```

- [ ] **Step 4: Run, PASS.**

Run: `npm --prefix app_v4/web test -- --run src/pages/UsersPage.test.tsx`

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/pages/UsersPage.tsx app_v4/web/src/pages/UsersPage.test.tsx
git commit -m "feat(users): inline CRUD with role select, active toggle, password reset"
```

---

## Task 8: Final verification + bundle rebuild

- [ ] **Step 1: Backend full**

Run: `python -m pytest app_v4/tests/ -q`
Expected: green.

- [ ] **Step 2: Frontend full**

Run: `npm --prefix app_v4/web test -- --run && npm --prefix app_v4/web run build`
Expected: green + build OK.

- [ ] **Step 3: Rebuild bundle**

Run: `powershell -ExecutionPolicy Bypass -File installer/v4/build_app.ps1 -SkipWebBuild`
Expected: `==> Build OK`.
