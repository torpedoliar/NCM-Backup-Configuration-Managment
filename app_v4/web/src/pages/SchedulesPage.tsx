import { useState } from 'react';
import {
  useCreateJob,
  useDeleteJob,
  useJobs,
  useRunJobNow,
  useSchedulerStatus,
  useSwitches,
  useTimeSettings,
  useUpdateJob,
} from '../api/hooks';
import type { JobRecord } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';
import { humanizeError } from '../lib/errors';

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
  const [saveError, setSaveError] = useState<string | null>(null);
  const { data: switches = [] } = useSwitches();
  const { data: jobs = [] } = useJobs();
  const { data: schedulerStatus } = useSchedulerStatus();
  const { data: timeSettings } = useTimeSettings();
  const tz = timeSettings?.timezone ?? 'Asia/Jakarta';
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
    setSaveError(null);
  }

  function save() {
    setSaveError(null);
    if (!draft) return;
    if (draft.switch_id === null) {
      setSaveError('Pick a switch first.');
      return;
    }
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
    const onErr = (err: unknown) => setSaveError(humanizeError(err));
    if (draft.id === null) {
      create.mutate(payload, { onSuccess: cancel, onError: onErr });
    } else {
      update.mutate({ id: draft.id, input: payload }, { onSuccess: cancel, onError: onErr });
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

      {saveError ? <div role="alert" className="settings-error" style={{ margin: '8px 0' }}>{saveError}</div> : null}

      <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Switch</th>
            <th>Schedule</th>
            <th>Next run ({tz})</th>
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
                <td>
                  {(() => {
                    const info = schedulerStatus?.jobs.find((j) => j.job_id === job.id);
                    if (!info?.next_run_time) return job.enabled ? 'pending sync…' : 'disabled';
                    return formatTzDateTime(info.next_run_time, tz);
                  })()}
                </td>
                <td>{job.last_run_at ? formatTzDateTime(job.last_run_at, tz) : '—'}</td>
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
      </div>
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
