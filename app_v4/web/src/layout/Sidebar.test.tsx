import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from './Sidebar';

vi.mock('../api/hooks', () => ({
  useSystemMetrics: () => ({
    data: { switches: 7, backups: 42, jobs: 3, failures_24h: 1 },
    isLoading: false,
  }),
}));

vi.mock('wouter', async () => {
  const actual = await vi.importActual<typeof import('wouter')>('wouter');
  return { ...actual, useLocation: () => ['/'] };
});

describe('Sidebar', () => {
  it('renders counts from /system/metrics', () => {
    render(<Sidebar />);
    expect(screen.getByText(/Switches/i).parentElement?.textContent).toContain('7');
    expect(screen.getByText(/Backup History/i).parentElement?.textContent).toContain('42');
    expect(screen.getByText(/Schedules/i).parentElement?.textContent).toContain('3');
  });
});
