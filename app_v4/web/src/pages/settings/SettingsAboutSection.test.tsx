import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SettingsAboutSection } from './SettingsAboutSection';

vi.mock('../../api/hooks', () => ({
  useSystemStatus: () => ({
    data: { service: 'running', version: '4.0.0', started_at: '2026-05-19T08:00:00Z', host: '127.0.0.1',
            port: 8443, uptime_seconds: 100, scheduler_running: true, db_size_bytes: 5242880,
            data_dir: '/var/data', backups_dir: '/var/backups', logs_dir: '/var/logs' },
    isLoading: false,
  }),
  useSystemMetrics: () => ({
    data: { switches: 12, backups: 348, jobs: 5, failures_24h: 1 },
    isLoading: false,
  }),
}));

describe('SettingsAboutSection', () => {
  it('renders application metadata, metrics, and paths', () => {
    render(<SettingsAboutSection />);
    expect(screen.getByText('NCM v4 Ops Terminal')).toBeInTheDocument();
    expect(screen.getByText('4.0.0')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('348')).toBeInTheDocument();
    expect(screen.getByText('/var/data')).toBeInTheDocument();
    expect(screen.getByText('/var/backups')).toBeInTheDocument();
    expect(screen.getByText('/var/logs')).toBeInTheDocument();
    expect(screen.getByText(/5\.0 MB/)).toBeInTheDocument();
  });
});
