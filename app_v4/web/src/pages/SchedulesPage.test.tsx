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
  useSchedulerStatus: () => ({ data: { running: true, timezone: 'Asia/Jakarta', lock_acquired: true, lock_file: '', jobs: [] } }),
  useTimeSettings: () => ({ data: { timezone: 'Asia/Jakarta', ntp_servers: [], ntp_enabled: false, available_timezones: [], server_now_utc: '', server_now_local: '' } }),
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
