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
