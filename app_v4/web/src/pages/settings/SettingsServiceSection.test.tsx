import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsServiceSection } from './SettingsServiceSection';

const mutate = vi.fn();

vi.mock('../../api/hooks', () => ({
  useSystemStatus: () => ({
    data: { service: 'running', version: '4.0.0', started_at: '2026-05-19T08:00:00Z', host: '127.0.0.1',
            port: 8443, uptime_seconds: 7321, scheduler_running: true, db_size_bytes: 12345,
            data_dir: '/data', backups_dir: '/backups', logs_dir: '/logs' },
    isLoading: false,
  }),
  useBackupLocation: () => ({
    data: { backup_root_folder: 'backups', resolved_backups_dir: '/data/backups' },
    isLoading: false,
  }),
  usePatchBackupLocation: () => ({ mutate, isPending: false }),
}));

describe('SettingsServiceSection', () => {
  it('renders host, port and status from /system/status', () => {
    render(<SettingsServiceSection />);
    expect(screen.getByText(/127\.0\.0\.1/)).toBeInTheDocument();
    expect(screen.getByText(/8443/)).toBeInTheDocument();
    expect(screen.getByText(/running/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /restart/i })).toBeDisabled();
  });

  it('saves custom backup location when path changes', async () => {
    const user = userEvent.setup();
    render(<SettingsServiceSection />);

    expect(screen.getByText(/\/data\/backups/)).toBeInTheDocument();
    const input = screen.getByLabelText(/backup root folder/i);
    await user.clear(input);
    await user.type(input, 'D:/NCM Backups');
    await user.click(screen.getByRole('button', { name: /save backup location/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({ backup_root_folder: 'D:/NCM Backups' });
  });
});
